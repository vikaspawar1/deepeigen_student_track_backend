from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse
from course.models import OverallProgress
import logging
import json

logger = logging.getLogger(__name__)  # Optional: for logging errors in production
  

# Overall Progress api
def overallProgress_api(request):
    """!
    @brief Administrative API endpoint to audit the academic progress of all users.
    @details Consolidates completion metrics across all courses for high-level student 
             tracking and performance analytics.

    @param request (HttpRequest) DRF/Django Request with 'page' and 'limit' query params.

    @return JsonResponse Paginated collection of student progress records (200).
    """
    try:
        # Get query parameters with defaults
        try:
            page = int(request.GET.get('page', 1))
            if page < 1:
                raise ValueError("Page number must be >= 1")
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Invalid page number'}, status=400)
        
        try:
            limit = int(request.GET.get('limit', 10))
            if limit < 1:
                raise ValueError("Limit must be >= 1")
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Invalid limit value'}, status=400)
        
        overallProgress = OverallProgress.objects.all().order_by('-created_at')
        
        # Paginate enrolled users
        paginator = Paginator(overallProgress, limit)
        
        try:
            overallProgress_page = paginator.page(page)
        except PageNotAnInteger:
            return JsonResponse({ 'error': 'Page is not an integer'}, status=400)
        except EmptyPage:
            return JsonResponse({'error': 'Page out of range', 'total_pages': paginator.num_pages}, status=404)
        
        overallProgress_data = []
        
        for eu in overallProgress_page.object_list:
            overallProgress_data.append({
                'id': eu.id,
                'user_email': eu.user.email,
                'course_title': eu.course.title,
                'progress': eu.progress,
                'created_at': eu.created_at,
            })
            
        # print("overallProgress_data:", json.dumps(overallProgress_data, indent=4, default=str))
        return JsonResponse({
            'overallProgress': overallProgress_data,
            'total_pages': paginator.num_pages,
            'current_page': page
        }, status=200)
    except Exception as e:
        # Optional: log unexpected errors
        logger.exception('unhandled error in assignment_api view')
        
        return JsonResponse({
            'error': 'Something went wrong. Please try again later'         
        }, status=500)
        
        
