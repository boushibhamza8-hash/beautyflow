from datetime import date, time, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from accounts.models import User, UserRole
from appcore.models import Appointment, Client, EmployeeProfile, Payment, Product, Salon, Service, SubscriptionPlan


class Command(BaseCommand):
    help = 'Charge des données de démonstration pour BEAUTYFLOW.'

    def handle(self, *args, **options):
        plans = {
            'starter': ('Starter', Decimal('199.00')),
            'pro': ('Pro', Decimal('349.00')),
            'premium': ('Premium', Decimal('599.00')),
        }
        for code, (name, price) in plans.items():
            SubscriptionPlan.objects.get_or_create(code=code, defaults={'name': name, 'price': price, 'features': name})

        super_admin, created = User.objects.get_or_create(username='superadmin', defaults={
            'role': UserRole.SUPER_ADMIN,
            'is_superuser': True,
            'is_staff': True,
            'email': 'superadmin@beautyflow.ma',
        })
        if created:
            super_admin.set_password('Admin123!')
            super_admin.save()

        salon, _ = Salon.objects.get_or_create(
            slug='timalux',
            defaults={
                'name': 'TimaLux Beauty Center',
                'owner_name': 'TimaLux Owner',
                'email': 'contact@timalux.ma',
                'phone': '+212600100100',
                'city': 'Casablanca',
                'plan': 'pro',
                'subscription_status': 'active',
                'opening_hours': 'Lun-Sam 09:00-19:00',
                'description': 'Salon premium beauté et esthétique',
                'whatsapp': '+212600100100',
            }
        )
        admin, created = User.objects.get_or_create(username='timalux_admin', defaults={
            'first_name': 'Sanae', 'last_name': 'Manager', 'role': UserRole.SALON_ADMIN,
            'salon': salon, 'email': 'admin@timalux.ma', 'phone': '+212600100101'
        })
        if created:
            admin.set_password('Salon123!')
            admin.save()
        employees = []
        for first in ['Fatima', 'Sara', 'Amina']:
            user, created = User.objects.get_or_create(username=first.lower(), defaults={
                'first_name': first, 'last_name': 'Team', 'role': UserRole.EMPLOYEE,
                'salon': salon, 'email': f'{first.lower()}@timalux.ma', 'phone': '+212600999999', 'position': 'Technicienne'
            })
            if created:
                user.set_password('Employe123!')
                user.save()
            EmployeeProfile.objects.get_or_create(salon=salon, user=user, defaults={'working_hours': '09:00-18:00', 'commission_percentage': 10})
            employees.append(user)

        service_names = [
            ('Microblading', 'Brows', 1200, 120),
            ('Lash Lift', 'Lashes', 450, 60),
            ('Blanchiment', 'Smile', 700, 60),
            ('Manucure', 'Nails', 180, 45),
            ('Soin visage', 'Skin', 550, 75),
        ]
        services = []
        for name, cat, price, duration in service_names:
            service, _ = Service.objects.get_or_create(salon=salon, name=name, defaults={'category': cat, 'price': price, 'duration_minutes': duration})
            service.assigned_employees.set(employees)
            services.append(service)

        client_names = [
            ('Sanae', 'El Amrani', '+212611111111'),
            ('Meryem', 'Zahra', '+212622222222'),
            ('Yassmine', 'K.', '+212633333333'),
            ('Hajar', 'M.', '+212644444444'),
            ('Laila', 'B.', '+212655555555'),
        ]
        clients = []
        for first, last, phone in client_names:
            client, _ = Client.objects.get_or_create(salon=salon, phone=phone, defaults={'first_name': first, 'last_name': last, 'source': 'instagram'})
            clients.append(client)

        today = date.today()
        slots = [(10, 0), (11, 30), (13, 0), (14, 30), (16, 0)]
        for idx, client in enumerate(clients):
            service = services[idx % len(services)]
            employee = employees[idx % len(employees)]
            start_h, start_m = slots[idx]
            appointment, _ = Appointment.objects.get_or_create(
                salon=salon,
                client=client,
                service=service,
                employee=employee,
                date=today,
                start_time=time(start_h, start_m),
                defaults={'end_time': time((start_h + 1) % 24, start_m), 'price': service.price, 'status': 'confirmed'}
            )
            Payment.objects.get_or_create(
                salon=salon,
                client=client,
                appointment=appointment,
                amount=service.price,
                payment_method='cash',
                date=today,
                employee=employee,
            )

        Product.objects.get_or_create(salon=salon, sku='MICRO-01', defaults={'name': 'Pigment Luxe', 'category': 'Brows', 'supplier': 'Pro Supply', 'purchase_price': 250, 'selling_price': 390, 'current_stock': 3, 'minimum_stock': 5})
        Product.objects.get_or_create(salon=salon, sku='LASH-01', defaults={'name': 'Kit Lash Lift', 'category': 'Lashes', 'supplier': 'LashPro', 'purchase_price': 180, 'selling_price': 320, 'current_stock': 12, 'minimum_stock': 4})

        self.stdout.write(self.style.SUCCESS('Données démo créées.'))
        self.stdout.write('Comptes: superadmin / Admin123! | timalux_admin / Salon123! | fatima / Employe123!')
