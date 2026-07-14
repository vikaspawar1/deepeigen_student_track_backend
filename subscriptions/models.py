"""
Models for the subscription application.

Defines the structure for subscription plans, category-based access control,
tracking active user subscriptions, and subscription-specific invoices.
"""
from django.db import models
from accounts.models import Account
from datetime import datetime


class SubscriptionPlan(models.Model):
    """!
    @brief Defines a high-level subscription tier (Basic, Standard, Premium) and its associated duration.
    @details Tracks regional pricing for both Indian and International users to support localized billing.
    """

    PLAN_TYPES = (
        ("BASIC", "Basic"),
        ("STANDARD", "Standard"),
        ("PREMIUM", "Premium"),
    )

    DURATION_TYPES = (
        ("MONTHLY", "Monthly"),
        ("FOUR_MONTH", "4 Months"),
        ("YEARLY", "Yearly"),
    )

    plan_type = models.CharField(
        max_length=20,
        choices=PLAN_TYPES
    )

    duration_type = models.CharField(
        max_length=20,
        choices=DURATION_TYPES
    )

    duration_days = models.IntegerField()

    indian_price = models.FloatField()
    foreign_price = models.FloatField()

    created_at = models.DateTimeField(default=datetime.now)

    def __str__(self):
        return f"{self.plan_type} - {self.duration_type}"


class PlanCategoryAccess(models.Model):
    """!
    @brief Defines the cross-reference mapping between subscription plans and course categories.
    @details Determines which course categories (IA, IB, II) are authorized for access based on the user's specific plan type.
    """

    CATEGORY_CHOICES = (
        ("IA", "IA"),
        ("IB", "IB"),
        ("II", "II"),
    )

    plan_type = models.CharField(
        max_length=20,
        choices=SubscriptionPlan.PLAN_TYPES
    )

    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES
    )

    def __str__(self):
        return f"{self.plan_type} -> {self.category}"


class UserSubscription(models.Model):
    """!
    @brief Records and tracks a specific user's active subscription status and temporal validity.
    @details Maps a user to a subscription plan and a concrete payment record.
    """

    user = models.ForeignKey(
        Account,
        on_delete=models.CASCADE
    )

    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.CASCADE
    )

    payment = models.ForeignKey(
        "course.Payment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    start_date = models.DateTimeField(default=datetime.now)
    end_date = models.DateTimeField()

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(default=datetime.now)

    def __str__(self):
        return f"{self.user.email} -> {self.plan.plan_type}"

class SubscriptionInvoice(models.Model):
    """!
    @brief Represents a finalized financial record link for a specific subscription purchase.
    @details Associates a user's subscription with a payment record and a physicsal PDF invoice file.
    """
    subscription = models.ForeignKey(UserSubscription, on_delete=models.CASCADE)
    payment = models.ForeignKey("course.Payment", on_delete=models.CASCADE)
    serial_no = models.CharField(max_length=500, blank=True, null=True)
    invoice = models.FileField(upload_to="Subscription_Invoices/", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Invoice {self.serial_no} for {self.subscription.user.email}"