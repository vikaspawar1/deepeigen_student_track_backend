from django.urls import path
from .views import (
    OverviewAPIView, CourseAnalyticsAPIView, ActivityAPIView,
    LeaderboardAPIView, PerformanceAPIView, StreakAPIView,
    HistoryAPIView
)

urlpatterns = [
    path('overview/', OverviewAPIView.as_view(), name='analytics-overview'),
    path('course/<int:course_id>/', CourseAnalyticsAPIView.as_view(), name='analytics-course'),
    path('activity/', ActivityAPIView.as_view(), name='analytics-activity'),
    path('leaderboard/', LeaderboardAPIView.as_view(), name='analytics-leaderboard'),
    path('performance/', PerformanceAPIView.as_view(), name='analytics-performance'),
    path('streak/', StreakAPIView.as_view(), name='analytics-streak'),
    path('history/', HistoryAPIView.as_view(), name='analytics-history'),
]
