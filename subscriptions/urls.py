from django.urls import path
from . import views

urlpatterns = [

    path("plans/", views.get_subscription_plans, name="subscription_plans"),

    path(
        "plan-details/<str:plan_type>/<str:duration>/",
        views.plan_details,
        name="plan_details"
    ),
    path("place-order/", views.subscription_place_order, name="subscription_place_order"),
    path("payment-done/<str:order_id>/", views.subscription_payment_done, name="subscription_payment_done"),
    path("invoices/", views.invoice_list, name="subscription_invoices"),
    path("invoice/<str:payment_id>/download/", views.download_invoice, name="subscription_download_invoice"),
    path("accessed-courses/", views.accessed_courses, name="accessed_courses"),

]