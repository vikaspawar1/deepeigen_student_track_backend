from django.http import JsonResponse
from datetime import datetime
from accounts.models import Account
from django.db.models import Count
from django.db.models.functions import TruncDate, TruncMonth, TruncYear
import logging

logger = logging.getLogger(__name__)

def graph_registeredUser_api(request):
    """
    API endpoint to retrieve user registration trends over a period.

    Automatically adjusts granularity based on the date range provided 
    (Daily, Monthly, or Yearly) and returns active vs inactive counts.

    Args:
        request (HttpRequest): Contains 'start_date' and 'end_date' (YYYY-MM-DD).

    Returns:
        JsonResponse: Time-series registration data.
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

        # Determine grouping granularity
        diff_days = (end_datetime - start_datetime).days
        if diff_days > 365:
            date_trunc = TruncYear('date_joined')
        elif diff_days > 31:
            date_trunc = TruncMonth('date_joined')
        else:
            date_trunc = TruncDate('date_joined')

        # Query and group
        users = Account.objects.filter(
            date_joined__range=(start_datetime, end_datetime)
        ).annotate(
            # date_group=date_trunc
            date_group=TruncDate('date_joined')  # ✅ daily-wise data

        ).values(
            'date_group', 'is_active'
        ).annotate(
            count=Count('id')
        ).order_by('date_group')

        # Format results
        result = {}
        for entry in users:
            date = entry['date_group'].strftime('%Y-%m-%d')
            if date not in result:
                result[date] = {'active': 0, 'inactive': 0}
            if entry['is_active']:
                result[date]['active'] += entry['count']
            else:
                result[date]['inactive'] += entry['count']

        response_data = {
            'dates': list(result.keys()),
            'active_counts': [v['active'] for v in result.values()],
            'inactive_counts': [v['inactive'] for v in result.values()],
        }

        # print("account data_:", response_data)
        return JsonResponse(response_data)

    except Exception as e:
        logger.exception('Unhandled error in graph_registeredUser_api')
        return JsonResponse({'error': 'Something went wrong. Please try again later.'}, status=500)
