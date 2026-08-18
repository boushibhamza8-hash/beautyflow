import json
from datetime import datetime, timedelta
from decimal import Decimal
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import models
from django.db.models import Avg, Count, Q, Sum
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView
from accounts.forms import LoginForm
from accounts.models import User, UserRole
from .forms import (
    AppointmentForm,
    CashRegisterDayForm,
    CashTransactionForm,
    ClientForm,
    EmployeeForm,
    EmployeeUpdateForm,
    ExpenseForm,
    PaymentForm,
    ProductForm,
    PromotionForm,
    ReviewForm,
    SalonCreateForm,
    SalonSettingsForm,
    ServiceForm,
    StockMovementForm,
)
from .models import (
    Appointment,
    CashRegisterDay,
    CashTransaction,
    Client,
    EmployeeProfile,
    Expense,
    LoyaltyAccount,
    LoyaltyTransaction,
    Notification,
    Payment,
    Product,
    Promotion,
    Review,
    Salon,
    Service,
    StockMovement,
    SubscriptionPlan,
)


class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    allowed_roles = []

    def test_func(self):
        return self.request.user.is_authenticated and (
            self.request.user.is_superuser or self.request.user.role in self.allowed_roles
        )


class SalonScopedMixin(LoginRequiredMixin):
    model = None
    search_fields = []
    context_object_name = 'objects'
    paginate_by = 25

    def get_queryset(self):
        qs = self.model.objects.all()
        user = self.request.user
        if not user.is_platform_admin:
            qs = qs.filter(salon=user.salon)
        q = self.request.GET.get('q', '').strip()
        if q and self.search_fields:
            query = Q()
            for field in self.search_fields:
                query |= Q(**{f'{field}__icontains': q})
            qs = qs.filter(query)
        return qs

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def form_valid(self, form):
        if hasattr(form.instance, 'salon_id') and not form.instance.salon_id:
            form.instance.salon = self.request.user.salon
        response = super().form_valid(form)
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('q', '')
        return context


class AdminOnlyMixin(RoleRequiredMixin):
    allowed_roles = [UserRole.SUPER_ADMIN, UserRole.SALON_ADMIN]


class SalonAdminOnlyMixin(RoleRequiredMixin):
    allowed_roles = [UserRole.SALON_ADMIN]


class EmployeeOrAdminMixin(RoleRequiredMixin):
    allowed_roles = [UserRole.SALON_ADMIN, UserRole.EMPLOYEE]


class HomeRedirectView(LoginRequiredMixin, View):
    def get(self, request):
        if request.user.is_platform_admin:
            return redirect('platform_dashboard')
        return redirect('dashboard')


class DashboardView(EmployeeOrAdminMixin, TemplateView):
    template_name = 'dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        salon = user.salon
        today = timezone.localdate()
        month_start = today.replace(day=1)
        appointment_qs = Appointment.objects.filter(salon=salon)
        if user.is_employee:
            appointment_qs = appointment_qs.filter(employee=user)
        payment_qs = Payment.objects.filter(salon=salon)
        if user.is_employee:
            payment_qs = payment_qs.filter(employee=user)
        today_revenue = payment_qs.filter(date=today).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        month_revenue = payment_qs.filter(date__gte=month_start).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        completed_appointments = appointment_qs.filter(status='completed').count()
        cancelled_appointments = appointment_qs.filter(status='cancelled').count()
        today_appointments = appointment_qs.filter(date=today).select_related('client', 'service', 'employee')
        total_clients = Client.objects.filter(salon=salon).count()
        new_clients_month = Client.objects.filter(salon=salon, created_at__date__gte=month_start).count()
        avg_order = payment_qs.aggregate(avg=Avg('amount'))['avg'] or Decimal('0.00')
        returning_clients = Client.objects.filter(salon=salon, appointments__status='completed').annotate(c=Count('appointments')).filter(c__gt=1).count()
        loyal_clients = Client.objects.filter(salon=salon).annotate(
            spending=Sum('payments__amount'),
            visits=Count('appointments', filter=Q(appointments__status='completed')),
        ).order_by('-spending', '-visits')[:5]
        top_employees = User.objects.filter(salon=salon, role=UserRole.EMPLOYEE).annotate(
            revenue=Sum('payments_received__amount', filter=Q(payments_received__date__gte=month_start)),
            appointment_total=Count('appointments', filter=Q(appointments__date__gte=month_start)),
            client_total=Count('appointments__client', distinct=True, filter=Q(appointments__date__gte=month_start)),
        ).order_by('-revenue')[:5]
        notifications = Notification.objects.filter(salon=salon)[:6]
        low_stock = Product.objects.filter(salon=salon, current_stock__lte=models.F('minimum_stock'))[:6]
        context.update({
            'today_revenue': today_revenue,
            'month_revenue': month_revenue,
            'today_appointments_count': today_appointments.count(),
            'new_clients_month': new_clients_month,
            'total_clients': total_clients,
            'completed_appointments': completed_appointments,
            'cancelled_appointments': cancelled_appointments,
            'avg_order': avg_order,
            'returning_clients': returning_clients,
            'today_appointments': today_appointments,
            'loyal_clients': loyal_clients,
            'top_employees': top_employees,
            'notifications': notifications,
            'low_stock': low_stock,
        })
        return context


class PlatformDashboardView(RoleRequiredMixin, TemplateView):
    allowed_roles = [UserRole.SUPER_ADMIN]
    template_name = 'platform/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        salons = Salon.objects.all()
        context.update({
            'total_salons': salons.count(),
            'active_salons': salons.filter(subscription_status='active').count(),
            'trial_salons': salons.filter(subscription_status='trial').count(),
            'suspended_salons': salons.filter(subscription_status='suspended').count(),
            'mrr': salons.filter(subscription_status='active').aggregate(total=Sum('subscription__plan__price'))['total'] or Decimal('0.00'),
            'new_salons': salons.filter(created_at__date__gte=timezone.localdate().replace(day=1)).count(),
            'salons': salons.select_related('subscription')[:20],
            'plans': SubscriptionPlan.objects.all(),
        })
        return context


class SalonCreateView(RoleRequiredMixin, CreateView):
    allowed_roles = [UserRole.SUPER_ADMIN]
    template_name = 'generic_form.html'
    form_class = SalonCreateForm
    success_url = reverse_lazy('platform_dashboard')

    def form_valid(self, form):
        messages.success(self.request, 'Salon créé avec succès.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Créer un salon'
        return context


class SalonUpdateView(RoleRequiredMixin, UpdateView):
    allowed_roles = [UserRole.SUPER_ADMIN]
    template_name = 'generic_form.html'
    model = Salon
    form_class = SalonSettingsForm
    success_url = reverse_lazy('platform_dashboard')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Modifier le salon'
        return context


@login_required
def toggle_salon_status(request, pk):
    if not request.user.is_platform_admin:
        return redirect('dashboard')
    salon = get_object_or_404(Salon, pk=pk)
    salon.subscription_status = 'active' if salon.subscription_status == 'suspended' else 'suspended'
    salon.is_active = salon.subscription_status != 'suspended'
    salon.save()
    messages.success(request, 'Statut du salon mis à jour.')
    return redirect('platform_dashboard')


class ClientListView(EmployeeOrAdminMixin, SalonScopedMixin, ListView):
    model = Client
    template_name = 'clients/list.html'
    context_object_name = 'clients'
    search_fields = ['first_name', 'last_name', 'phone', 'email']

    def get_queryset(self):
        qs = super().get_queryset().annotate(
            total_spending=Sum('payments__amount'),
            visits=Count('appointments', filter=Q(appointments__status='completed')),
        )
        filter_name = self.request.GET.get('filter')
        today = timezone.localdate()
        if filter_name == 'new':
            qs = qs.filter(created_at__date=today)
        elif filter_name == 'loyal':
            qs = qs.filter(appointments__status='completed').annotate(v=Count('appointments')).filter(v__gte=3)
        elif filter_name == 'inactive':
            threshold = today - timedelta(days=getattr(settings, 'INACTIVITY_DAYS_DEFAULT', 60))
            qs = qs.exclude(appointments__date__gte=threshold)
        elif filter_name == 'vip':
            qs = qs.filter(is_vip=True)
        elif filter_name == 'today':
            qs = qs.filter(appointments__date=today)
        elif filter_name == 'month':
            qs = qs.filter(created_at__date__gte=today.replace(day=1))
        return qs.distinct()


class ClientCreateView(AdminOnlyMixin, CreateView):
    template_name = 'generic_form.html'
    form_class = ClientForm
    success_url = reverse_lazy('clients')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def form_valid(self, form):
        form.instance.salon = self.request.user.salon
        response = super().form_valid(form)
        LoyaltyAccount.objects.get_or_create(salon=self.request.user.salon, client=self.object)
        Notification.objects.create(
            salon=self.request.user.salon,
            type='client_new',
            title='Nouveau client',
            message=f'{self.object} a été ajouté(e).',
        )
        messages.success(self.request, 'Client ajouté avec succès.')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Ajouter un client'
        return context


class ClientUpdateView(AdminOnlyMixin, UpdateView):
    model = Client
    form_class = ClientForm
    template_name = 'generic_form.html'
    success_url = reverse_lazy('clients')

    def get_queryset(self):
        return Client.objects.filter(salon=self.request.user.salon)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Modifier le client'
        return context


class ClientDeleteView(AdminOnlyMixin, DeleteView):
    model = Client
    template_name = 'generic_confirm_delete.html'
    success_url = reverse_lazy('clients')

    def get_queryset(self):
        return Client.objects.filter(salon=self.request.user.salon)


class ClientDetailView(EmployeeOrAdminMixin, DetailView):
    model = Client
    template_name = 'clients/detail.html'
    context_object_name = 'client'

    def get_queryset(self):
        return Client.objects.filter(salon=self.request.user.salon)


class ServiceListView(EmployeeOrAdminMixin, SalonScopedMixin, ListView):
    model = Service
    template_name = 'services/list.html'
    context_object_name = 'services'
    search_fields = ['name', 'category']


class ServiceCreateView(AdminOnlyMixin, CreateView):
    form_class = ServiceForm
    template_name = 'generic_form.html'
    success_url = reverse_lazy('services')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def form_valid(self, form):
        form.instance.salon = self.request.user.salon
        messages.success(self.request, 'Service ajouté avec succès.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Ajouter un service'
        return context


class ServiceUpdateView(AdminOnlyMixin, UpdateView):
    model = Service
    form_class = ServiceForm
    template_name = 'generic_form.html'
    success_url = reverse_lazy('services')

    def get_queryset(self):
        return Service.objects.filter(salon=self.request.user.salon)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Modifier le service'
        return context


class ServiceDeleteView(AdminOnlyMixin, DeleteView):
    model = Service
    template_name = 'generic_confirm_delete.html'
    success_url = reverse_lazy('services')

    def get_queryset(self):
        return Service.objects.filter(salon=self.request.user.salon)


class EmployeeListView(AdminOnlyMixin, ListView):
    template_name = 'employees/list.html'
    context_object_name = 'employees'

    def get_queryset(self):
        return User.objects.filter(salon=self.request.user.salon, role=UserRole.EMPLOYEE).select_related('employee_profile')


class EmployeeCreateView(SalonAdminOnlyMixin, View):
    template_name = 'generic_form.html'

    def get(self, request):
        form = EmployeeForm(request=request)
        return render(request, self.template_name, {'form': form, 'title': 'Ajouter un employé'})

    def post(self, request):
        form = EmployeeForm(request.POST, request=request)
        if form.is_valid():
            form.save(request.user.salon)
            messages.success(request, 'Employé ajouté avec succès.')
            return redirect('employees')
        return render(request, self.template_name, {'form': form, 'title': 'Ajouter un employé'})


class EmployeeUpdateView(SalonAdminOnlyMixin, View):
    template_name = 'generic_form.html'

    def get_object(self, pk, user):
        return get_object_or_404(User, pk=pk, salon=user.salon, role=UserRole.EMPLOYEE)

    def get(self, request, pk):
        instance = self.get_object(pk, request.user)
        form = EmployeeUpdateForm(instance=instance, request=request)
        return render(request, self.template_name, {'form': form, 'title': 'Modifier l’employé'})

    def post(self, request, pk):
        instance = self.get_object(pk, request.user)
        form = EmployeeUpdateForm(request.POST, instance=instance, request=request)
        if form.is_valid():
            form.save()
            messages.success(request, 'Employé mis à jour.')
            return redirect('employees')
        return render(request, self.template_name, {'form': form, 'title': 'Modifier l’employé'})


@login_required
def employee_delete(request, pk):
    if not request.user.is_salon_admin:
        return redirect('dashboard')
    employee = get_object_or_404(User, pk=pk, salon=request.user.salon, role=UserRole.EMPLOYEE)
    employee.delete()
    messages.success(request, 'Employé supprimé.')
    return redirect('employees')


class AppointmentListView(EmployeeOrAdminMixin, ListView):
    model = Appointment
    template_name = 'appointments/list.html'
    context_object_name = 'appointments'

    def get_queryset(self):
        qs = Appointment.objects.filter(salon=self.request.user.salon).select_related('client', 'service', 'employee')
        if self.request.user.is_employee:
            qs = qs.filter(employee=self.request.user)
        view_mode = self.request.GET.get('view', 'day')
        anchor = self.request.GET.get('date')
        today = timezone.localdate()
        target = datetime.strptime(anchor, '%Y-%m-%d').date() if anchor else today
        if view_mode == 'week':
            start = target - timedelta(days=target.weekday())
            end = start + timedelta(days=6)
            qs = qs.filter(date__range=(start, end))
        elif view_mode == 'month':
            start = target.replace(day=1)
            end = (start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            qs = qs.filter(date__range=(start, end))
        else:
            qs = qs.filter(date=target)
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(Q(client__first_name__icontains=q) | Q(client__last_name__icontains=q) | Q(service__name__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['view_mode'] = self.request.GET.get('view', 'day')
        context['selected_date'] = self.request.GET.get('date', timezone.localdate().isoformat())
        return context


class AppointmentCreateView(AdminOnlyMixin, CreateView):
    form_class = AppointmentForm
    template_name = 'generic_form.html'
    success_url = reverse_lazy('appointments')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def form_valid(self, form):
        form.instance.salon = self.request.user.salon
        response = super().form_valid(form)
        Notification.objects.create(
            salon=self.request.user.salon,
            type='appointment_new',
            title='Nouveau rendez-vous',
            message=f'Rendez-vous créé pour {self.object.client} le {self.object.date}.',
        )
        messages.success(self.request, 'Rendez-vous ajouté avec succès.')
        return response

    def get_initial(self):
        initial = super().get_initial()
        if self.request.GET.get('client'):
            initial['client'] = self.request.GET['client']
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Nouveau rendez-vous'
        return context


class AppointmentUpdateView(AdminOnlyMixin, UpdateView):
    model = Appointment
    form_class = AppointmentForm
    template_name = 'generic_form.html'
    success_url = reverse_lazy('appointments')

    def get_queryset(self):
        return Appointment.objects.filter(salon=self.request.user.salon)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Modifier le rendez-vous'
        return context


class AppointmentDeleteView(AdminOnlyMixin, DeleteView):
    model = Appointment
    template_name = 'generic_confirm_delete.html'
    success_url = reverse_lazy('appointments')

    def get_queryset(self):
        return Appointment.objects.filter(salon=self.request.user.salon)


@login_required
def mark_appointment_completed(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk, salon=request.user.salon)
    if request.user.is_employee and appointment.employee != request.user:
        return redirect('appointments')
    appointment.status = 'completed'
    appointment.save()
    messages.success(request, 'Rendez-vous marqué comme terminé.')
    return redirect('appointments')


@login_required
def cancel_appointment(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk, salon=request.user.salon)
    if request.user.is_employee and appointment.employee != request.user:
        return redirect('appointments')
    appointment.status = 'cancelled'
    appointment.save()
    Notification.objects.create(
        salon=request.user.salon,
        type='appointment_cancelled',
        title='Rendez-vous annulé',
        message=f'Rendez-vous de {appointment.client} annulé.',
    )
    messages.success(request, 'Rendez-vous annulé.')
    return redirect('appointments')


class PaymentListView(AdminOnlyMixin, ListView):
    model = Payment
    template_name = 'payments/list.html'
    context_object_name = 'payments'

    def get_queryset(self):
        qs = Payment.objects.filter(salon=self.request.user.salon).select_related('client', 'appointment', 'employee')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(Q(client__first_name__icontains=q) | Q(client__last_name__icontains=q) | Q(notes__icontains=q))
        return qs


class PaymentCreateView(AdminOnlyMixin, CreateView):
    form_class = PaymentForm
    template_name = 'generic_form.html'
    success_url = reverse_lazy('payments')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def form_valid(self, form):
        form.instance.salon = self.request.user.salon
        response = super().form_valid(form)
        points = int(self.object.amount * self.request.user.salon.loyalty_points_per_dh)
        account, _ = LoyaltyAccount.objects.get_or_create(salon=self.request.user.salon, client=self.object.client)
        account.points_balance += points
        account.total_points_earned += points
        account.vip_status = self.object.client.total_spent >= Decimal('5000.00')
        account.save()
        LoyaltyTransaction.objects.create(
            salon=self.request.user.salon,
            loyalty_account=account,
            points=points,
            reason=f'Paiement #{self.object.id}',
        )
        Notification.objects.create(
            salon=self.request.user.salon,
            type='payment_received',
            title='Paiement reçu',
            message=f'{self.object.amount} DH encaissés pour {self.object.client}.',
        )
        messages.success(self.request, 'Paiement enregistré avec succès.')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Encaisser un paiement'
        return context


class ExpenseListView(AdminOnlyMixin, ListView):
    model = Expense
    template_name = 'expenses/list.html'
    context_object_name = 'expenses'

    def get_queryset(self):
        return Expense.objects.filter(salon=self.request.user.salon)


class ExpenseCreateView(AdminOnlyMixin, CreateView):
    form_class = ExpenseForm
    template_name = 'generic_form.html'
    success_url = reverse_lazy('expenses')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def form_valid(self, form):
        form.instance.salon = self.request.user.salon
        messages.success(self.request, 'Dépense enregistrée avec succès.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Ajouter une dépense'
        return context


class CashRegisterView(AdminOnlyMixin, TemplateView):
    template_name = 'cash/register.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        salon = self.request.user.salon
        date_param = self.request.GET.get('date')
        target_date = datetime.strptime(date_param, '%Y-%m-%d').date() if date_param else timezone.localdate()
        opening, _ = CashRegisterDay.objects.get_or_create(salon=salon, date=target_date)
        payments = Payment.objects.filter(salon=salon, date=target_date)
        expenses = Expense.objects.filter(salon=salon, date=target_date)
        tx = CashTransaction.objects.filter(salon=salon, date=target_date)
        cash_received = payments.filter(payment_method='cash').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        card_received = payments.filter(payment_method='card').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        other_received = payments.exclude(payment_method__in=['cash', 'card']).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        manual_income = tx.filter(type='income').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        manual_expense = tx.filter(type='expense').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        expense_total = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        total_revenue = cash_received + card_received + other_received + manual_income
        closing_balance = opening.opening_balance + cash_received + manual_income - expense_total - manual_expense
        context.update({
            'selected_date': target_date,
            'opening_record': opening,
            'opening_form': CashRegisterDayForm(instance=opening, request=self.request),
            'transaction_form': CashTransactionForm(request=self.request),
            'transactions': tx,
            'payments': payments,
            'expenses': expenses,
            'cash_received': cash_received,
            'card_received': card_received,
            'other_received': other_received,
            'manual_income': manual_income,
            'manual_expense': manual_expense,
            'expense_total': expense_total,
            'total_revenue': total_revenue,
            'closing_balance': closing_balance,
            'estimated_net': total_revenue - expense_total - manual_expense,
        })
        return context

    def post(self, request):
        salon = request.user.salon
        action = request.POST.get('action')
        if action == 'opening':
            instance = CashRegisterDay.objects.filter(salon=salon, date=request.POST.get('date')).first()
            form = CashRegisterDayForm(request.POST, instance=instance, request=request)
            if form.is_valid():
                obj = form.save(commit=False)
                obj.salon = salon
                obj.save()
                messages.success(request, 'Solde d’ouverture mis à jour.')
        elif action == 'transaction':
            form = CashTransactionForm(request.POST, request=request)
            if form.is_valid():
                obj = form.save(commit=False)
                obj.salon = salon
                obj.save()
                messages.success(request, 'Mouvement de caisse ajouté.')
        return redirect(f"{reverse('cash_register')}?date={request.POST.get('date', timezone.localdate().isoformat())}")


class ProductListView(AdminOnlyMixin, ListView):
    model = Product
    template_name = 'products/list.html'
    context_object_name = 'products'

    def get_queryset(self):
        qs = Product.objects.filter(salon=self.request.user.salon)
        status = self.request.GET.get('stock_status')
        if status == 'low':
            qs = qs.filter(current_stock__lte=models.F('minimum_stock'), current_stock__gt=0)
        elif status == 'out':
            qs = qs.filter(current_stock__lte=0)
        return qs


class ProductCreateView(AdminOnlyMixin, CreateView):
    form_class = ProductForm
    template_name = 'generic_form.html'
    success_url = reverse_lazy('products')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def form_valid(self, form):
        form.instance.salon = self.request.user.salon
        messages.success(self.request, 'Produit ajouté avec succès.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Ajouter un produit'
        return context


class ProductUpdateView(AdminOnlyMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = 'generic_form.html'
    success_url = reverse_lazy('products')

    def get_queryset(self):
        return Product.objects.filter(salon=self.request.user.salon)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Modifier le produit'
        return context


class ProductDeleteView(AdminOnlyMixin, DeleteView):
    model = Product
    template_name = 'generic_confirm_delete.html'
    success_url = reverse_lazy('products')

    def get_queryset(self):
        return Product.objects.filter(salon=self.request.user.salon)


class StockMovementListView(AdminOnlyMixin, ListView):
    model = StockMovement
    template_name = 'stock/list.html'
    context_object_name = 'movements'

    def get_queryset(self):
        return StockMovement.objects.filter(salon=self.request.user.salon).select_related('product')


class StockMovementCreateView(AdminOnlyMixin, CreateView):
    form_class = StockMovementForm
    template_name = 'generic_form.html'
    success_url = reverse_lazy('stock')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def form_valid(self, form):
        form.instance.salon = self.request.user.salon
        response = super().form_valid(form)
        product = self.object.product
        product.current_stock += self.object.quantity
        product.save()
        if product.current_stock <= 0:
            Notification.objects.create(salon=product.salon, type='stock_out', title='Produit épuisé', message=f'{product.name} est en rupture de stock.')
        elif product.current_stock <= product.minimum_stock:
            Notification.objects.create(salon=product.salon, type='stock_low', title='Stock faible', message=f'{product.name} est en stock faible.')
        messages.success(self.request, 'Mouvement de stock enregistré.')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Ajouter un mouvement de stock'
        return context


class PromotionListView(AdminOnlyMixin, ListView):
    model = Promotion
    template_name = 'promotions/list.html'
    context_object_name = 'promotions'

    def get_queryset(self):
        return Promotion.objects.filter(salon=self.request.user.salon).prefetch_related('services')


class PromotionCreateView(AdminOnlyMixin, CreateView):
    form_class = PromotionForm
    template_name = 'generic_form.html'
    success_url = reverse_lazy('promotions')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def form_valid(self, form):
        form.instance.salon = self.request.user.salon
        messages.success(self.request, 'Promotion ajoutée avec succès.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Ajouter une promotion'
        return context


class PromotionUpdateView(AdminOnlyMixin, UpdateView):
    model = Promotion
    form_class = PromotionForm
    template_name = 'generic_form.html'
    success_url = reverse_lazy('promotions')

    def get_queryset(self):
        return Promotion.objects.filter(salon=self.request.user.salon)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Modifier la promotion'
        return context


class PromotionDeleteView(AdminOnlyMixin, DeleteView):
    model = Promotion
    template_name = 'generic_confirm_delete.html'
    success_url = reverse_lazy('promotions')

    def get_queryset(self):
        return Promotion.objects.filter(salon=self.request.user.salon)


class ReviewListView(EmployeeOrAdminMixin, ListView):
    model = Review
    template_name = 'reviews/list.html'
    context_object_name = 'reviews'

    def get_queryset(self):
        return Review.objects.filter(salon=self.request.user.salon).select_related('client', 'service')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        stats = self.get_queryset().aggregate(avg=Avg('rating'), total=Count('id'))
        context['avg_rating'] = stats['avg'] or 0
        context['review_count'] = stats['total'] or 0
        return context


class ReviewCreateView(AdminOnlyMixin, CreateView):
    form_class = ReviewForm
    template_name = 'generic_form.html'
    success_url = reverse_lazy('reviews')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def form_valid(self, form):
        form.instance.salon = self.request.user.salon
        messages.success(self.request, 'Avis enregistré avec succès.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Ajouter un avis'
        return context


class NotificationListView(EmployeeOrAdminMixin, ListView):
    model = Notification
    template_name = 'notifications/list.html'
    context_object_name = 'notifications'

    def get_queryset(self):
        return Notification.objects.filter(salon=self.request.user.salon)


@login_required
def mark_notification_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, salon=request.user.salon)
    notification.is_read = True
    notification.save()
    return redirect('notifications')


class ReportsView(AdminOnlyMixin, TemplateView):
    template_name = 'reports/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        salon = self.request.user.salon
        start_param = self.request.GET.get('start')
        end_param = self.request.GET.get('end')
        today = timezone.localdate()
        start = datetime.strptime(start_param, '%Y-%m-%d').date() if start_param else today.replace(day=1)
        end = datetime.strptime(end_param, '%Y-%m-%d').date() if end_param else today
        appointments = Appointment.objects.filter(salon=salon, date__range=(start, end))
        payments = Payment.objects.filter(salon=salon, date__range=(start, end))
        expenses = Expense.objects.filter(salon=salon, date__range=(start, end))
        revenue_total = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        expense_total = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        new_clients = Client.objects.filter(salon=salon, created_at__date__range=(start, end)).count()
        returning_clients = Client.objects.filter(salon=salon, appointments__date__range=(start, end), appointments__status='completed').annotate(v=Count('appointments')).filter(v__gt=1).distinct().count()
        inactive_clients = Client.objects.filter(salon=salon).exclude(appointments__date__gte=today - timedelta(days=getattr(settings, 'INACTIVITY_DAYS_DEFAULT', 60))).count()
        vip_clients = Client.objects.filter(salon=salon, is_vip=True).count()
        service_stats = list(appointments.values('service__name').annotate(total=Count('id'), revenue=Sum('price')).order_by('-total'))
        employee_stats = list(appointments.values('employee__first_name', 'employee__last_name').annotate(total=Count('id'), revenue=Sum('price')).order_by('-revenue'))
        payment_stats = list(payments.values('payment_method').annotate(total=Sum('amount')).order_by('payment_method'))
        total_services = sum(item['total'] for item in service_stats) or 1
        distribution = [
            {'name': item['service__name'], 'percentage': round((item['total'] / total_services) * 100, 2), 'count': item['total']}
            for item in service_stats
        ]
        context.update({
            'start': start,
            'end': end,
            'revenue_total': revenue_total,
            'expense_total': expense_total,
            'estimated_net': revenue_total - expense_total,
            'new_clients': new_clients,
            'returning_clients': returning_clients,
            'inactive_clients': inactive_clients,
            'vip_clients': vip_clients,
            'service_stats': service_stats,
            'employee_stats': employee_stats,
            'payment_stats': payment_stats,
            'distribution': distribution,
            'distribution_json': json.dumps(distribution),
            'payment_json': json.dumps(payment_stats),
            'employee_json': json.dumps(employee_stats),
        })
        return context


class SalonSettingsView(AdminOnlyMixin, UpdateView):
    model = Salon
    form_class = SalonSettingsForm
    template_name = 'generic_form.html'
    success_url = reverse_lazy('settings')

    def get_object(self):
        return self.request.user.salon

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Paramètres du salon'
        return context
