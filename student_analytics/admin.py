from django.contrib import admin

from .models import (
    StudentAnalytics,
    StudentCourseAnalytics,
    LectureActivity,
    AssignmentActivity,

    DailyLearningActivity,
)


@admin.register(StudentAnalytics)
class StudentAnalyticsAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'total_courses_purchased',
        'total_courses_completed',
        'overall_performance_score',
        'internship_eligible',
    )
    search_fields = ('user__email', 'user__first_name', 'user__last_name')


@admin.register(StudentCourseAnalytics)
class StudentCourseAnalyticsAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'course',
        'completion_percentage',
        'course_status',
        'course_performance_score',
    )
    search_fields = ('user__email', 'course__title')


@admin.register(LectureActivity)
class LectureActivityAdmin(admin.ModelAdmin):
    list_display = ('user', 'course', 'lecture', 'is_completed', 'completed_at')
    search_fields = ('user__email', 'course__title', 'lecture__title')


@admin.register(AssignmentActivity)
class AssignmentActivityAdmin(admin.ModelAdmin):
    list_display = ('user', 'course', 'assignment', 'marks', 'status', 'assignment_submission_time', 'admin_review_time')
    list_filter = ('status', 'course')
    search_fields = ('user__email', 'course__title', 'assignment__name')
    readonly_fields = ('user', 'course', 'assignment', 'assignment_submission_time', 'assignment_download_time')
    fieldsets = (
        ('Student Info', {'fields': ('user', 'course', 'assignment')}),
        ('Submission', {'fields': ('assignment_submission_time', 'assignment_download_time')}),
        ('Grading', {'fields': ('marks', 'status', 'admin_reviewer', 'admin_review_time', 'feedback')}),
    )


@admin.register(DailyLearningActivity)
class DailyLearningActivityAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'study_time', 'lectures_completed', 'assignments_submitted')
    search_fields = ('user__email',)
