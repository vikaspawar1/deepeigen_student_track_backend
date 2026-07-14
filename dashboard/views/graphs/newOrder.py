from django.http import JsonResponse
from course.models import Order
import logging
import json

from django.utils.dateparse import parse_date
from datetime import datetime

logger = logging.getLogger(__name__)  # Optional: for logging errors in production


# enrolled user api- getting all the enrolled users
def graph_new_order_api(request):
    """
    API endpoint to retrieve order records within a specific date range.

    Used for generating visualization of order volume trends.

    Args:
        request (HttpRequest): Contains 'start_date' and 'end_date' (YYYY-MM-DD).

    Returns:
        JsonResponse: List of raw order records or error message.
    """
    try:
        if request.method == 'GET':
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')
            
            if not start_date or not end_date:
                return JsonResponse({'error': 'From date and to date are required.'}, status=400)
            
            start_datetime = datetime.strptime(start_date + 'T00:00:00Z', '%Y-%m-%dT%H:%M:%SZ')
            end_datetime = datetime.strptime(end_date + 'T23:59:59Z', '%Y-%m-%dT%H:%M:%SZ')
            
            users = Order.objects.filter(created_at__range=(start_datetime, end_datetime))
            
            data = list(users.values())
            return JsonResponse(data, safe=False)
        
        return JsonResponse({'error': 'Only GET method is allowed.'}, status=405)

    
    except Exception as e:
        # Optional: log unexpected errors
        logger.exception('Unhandled error in enrolled_users_api view')
        
        return JsonResponse({
            'error': 'Something went wronge. Please try again later'
        }, status=500)
        
    
    