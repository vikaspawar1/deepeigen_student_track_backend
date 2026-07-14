from django.http import JsonResponse
from datetime import datetime
from course.models import Order
import logging

logger = logging.getLogger(__name__)

def monthly_shell_world_wide_api(request):
    """
    API endpoint to retrieve regional order distribution within a date range.

    Calculates the count and percentage of orders from India versus 
    other countries/unspecified locations.

    Args:
        request (HttpRequest): Contains 'start_date' and 'end_date' (YYYY-MM-DD).

    Returns:
        JsonResponse: Aggregated regional statistics.
    """
    try:
        if request.method != 'GET':
            return JsonResponse({'error': 'Only GET method is allowed.'}, status=405)

        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        if not start_date or not end_date:
            return JsonResponse({'error': 'From date and to date are required.'}, status=400)

        start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
        end_datetime = datetime.strptime(end_date, '%Y-%m-%d')

        orders = Order.objects.filter(is_ordered=True, created_at__range=(start_datetime, end_datetime))

        total_orders = orders.count()

        # Count per country category
        india_count = orders.filter(country__iexact="india").count()
        other_country_count = orders.exclude(country__iexact="india").exclude(country="").count()
        empty_count = orders.filter(country="").count()

        # Calculate percentages
        india_percent = round((india_count / total_orders) * 100, 2) if total_orders else 0
        other_country_percent = round((other_country_count / total_orders) * 100, 2) if total_orders else 0
        empty_percent = round((empty_count / total_orders) * 100, 2) if total_orders else 0

        data = {
            'total_orders': total_orders,
            'india': {
                'count': india_count,
                'percentage': india_percent
            },
            'other_country': {
                'count': other_country_count,
                'percentage': other_country_percent
            },
            'empty': {
                'count': empty_count,
                'percentage': empty_percent
            }
        }

        return JsonResponse(data, status=200)

    except Exception as e:
        logger.exception("Error in monthly_shell_world_wide_api")
        return JsonResponse({'error': 'Something went wrong.'}, status=500)
