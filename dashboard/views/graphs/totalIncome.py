from django.http import JsonResponse
from course.models import Order
import logging
import json
from django.db.models import Sum

from django.utils.dateparse import parse_date
from datetime import datetime

logger = logging.getLogger(__name__)  # Optional: for logging errors in production


# enrolled user api- getting all the enrolled users
def graph_total_income_api(request):
    """
    API endpoint to retrieve the total financial turnover for a given period.

    Aggregates income from all successful 'is_ordered' transactions.

    Args:
        request (HttpRequest): Contains 'start_date' and 'end_date' (YYYY-MM-DD).

    Returns:
        JsonResponse: Aggregated income amount and total order count.
    """
    try:
        if request.method == 'GET':
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')
            
            if not start_date or not end_date:
                return JsonResponse({'error': 'From date and to date are required.'}, status=400)
            
            start_datetime = datetime.strptime(start_date + 'T00:00:00Z', '%Y-%m-%dT%H:%M:%SZ')
            end_datetime = datetime.strptime(end_date + 'T23:59:59Z', '%Y-%m-%dT%H:%M:%SZ')
            
            # Filter orders with is_ordered=True
            orders = Order.objects.filter(is_ordered=True, created_at__range=(start_datetime, end_datetime))

            # Calculate total income (sum of total_amount)
            total_income = orders.aggregate(income=Sum('total_amount'))['income'] or 0
            total_orders = orders.count()

            return JsonResponse({
                'total_orders': total_orders,
                'total_income': round(total_income, 2)  # Rounded for display
            }, status=200)
        
        return JsonResponse({'error': 'Only GET method is allowed.'}, status=405)

    
    except Exception as e:
        # Optional: log unexpected errors
        logger.exception('Unhandled error in enrolled_users_api view')
        
        return JsonResponse({
            'error': 'Something went wronge. Please try again later'
        }, status=500)
        
    
    