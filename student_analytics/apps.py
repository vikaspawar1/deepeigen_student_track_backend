from django.apps import AppConfig


class StudentAnalyticsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'student_analytics'

    def ready(self):
        try:
            import student_analytics.signals  # noqa: F401
        except ImportError:
            pass

