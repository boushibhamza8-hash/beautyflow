from decimal import Decimal
from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils import timezone
from django.utils.text import slugify
from accounts.models import User, UserRole
from .models import (
    Appointment,
    CashRegisterDay,
    CashTransaction,
    Client,
    EmployeeProfile,
    Expense,
    Notification,
    Payment,
    Product,
    Promotion,
    Review,
    Salon,
    Service,
    StockMovement,
    Subscription,
    SubscriptionPlan,
)

phone_validator = RegexValidator(
    regex=r'^\+?[0-9\s\-]{8,20}$',
    message='Veuillez saisir un numéro de téléphone valide.'
)


class StyledFormMixin:
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = 'form-control'
            if isinstance(field.widget, forms.CheckboxInput):
                css = 'form-check-input'
            elif isinstance(field.widget, forms.SelectMultiple):
                css = 'form-select form-multiselect'
            elif isinstance(field.widget, forms.Select):
                css = 'form-select'
            field.widget.attrs.setdefault('class', css)


class SalonCreateForm(StyledFormMixin, forms.ModelForm):
    admin_first_name = forms.CharField(label='Prénom du propriétaire')
    admin_last_name = forms.CharField(label='Nom du propriétaire')
    admin_email = forms.EmailField(label='Email administrateur')
    admin_phone = forms.CharField(label='Téléphone administrateur', validators=[phone_validator])
    admin_username = forms.CharField(label='Nom d’utilisateur administrateur')
    admin_password = forms.CharField(label='Mot de passe initial', widget=forms.PasswordInput)

    class Meta:
        model = Salon
        fields = [
            'name', 'slug', 'owner_name', 'email', 'phone', 'address', 'city', 'description',
            'opening_hours', 'currency', 'loyalty_points_per_dh', 'loyalty_reward_notes', 'plan', 'subscription_status', 'instagram', 'whatsapp',
            'brand_primary', 'brand_secondary', 'closed_days'
        ]

    def clean_slug(self):
        return slugify(self.cleaned_data['slug'])

    def clean_phone(self):
        value = self.cleaned_data['phone']
        phone_validator(value)
        return value

    def save(self, commit=True):
        salon = super().save(commit=commit)
        user = User.objects.create_user(
            username=self.cleaned_data['admin_username'],
            first_name=self.cleaned_data['admin_first_name'],
            last_name=self.cleaned_data['admin_last_name'],
            email=self.cleaned_data['admin_email'],
            phone=self.cleaned_data['admin_phone'],
            role=UserRole.SALON_ADMIN,
            salon=salon,
            password=self.cleaned_data['admin_password'],
        )
        EmployeeProfile.objects.create(salon=salon, user=user, status='active', working_hours=salon.opening_hours)
        plan, _ = SubscriptionPlan.objects.get_or_create(
            code=salon.plan,
            defaults={
                'name': salon.get_plan_display(),
                'price': {'starter': 199, 'pro': 349, 'premium': 599}.get(salon.plan, 199),
                'features': 'Plan généré automatiquement',
            }
        )
        Subscription.objects.create(
            salon=salon,
            plan=plan,
            status=salon.subscription_status,
            starts_at=timezone.localdate(),
        )
        return salon


class SalonSettingsForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Salon
        fields = [
            'name', 'owner_name', 'email', 'phone', 'address', 'city', 'description', 'opening_hours',
            'closed_days', 'currency', 'loyalty_points_per_dh', 'loyalty_reward_notes', 'brand_primary', 'brand_secondary', 'instagram', 'facebook',
            'tiktok', 'whatsapp'
        ]

    def clean_phone(self):
        value = self.cleaned_data['phone']
        phone_validator(value)
        return value


class ClientForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Client
        fields = ['first_name', 'last_name', 'phone', 'email', 'birthday', 'gender', 'notes', 'source', 'preferences', 'is_vip']
        widgets = {'birthday': forms.DateInput(attrs={'type': 'date'})}

    def clean_phone(self):
        value = self.cleaned_data['phone']
        phone_validator(value)
        return value


class ServiceForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Service
        fields = ['name', 'description', 'category', 'price', 'duration_minutes', 'is_active', 'assigned_employees']
        widgets = {'assigned_employees': forms.SelectMultiple()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request and getattr(self.request.user, 'salon_id', None):
            self.fields['assigned_employees'].queryset = User.objects.filter(salon=self.request.user.salon, role=UserRole.EMPLOYEE)


class EmployeeForm(StyledFormMixin, forms.Form):
    first_name = forms.CharField(label='Prénom')
    last_name = forms.CharField(label='Nom')
    username = forms.CharField(label='Nom d’utilisateur')
    email = forms.EmailField(label='Email')
    phone = forms.CharField(label='Téléphone', validators=[phone_validator])
    position = forms.CharField(label='Poste')
    password = forms.CharField(label='Mot de passe', widget=forms.PasswordInput)
    working_hours = forms.CharField(label='Horaires', widget=forms.Textarea, required=False)
    commission_percentage = forms.DecimalField(label='Commission %', max_digits=5, decimal_places=2, initial=0)
    status = forms.ChoiceField(label='Statut', choices=EmployeeProfile.STATUS_CHOICES)

    def save(self, salon):
        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            email=self.cleaned_data['email'],
            phone=self.cleaned_data['phone'],
            position=self.cleaned_data['position'],
            role=UserRole.EMPLOYEE,
            salon=salon,
            password=self.cleaned_data['password'],
        )
        EmployeeProfile.objects.create(
            salon=salon,
            user=user,
            working_hours=self.cleaned_data['working_hours'],
            commission_percentage=self.cleaned_data['commission_percentage'],
            status=self.cleaned_data['status'],
        )
        return user


class EmployeeUpdateForm(StyledFormMixin, forms.Form):
    first_name = forms.CharField(label='Prénom')
    last_name = forms.CharField(label='Nom')
    email = forms.EmailField(label='Email')
    phone = forms.CharField(label='Téléphone', validators=[phone_validator])
    position = forms.CharField(label='Poste')
    working_hours = forms.CharField(label='Horaires', widget=forms.Textarea, required=False)
    commission_percentage = forms.DecimalField(label='Commission %', max_digits=5, decimal_places=2, initial=0)
    status = forms.ChoiceField(label='Statut', choices=EmployeeProfile.STATUS_CHOICES)
    is_active_member = forms.BooleanField(label='Compte actif', required=False)

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.pop('instance')
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial.update({
                'first_name': self.instance.first_name,
                'last_name': self.instance.last_name,
                'email': self.instance.email,
                'phone': self.instance.phone,
                'position': self.instance.position,
                'working_hours': getattr(self.instance.employee_profile, 'working_hours', ''),
                'commission_percentage': getattr(self.instance.employee_profile, 'commission_percentage', 0),
                'status': getattr(self.instance.employee_profile, 'status', 'active'),
                'is_active_member': self.instance.is_active_member,
            })

    def save(self):
        user = self.instance
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        user.phone = self.cleaned_data['phone']
        user.position = self.cleaned_data['position']
        user.is_active_member = self.cleaned_data['is_active_member']
        user.save()
        profile, _ = EmployeeProfile.objects.get_or_create(salon=user.salon, user=user)
        profile.working_hours = self.cleaned_data['working_hours']
        profile.commission_percentage = self.cleaned_data['commission_percentage']
        profile.status = self.cleaned_data['status']
        profile.save()
        return user


class AppointmentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ['client', 'service', 'employee', 'date', 'start_time', 'end_time', 'price', 'status', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request and getattr(self.request.user, 'salon_id', None):
            salon = self.request.user.salon
            self.fields['client'].queryset = Client.objects.filter(salon=salon)
            self.fields['service'].queryset = Service.objects.filter(salon=salon, is_active=True)
            self.fields['employee'].queryset = User.objects.filter(salon=salon, role=UserRole.EMPLOYEE, is_active_member=True)

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_time')
        end = cleaned.get('end_time')
        employee = cleaned.get('employee')
        date = cleaned.get('date')
        if start and end and end <= start:
            raise ValidationError('L’heure de fin doit être postérieure à l’heure de début.')
        if employee and date and start and end:
            conflicts = Appointment.objects.filter(
                salon=self.request.user.salon,
                employee=employee,
                date=date,
            ).exclude(pk=self.instance.pk).exclude(status__in=['cancelled', 'no_show'])
            for item in conflicts:
                if start < item.end_time and end > item.start_time:
                    raise ValidationError('Conflit détecté avec un autre rendez-vous pour cet employé.')
        return cleaned


class PaymentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['client', 'appointment', 'amount', 'payment_method', 'date', 'employee', 'notes']
        widgets = {'date': forms.DateInput(attrs={'type': 'date'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request and getattr(self.request.user, 'salon_id', None):
            salon = self.request.user.salon
            self.fields['client'].queryset = Client.objects.filter(salon=salon)
            self.fields['appointment'].queryset = Appointment.objects.filter(salon=salon)
            self.fields['employee'].queryset = User.objects.filter(salon=salon)


class ExpenseForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['category', 'description', 'amount', 'payment_method', 'date', 'notes']
        widgets = {'date': forms.DateInput(attrs={'type': 'date'})}


class ProductForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'category', 'sku', 'supplier', 'purchase_price', 'selling_price', 'current_stock', 'minimum_stock', 'expiration_date', 'status']
        widgets = {'expiration_date': forms.DateInput(attrs={'type': 'date'})}

    def clean_current_stock(self):
        value = self.cleaned_data['current_stock']
        if value < 0:
            raise ValidationError('Le stock ne peut pas être négatif.')
        return value


class StockMovementForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = StockMovement
        fields = ['product', 'movement_type', 'quantity', 'date', 'notes']
        widgets = {'date': forms.DateInput(attrs={'type': 'date'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request and getattr(self.request.user, 'salon_id', None):
            self.fields['product'].queryset = Product.objects.filter(salon=self.request.user.salon)

    def clean(self):
        cleaned = super().clean()
        product = cleaned.get('product')
        quantity = cleaned.get('quantity')
        movement_type = cleaned.get('movement_type')
        if quantity is None or quantity == 0:
            raise ValidationError('La quantité doit être différente de zéro.')
        if product and movement_type in ['reduction', 'usage'] and product.current_stock + quantity < 0:
            raise ValidationError('Stock insuffisant pour ce mouvement.')
        return cleaned


class PromotionForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Promotion
        fields = ['name', 'discount_percentage', 'fixed_discount', 'start_date', 'end_date', 'is_active', 'services']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'services': forms.SelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request and getattr(self.request.user, 'salon_id', None):
            self.fields['services'].queryset = Service.objects.filter(salon=self.request.user.salon)

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('discount_percentage') and not cleaned.get('fixed_discount'):
            raise ValidationError('Veuillez saisir une remise en pourcentage ou une remise fixe.')
        if cleaned.get('start_date') and cleaned.get('end_date') and cleaned['end_date'] < cleaned['start_date']:
            raise ValidationError('La date de fin doit être postérieure à la date de début.')
        return cleaned


class ReviewForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Review
        fields = ['client', 'service', 'rating', 'comment', 'date']
        widgets = {'date': forms.DateInput(attrs={'type': 'date'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request and getattr(self.request.user, 'salon_id', None):
            salon = self.request.user.salon
            self.fields['client'].queryset = Client.objects.filter(salon=salon)
            self.fields['service'].queryset = Service.objects.filter(salon=salon)


class CashRegisterDayForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = CashRegisterDay
        fields = ['date', 'opening_balance']
        widgets = {'date': forms.DateInput(attrs={'type': 'date'})}


class CashTransactionForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = CashTransaction
        fields = ['type', 'description', 'amount', 'payment_method', 'date', 'notes']
        widgets = {'date': forms.DateInput(attrs={'type': 'date'})}
