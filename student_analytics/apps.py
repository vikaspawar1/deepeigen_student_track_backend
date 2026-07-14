from django.apps import AppConfig


class StudentAnalyticsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'student_analytics'

    def ready(self):
        import student_analytics.signals
