from django.http import JsonResponse
from django.db.models import Sum, Count
from django.db.models.functions import TruncYear
from course.models import Order
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

def five_year_sales_summary_api(request):
    """
    API endpoint to retrieve a 5-year yearly sales and course enrollment summary.

    Aggregates revenue and unique course counts per year for orders marked as 
    purchased within the last five years.

    Args:
        request (HttpRequest): The user request.

    Returns:
        JsonResponse: List of yearly sales data points.
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=5*365)

        sales_summary = (
            Order.objects.filter(is_ordered=True, created_at__range=(start_date, end_date))
            .annotate(year=TruncYear('created_at'))
            .values('year')
            .annotate(
                total_revenue=Sum('total_amount'),
                total_courses=Count('course', distinct=True)
            )
            .order_by('year')
        )

        data = [
            {
                'year': item['year'].year,
                'total_revenue': item['total_revenue'],
                'total_courses': item['total_courses']
            }
            for item in sales_summary
        ]

        return JsonResponse({'sales_summary': data}, status=200)

    except Exception as e:
        logger.exception("Error in five_year_sales_summary")
        return JsonResponse({'error': 'Something went wrong.'}, status=500)
