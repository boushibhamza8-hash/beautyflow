from django.contrib import admin
from .models import (
    Appointment, CashRegisterDay, CashTransaction, Client, EmployeeProfile, Expense,
    LoyaltyAccount, LoyaltyTransaction, Notification, Payment, Product, Promotion,
    Review, Salon, SalonMembership, Service, StockMovement, Subscription, SubscriptionPlan
)

admin.site.register([
    Salon, SubscriptionPlan, Subscription, SalonMembership, Client, Service, EmployeeProfile,
    Appointment, Payment, CashRegisterDay, CashTransaction, Expense, Product, StockMovement,
    Promotion, LoyaltyAccount, LoyaltyTransaction, Review, Notification
])
