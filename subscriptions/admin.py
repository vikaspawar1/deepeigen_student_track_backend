from django.contrib import admin
from .models import SubscriptionPlan, PlanCategoryAccess, UserSubscription, SubscriptionInvoice

admin.site.register(SubscriptionPlan)
admin.site.register(PlanCategoryAccess)
admin.site.register(UserSubscription)
admin.site.register(SubscriptionInvoice)