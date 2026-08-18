from datetime import date, time
from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from accounts.models import User, UserRole
from .models import Appointment, Client, Payment, Product, Salon, Service, SubscriptionPlan, LoyaltyAccount


class BeautyflowTestCase(TestCase):
    def setUp(self):
        self.plan = SubscriptionPlan.objects.create(code='pro', name='Pro', price=349)
        self.salon_a = Salon.objects.create(name='TimaLux Beauty Center', slug='timalux', owner_name='Owner A', email='a@example.com', phone='+212600000001', plan='pro', subscription_status='active')
        self.salon_b = Salon.objects.create(name='Nina Beauty Studio', slug='nina', owner_name='Owner B', email='b@example.com', phone='+212600000002', plan='pro', subscription_status='active')
        self.admin_a = User.objects.create_user(username='admina', password='Secret123!', role=UserRole.SALON_ADMIN, salon=self.salon_a)
        self.admin_b = User.objects.create_user(username='adminb', password='Secret123!', role=UserRole.SALON_ADMIN, salon=self.salon_b)
        self.employee_a = User.objects.create_user(username='empa', password='Secret123!', role=UserRole.EMPLOYEE, salon=self.salon_a, first_name='Fatima')
        self.client_a = Client.objects.create(salon=self.salon_a, first_name='Sanae', last_name='El Amrani', phone='+212611111111')
        self.client_b = Client.objects.create(salon=self.salon_b, first_name='Meryem', last_name='Zahra', phone='+212622222222')
        self.service_a = Service.objects.create(salon=self.salon_a, name='Microblading', category='Brows', price=Decimal('900.00'), duration_minutes=90)
        self.product_a = Product.objects.create(salon=self.salon_a, name='Sérum', category='Soin', sku='SER-001', purchase_price=100, selling_price=180, current_stock=10, minimum_stock=5)

    def test_authentication_login_required(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_multi_tenant_clients_isolation(self):
        self.client.login(username='admina', password='Secret123!')
        response = self.client.get(reverse('clients'))
        self.assertContains(response, 'Sanae')
        self.assertNotContains(response, 'Meryem')

    def test_revenue_metrics_update_with_payment(self):
        self.client.login(username='admina', password='Secret123!')
        appointment = Appointment.objects.create(
            salon=self.salon_a,
            client=self.client_a,
            service=self.service_a,
            employee=self.employee_a,
            date=date.today(),
            start_time=time(10, 0),
            end_time=time(11, 30),
            price=Decimal('900.00'),
            status='completed',
        )
        Payment.objects.create(salon=self.salon_a, client=self.client_a, appointment=appointment, amount=Decimal('900.00'), payment_method='cash', date=date.today(), employee=self.employee_a)
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, '900 DH')

    def test_client_analytics_update(self):
        appointment = Appointment.objects.create(
            salon=self.salon_a,
            client=self.client_a,
            service=self.service_a,
            employee=self.employee_a,
            date=date.today(),
            start_time=time(12, 0),
            end_time=time(13, 0),
            price=Decimal('900.00'),
            status='completed',
        )
        Payment.objects.create(salon=self.salon_a, client=self.client_a, appointment=appointment, amount=Decimal('900.00'), payment_method='cash', date=date.today(), employee=self.employee_a)
        self.assertEqual(self.client_a.total_spent, Decimal('900'))
        self.assertEqual(self.client_a.visit_count, 1)

    def test_stock_movement_updates_quantity(self):
        self.client.login(username='admina', password='Secret123!')
        response = self.client.post(reverse('stock_create'), {
            'product': self.product_a.id,
            'movement_type': 'reduction',
            'quantity': -6,
            'date': date.today(),
            'notes': 'Consommation cabine',
        })
        self.assertEqual(response.status_code, 302)
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.current_stock, 4)

    def test_loyalty_points_created_from_payment(self):
        self.client.login(username='admina', password='Secret123!')
        response = self.client.post(reverse('payment_create'), {
            'client': self.client_a.id,
            'appointment': '',
            'amount': '300.00',
            'payment_method': 'cash',
            'date': date.today(),
            'employee': self.employee_a.id,
            'notes': 'Test',
        })
        self.assertEqual(response.status_code, 302)
        account = LoyaltyAccount.objects.get(client=self.client_a)
        self.assertEqual(account.points_balance, 300)
