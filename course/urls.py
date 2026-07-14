"""
URL configuration for the course application.

Defines routes for course listing, detailed viewing, enrollment, 
payment processing, and student progress tracking (videos and assignments).
"""
from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.courses, name='courses'), #done test

    path('<int:id>/<str:course_url>', views.course_detail, name="course_detail"), #done test

    path('<int:id>/<str:course_url>/overview', views.course_overview, name="course_overview"), #done test

    path('<int:id>/<str:course_url>/enroll', views.course_enrollment, name="course_enrollment"), #done test

    path('<int:id>/<str:course_url>/place_order', views.place_order, name="place_order"), #done test

    path('<int:id>/<str:course_url>/cart_summary', views.cart_summary, name="cart_summary"), #done test


    path('<int:id>/<str:course_url>/payment_done/<str:order_id>', views.payment_done, name="payment_done"),#done test

    
    path('<int:id>/<str:course_url>/payment_success/<str:order_id>', views.payment_success, name="payment_success"),#done test

    path('<int:id>/<str:course_url>/<str:section_url>/<int:assignment_id>', views.course_progress, name="course_progress"),#done test

    path('<int:id>/<str:course_url>/optional_assignments', views.optional_assignments, name="optional_assignments"),#done test

    # Must be before <section_url> pattern to avoid matching "assignments" as a section
    path('<int:id>/<str:course_url>/assignments', views.course_assignments, name="course_assignments"),#new endpoint for all assignments

    path('<int:id>/<str:course_url>/<str:section_url>', views.course_section, name="course_section"),#done test

    path('payment_failed/<str:order_id>', views.payment_failed, name="payment_failed"),#done test

    path('manual_registration', views.manual_user_registration, name='manual_registration'),#done test

    path('place_order_mannualy', views.place_order_manually, name="place_order_mannualy"),#done test

    path('get_orders', views.get_orders, name='get_orders'),#done test

    path('payment/', views.payment_installment, name='payment_installment'),#API for installment payment - added 10 Feb 2026

    path('payment_verify/', views.payment_verify, name='payment_verify'),#API for payment verification - added 10 Feb 2026

    path('<int:course_id>/sections/accessible/', views.get_accessible_sections, name='get_accessible_sections'),#API for progressive section access - added 23 Feb 2026

      


    #   on feb14 
    # Protected PDF download endpoint - added 12 Feb 2026
    path('<int:id>/<str:course_url>/assignments/<int:assignment_id>/pdf', views.download_assignment_pdf, name='download_assignment_pdf'),

    # Save video progress endpoint - added to track recent watch
    path('save-video-progress/', views.save_video_progress, name='save_video_progress'),
    
    # Get video progress endpoint - to load completion status on page load 14 feb 2026
    path('<int:course_id>/get-video-progress/', views.get_video_progress, name='get_video_progress'),
    
    # Custom Plan - Get proportional assessments based on selected lectures
    # Formula: assessment_count = ceil((selected_lectures / total_lectures) * total_assessments)
    path('<int:id>/<str:course_url>/custom-plan-assignments/', views.custom_plan_assignments, name='custom_plan_assignments'),
]
