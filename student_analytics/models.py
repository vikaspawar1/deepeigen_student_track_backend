from django.db import models
from django.conf import settings
from course.models import Course, Module, Video, Assignment

class StudentAnalytics(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='student_analytics')
    total_courses_purchased = models.IntegerField(default=0)
    total_courses_completed = models.IntegerField(default=0)
    total_learning_hours = models.FloatField(default=0.0)
    total_study_minutes = models.FloatField(default=0.0)
    total_assignment_score = models.FloatField(default=0.0)
    average_assignment_score = models.FloatField(default=0.0)
    total_assessment_score = models.FloatField(default=0.0)
    average_assessment_score = models.FloatField(default=0.0)
    current_learning_streak = models.IntegerField(default=0)
    longest_learning_streak = models.IntegerField(default=0)
    total_login_days = models.IntegerField(default=0)
    total_modules_completed = models.IntegerField(default=0)
    total_lectures_completed = models.IntegerField(default=0)
    total_assignments_completed = models.IntegerField(default=0)
    total_assessments_completed = models.IntegerField(default=0)
    average_course_completion_days = models.FloatField(default=0.0)
    overall_performance_score = models.FloatField(default=0.0)
    internship_eligible = models.BooleanField(default=False)
    student_rank = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} Analytics"

class StudentCourseAnalytics(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='course_analytics')
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    purchase_date = models.DateTimeField(null=True, blank=True)
    access_start_date = models.DateTimeField(null=True, blank=True)
    expected_course_duration = models.IntegerField(default=0, help_text="Duration in days")
    expected_completion_date = models.DateTimeField(null=True, blank=True)
    actual_completion_date = models.DateTimeField(null=True, blank=True)
    completion_days = models.IntegerField(default=0)
    completion_percentage = models.FloatField(default=0.0)
    course_status = models.CharField(max_length=50, default='Not Started')
    total_modules = models.IntegerField(default=0)
    completed_modules = models.IntegerField(default=0)
    total_lectures = models.IntegerField(default=0)
    completed_lectures = models.IntegerField(default=0)
    total_assignments = models.IntegerField(default=0)
    completed_assignments = models.IntegerField(default=0)
    total_assessments = models.IntegerField(default=0)
    completed_assessments = models.IntegerField(default=0)
    assignment_average = models.FloatField(default=0.0)
    assessment_average = models.FloatField(default=0.0)
    study_minutes = models.FloatField(default=0.0)
    study_hours = models.FloatField(default=0.0)
    discussion_posts = models.IntegerField(default=0)
    discussion_replies = models.IntegerField(default=0)
    login_days = models.IntegerField(default=0)
    learning_streak = models.IntegerField(default=0)
    course_performance_score = models.FloatField(default=0.0)

    class Meta:
        unique_together = ('user', 'course')

class LectureActivity(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    lecture = models.ForeignKey(Video, on_delete=models.CASCADE)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    watch_duration = models.FloatField(default=0.0, help_text="Duration in seconds")
    completion_percentage = models.FloatField(default=0.0)
    is_completed = models.BooleanField(default=False)

# class ModuleActivity(models.Model):
#     user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
#     course = models.ForeignKey(Course, on_delete=models.CASCADE)
#     module = models.ForeignKey(Module, on_delete=models.CASCADE)
#     started_at = models.DateTimeField(null=True, blank=True)
#     completed_at = models.DateTimeField(null=True, blank=True)
#     completion_time = models.FloatField(default=0.0, help_text="Time taken in minutes")


    

class AssignmentActivity(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE)
    assignment_download_time = models.DateTimeField(null=True, blank=True)
    assignment_submission_time = models.DateTimeField(null=True, blank=True)
    admin_review_time = models.DateTimeField(null=True, blank=True)
    admin_reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_assignments')
    marks = models.FloatField(default=0.0, help_text="0-100")
    status = models.CharField(max_length=50, default='Pending')
    feedback = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('user', 'course', 'assignment')
        verbose_name = "Student Assignment Submission"
        verbose_name_plural = "Student Assignment Submissions"




class AssessmentActivity(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    assessment = models.CharField(max_length=255, default='Unknown Assessment')
    started_time = models.DateTimeField(null=True, blank=True)
    completed_time = models.DateTimeField(null=True, blank=True)
    score = models.FloatField(default=0.0)
    passing_status = models.BooleanField(default=False)
    time_taken = models.FloatField(default=0.0, help_text="Time taken in minutes")



class DailyLearningActivity(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date = models.DateField()
    study_time = models.FloatField(default=0.0, help_text="In minutes")
    lectures_completed = models.IntegerField(default=0)
    modules_completed = models.IntegerField(default=0)
    assignments_submitted = models.IntegerField(default=0)
    assessments_completed = models.IntegerField(default=0)
    discussion_posts = models.IntegerField(default=0)
    discussion_replies = models.IntegerField(default=0)
    login_count = models.IntegerField(default=0)
    daily_score = models.FloatField(default=0.0)

    class Meta:
        unique_together = ('user', 'date')
