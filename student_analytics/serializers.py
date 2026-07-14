from rest_framework import serializers
from .models import (
    StudentAnalytics, StudentCourseAnalytics, LectureActivity,
    AssignmentActivity, AssessmentActivity,
    DailyLearningActivity
)

class StudentAnalyticsSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentAnalytics
        fields = '__all__'

class StudentCourseAnalyticsSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentCourseAnalytics
        fields = '__all__'

class LectureActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = LectureActivity
        fields = '__all__'

class AssignmentActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = AssignmentActivity
        fields = '__all__'

class AssessmentActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = AssessmentActivity
        fields = '__all__'

class DailyLearningActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyLearningActivity
        fields = '__all__'
