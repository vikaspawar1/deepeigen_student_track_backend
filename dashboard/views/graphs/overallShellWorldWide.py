from django.http import JsonResponse
from course.models import Order
from django.db.models import Count
import logging

logger = logging.getLogger(__name__)

def overall_shell_world_wide_api(request):
    """
    API endpoint to retrieve the lifetime geographical distribution of orders.

    Calculates the breakdown of all successfully placed orders between 
    India and other global regions.

    Args:
        request (HttpRequest): The user request.

    Returns:
        JsonResponse: Global distribution statistics and percentages.
    """
    try:
        # Get all successful orders
        orders = Order.objects.filter(is_ordered=True)

        total_orders = orders.count()
        if total_orders == 0:
            return JsonResponse({
                'message': 'No sales data available',
                'data': {
                    'india': 0,
                    'other_country': 0,
                    'empty': 0
                }
            })

        # Count per country category
        india_count = orders.filter(country__iexact="india").count()
        other_country_count = orders.exclude(country__iexact="india").exclude(country="").count()
        empty_count = orders.filter(country="").count()

        # Calculate percentages
        india_percent = round((india_count / total_orders) * 100, 2)
        other_country_percent = round((other_country_count / total_orders) * 100, 2)
        empty_percent = round((empty_count / total_orders) * 100, 2)

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
        logger.exception('Error in overall_shell_world_wide')
        return JsonResponse({'error': 'Something went wrong.'}, status=500)
