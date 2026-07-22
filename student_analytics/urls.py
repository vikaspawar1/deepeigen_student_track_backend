from django.urls import path
from .views import (
    DELSDetailAPIView, DELSBreakdownAPIView, EnrollmentMetricsAPIView,
    FollowThroughAPIView, AvgMetricsAPIView,
    PerformanceAPIView,
)

urlpatterns = [
    # Single consolidated endpoint — all dashboard data in one request
    path('performance/', PerformanceAPIView.as_view(), name='student-performance'),
    # DELS-only API surface (frontend uses only these endpoints)
    path('users/<str:user_id>/dels/', DELSDetailAPIView.as_view(), name='dels-detail'),
    path('users/<str:user_id>/dels/breakdown/', DELSBreakdownAPIView.as_view(), name='dels-breakdown'),
    path('enrollments/<int:enrollment_id>/metrics/', EnrollmentMetricsAPIView.as_view(), name='enrollment-metrics'),
    path('users/<str:user_id>/follow-through/', FollowThroughAPIView.as_view(), name='follow-through'),
    # Averaged metrics across all enrollments (ASR, ATS, AQS, PALC, ECI)
    path('users/<str:user_id>/avg-metrics/', AvgMetricsAPIView.as_view(), name='avg-metrics'),
]