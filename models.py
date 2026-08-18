from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import Sum, Count
from django.utils import timezone


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Salon(TimestampedModel):
    PLAN_CHOICES = [
        ('starter', 'Starter'),
        ('pro', 'Pro'),
        ('premium', 'Premium'),
    ]
    STATUS_CHOICES = [
        ('trial', 'Essai'),
        ('active', 'Actif'),
        ('suspended', 'Suspendu'),
        ('inactive', 'Inactif'),
    ]

    name = models.CharField(max_length=180)
    slug = models.SlugField(unique=True)
    owner_name = models.CharField(max_length=180)
    email = models.EmailField()
    phone = models.CharField(max_length=30)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='salon_logos/', blank=True, null=True)
    instagram = models.CharField(max_length=120, blank=True)
    whatsapp = models.CharField(max_length=30, blank=True)
    facebook = models.CharField(max_length=120, blank=True)
    tiktok = models.CharField(max_length=120, blank=True)
    brand_primary = models.CharField(max_length=20, default='#c9a34a')
    brand_secondary = models.CharField(max_length=20, default='#1a1a1a')
    opening_hours = models.TextField(blank=True)
    closed_days = models.CharField(max_length=120, blank=True)
    currency = models.CharField(max_length=10, default='MAD')
    loyalty_points_per_dh = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    loyalty_reward_notes = models.TextField(blank=True)
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='starter')
    subscription_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='trial')
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class SubscriptionPlan(TimestampedModel):
    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=120)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    features = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Subscription(TimestampedModel):
    salon = models.OneToOneField(Salon, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, default='trial')
    starts_at = models.DateField(null=True, blank=True)
    ends_at = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)


class SalonOwnedModel(TimestampedModel):
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE)

    class Meta:
        abstract = True


class SalonMembership(TimestampedModel):
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(max_length=20)

    class Meta:
        unique_together = ('salon', 'user')


class Client(SalonOwnedModel):
    SOURCE_CHOICES = [('instagram', 'Instagram'), ('whatsapp', 'WhatsApp'), ('walkin', 'Passage'), ('referral', 'Recommandation'), ('other', 'Autre')]
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    birthday = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=30, blank=True)
    notes = models.TextField(blank=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='other')
    preferences = models.TextField(blank=True)
    is_vip = models.BooleanField(default=False)

    class Meta:
        ordering = ['first_name', 'last_name']
        unique_together = ('salon', 'phone')
        indexes = [models.Index(fields=['salon', 'phone']), models.Index(fields=['salon', 'created_at'])]

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def total_spent(self):
        return self.payments.filter(appointment__status='completed').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    @property
    def visit_count(self):
        return self.appointments.filter(status='completed').count()

    @property
    def average_basket(self):
        visits = self.visit_count
        return self.total_spent / visits if visits else Decimal('0.00')

    @property
    def last_visit(self):
        appointment = self.appointments.filter(status='completed').order_by('-date', '-end_time').first()
        return appointment.date if appointment else None

    @property
    def next_appointment(self):
        today = timezone.localdate()
        return self.appointments.filter(date__gte=today).exclude(status__in=['cancelled', 'no_show']).order_by('date', 'start_time').first()


class Service(SalonOwnedModel):
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=120)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    duration_minutes = models.PositiveIntegerField(default=60)
    is_active = models.BooleanField(default=True)
    image = models.ImageField(upload_to='services/', blank=True, null=True)
    assigned_employees = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='service_assignments')

    class Meta:
        ordering = ['category', 'name']
        indexes = [models.Index(fields=['salon', 'category'])]

    def __str__(self):
        return self.name


class EmployeeProfile(SalonOwnedModel):
    STATUS_CHOICES = [('active', 'Actif'), ('inactive', 'Inactif')]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='employee_profile')
    profile_photo = models.ImageField(upload_to='employees/', blank=True, null=True)
    working_hours = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    commission_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])

    def __str__(self):
        return str(self.user)


class Appointment(SalonOwnedModel):
    STATUS_CHOICES = [
        ('confirmed', 'Confirmé'),
        ('pending', 'En attente'),
        ('completed', 'Terminé'),
        ('cancelled', 'Annulé'),
        ('no_show', 'No-show'),
    ]
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='appointments')
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name='appointments')
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='appointments')
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['date', 'start_time']
        indexes = [models.Index(fields=['salon', 'date']), models.Index(fields=['salon', 'status'])]

    def __str__(self):
        return f"{self.client} - {self.service} - {self.date}"


class Payment(SalonOwnedModel):
    METHOD_CHOICES = [('cash', 'Espèces'), ('card', 'Carte bancaire'), ('transfer', 'Virement'), ('other', 'Autre')]
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='payments')
    appointment = models.ForeignKey(Appointment, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    payment_method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    date = models.DateField(default=timezone.localdate)
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments_received')
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [models.Index(fields=['salon', 'date'])]


class CashRegisterDay(SalonOwnedModel):
    date = models.DateField(default=timezone.localdate)
    opening_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        unique_together = ('salon', 'date')
        ordering = ['-date']


class CashTransaction(SalonOwnedModel):
    TYPE_CHOICES = [('income', 'Entrée'), ('expense', 'Sortie')]
    METHOD_CHOICES = Payment.METHOD_CHOICES
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    payment_method = models.CharField(max_length=20, choices=METHOD_CHOICES, default='cash')
    date = models.DateField(default=timezone.localdate)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-date', '-created_at']


class Expense(SalonOwnedModel):
    CATEGORY_CHOICES = [('rent', 'Loyer'), ('electricity', 'Électricité'), ('products', 'Produits'), ('marketing', 'Marketing'), ('salaries', 'Salaires'), ('maintenance', 'Maintenance'), ('other', 'Autre')]
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    payment_method = models.CharField(max_length=20, choices=Payment.METHOD_CHOICES)
    date = models.DateField(default=timezone.localdate)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-date', '-created_at']


class Product(SalonOwnedModel):
    name = models.CharField(max_length=160)
    category = models.CharField(max_length=120)
    sku = models.CharField(max_length=80)
    supplier = models.CharField(max_length=160, blank=True)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    current_stock = models.IntegerField(default=0)
    minimum_stock = models.IntegerField(default=0)
    expiration_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, default='active')

    class Meta:
        ordering = ['name']
        unique_together = ('salon', 'sku')

    @property
    def stock_status(self):
        if self.current_stock <= 0:
            return 'rupture'
        if self.current_stock <= self.minimum_stock:
            return 'faible'
        return 'ok'

    def __str__(self):
        return self.name


class StockMovement(SalonOwnedModel):
    TYPE_CHOICES = [('entry', 'Entrée'), ('reduction', 'Réduction'), ('adjustment', 'Ajustement'), ('usage', 'Utilisation')]
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_movements')
    movement_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    quantity = models.IntegerField()
    date = models.DateField(default=timezone.localdate)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-date', '-created_at']


class Promotion(SalonOwnedModel):
    name = models.CharField(max_length=160)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    fixed_discount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)
    services = models.ManyToManyField(Service, blank=True, related_name='promotions')

    def __str__(self):
        return self.name


class LoyaltyAccount(SalonOwnedModel):
    client = models.OneToOneField(Client, on_delete=models.CASCADE, related_name='loyalty_account')
    points_balance = models.IntegerField(default=0)
    total_points_earned = models.IntegerField(default=0)
    vip_status = models.BooleanField(default=False)


class LoyaltyTransaction(SalonOwnedModel):
    loyalty_account = models.ForeignKey(LoyaltyAccount, on_delete=models.CASCADE, related_name='transactions')
    points = models.IntegerField()
    reason = models.CharField(max_length=255)
    date = models.DateField(default=timezone.localdate)


class Review(SalonOwnedModel):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='reviews')
    service = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True, blank=True)
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    date = models.DateField(default=timezone.localdate)

    class Meta:
        ordering = ['-date', '-created_at']


class Notification(SalonOwnedModel):
    TYPE_CHOICES = [('stock_low', 'Stock faible'), ('stock_out', 'Produit épuisé'), ('appointment_cancelled', 'Rendez-vous annulé'), ('appointment_new', 'Nouveau rendez-vous'), ('client_new', 'Nouveau client'), ('payment_received', 'Paiement reçu')]
    type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['is_read', '-created_at']
