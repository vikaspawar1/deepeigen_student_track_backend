from django.http import JsonResponse
from django.db.models import Count
from course.models import EnrolledUser
import logging

logger = logging.getLogger(__name__)

def most_selling_courses_api(request):
    """
    API endpoint to retrieve enrollment rankings for active courses.

    Excludes legacy/discontinued courses and returns a list of courses 
    ranked by total quantity sold.

    Args:
        request (HttpRequest): The user request.

    Returns:
        JsonResponse: Ranked list of course sales data.
    """
    try:
        # Titles of courses you want to exclude (discontinued)
        excluded_titles = [
            "RO-2.0X: Introduction to Robotics Perception and Visual Navigation",
            "RO-1.0X: Introduction to Robotics and Visual Navigation"
        ]

        # Count how many users are enrolled per course (excluding discontinued ones)
        course_counts = EnrolledUser.objects.filter(enrolled=True)\
            .exclude(course__title__in=excluded_titles)\
            .values('course__id', 'course__title')\
            .annotate(total_enrolled=Count('id'))\
            .order_by('-total_enrolled')
            
        # Format the response
        data = [
            {
                'course_id': item['course__id'],
                'course_name': item['course__title'],
                'total_enrolled': item['total_enrolled']
            }
            for item in course_counts
        ]
        
        return JsonResponse({'most_selling_course': data}, safe=False)

    except Exception as e:
        logger.exception('Unhandled error in most_selling_courses_api')
        return JsonResponse({'error': 'Something went wrong. Please try again later.'}, status=500)
