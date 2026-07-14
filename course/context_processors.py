"""
Context processors for the course application.

Provides global template variables related to courses, enabling featured
course listings to be accessible across all templates.
"""
from .models import Course, EnrolledUser

def course_list(request):
    """
    Template context processor that adds a list of featured courses to the context.

    Args:
        request (HttpRequest): The incoming request.

    Returns:
        dict: A dictionary containing the 'courses_list' queryset.
    """
    courses_list = Course.objects.order_by('id').filter(is_featured=True)
    return dict(courses_list=courses_list)
