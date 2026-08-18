from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path
from accounts.forms import LoginForm
from appcore import views

urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('', views.HomeRedirectView.as_view(), name='home'),
    path('login/', auth_views.LoginView.as_view(template_name='auth/login.html', authentication_form=LoginForm), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('password-reset/', auth_views.PasswordResetView.as_view(template_name='auth/password_reset.html'), name='password_reset'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('platform/', views.PlatformDashboardView.as_view(), name='platform_dashboard'),
    path('platform/salons/new/', views.SalonCreateView.as_view(), name='salon_create'),
    path('platform/salons/<int:pk>/edit/', views.SalonUpdateView.as_view(), name='salon_update'),
    path('platform/salons/<int:pk>/toggle/', views.toggle_salon_status, name='salon_toggle'),

    path('clients/', views.ClientListView.as_view(), name='clients'),
    path('clients/new/', views.ClientCreateView.as_view(), name='client_create'),
    path('clients/<int:pk>/', views.ClientDetailView.as_view(), name='client_detail'),
    path('clients/<int:pk>/edit/', views.ClientUpdateView.as_view(), name='client_update'),
    path('clients/<int:pk>/delete/', views.ClientDeleteView.as_view(), name='client_delete'),

    path('services/', views.ServiceListView.as_view(), name='services'),
    path('services/new/', views.ServiceCreateView.as_view(), name='service_create'),
    path('services/<int:pk>/edit/', views.ServiceUpdateView.as_view(), name='service_update'),
    path('services/<int:pk>/delete/', views.ServiceDeleteView.as_view(), name='service_delete'),

    path('employees/', views.EmployeeListView.as_view(), name='employees'),
    path('employees/new/', views.EmployeeCreateView.as_view(), name='employee_create'),
    path('employees/<int:pk>/edit/', views.EmployeeUpdateView.as_view(), name='employee_update'),
    path('employees/<int:pk>/delete/', views.employee_delete, name='employee_delete'),

    path('appointments/', views.AppointmentListView.as_view(), name='appointments'),
    path('appointments/new/', views.AppointmentCreateView.as_view(), name='appointment_create'),
    path('appointments/<int:pk>/edit/', views.AppointmentUpdateView.as_view(), name='appointment_update'),
    path('appointments/<int:pk>/delete/', views.AppointmentDeleteView.as_view(), name='appointment_delete'),
    path('appointments/<int:pk>/complete/', views.mark_appointment_completed, name='appointment_complete'),
    path('appointments/<int:pk>/cancel/', views.cancel_appointment, name='appointment_cancel'),

    path('payments/', views.PaymentListView.as_view(), name='payments'),
    path('payments/new/', views.PaymentCreateView.as_view(), name='payment_create'),
    path('expenses/', views.ExpenseListView.as_view(), name='expenses'),
    path('expenses/new/', views.ExpenseCreateView.as_view(), name='expense_create'),
    path('cash-register/', views.CashRegisterView.as_view(), name='cash_register'),

    path('products/', views.ProductListView.as_view(), name='products'),
    path('products/new/', views.ProductCreateView.as_view(), name='product_create'),
    path('products/<int:pk>/edit/', views.ProductUpdateView.as_view(), name='product_update'),
    path('products/<int:pk>/delete/', views.ProductDeleteView.as_view(), name='product_delete'),
    path('stock/', views.StockMovementListView.as_view(), name='stock'),
    path('stock/new/', views.StockMovementCreateView.as_view(), name='stock_create'),

    path('reports/', views.ReportsView.as_view(), name='reports'),
    path('promotions/', views.PromotionListView.as_view(), name='promotions'),
    path('promotions/new/', views.PromotionCreateView.as_view(), name='promotion_create'),
    path('promotions/<int:pk>/edit/', views.PromotionUpdateView.as_view(), name='promotion_update'),
    path('promotions/<int:pk>/delete/', views.PromotionDeleteView.as_view(), name='promotion_delete'),
    path('reviews/', views.ReviewListView.as_view(), name='reviews'),
    path('reviews/new/', views.ReviewCreateView.as_view(), name='review_create'),
    path('notifications/', views.NotificationListView.as_view(), name='notifications'),
    path('notifications/<int:pk>/read/', views.mark_notification_read, name='notification_read'),
    path('settings/', views.SalonSettingsView.as_view(), name='settings'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
