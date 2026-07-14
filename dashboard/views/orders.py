import logging
from django.http import JsonResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from course.models import Order

logger = logging.getLogger(__name__)

def orders_api(request):
    """!
    @brief Administrative API endpoint to retrieve course and subscription order history.
    @details Provides a comprehensive audit trail of all transactions, including 
             payment status, gateway identifiers, and total amounts.

    @param request (HttpRequest) DRF/Django Request with 'page' and 'limit' query params.

    @return JsonResponse Paginated collection of order records (200).
    """
    try:
        #Get query parameters with defaults
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
        
        orders = Order.objects.all().order_by('-created_at')
        
        # Paginate orders
        paginator = Paginator(orders, limit)
        
        try:
            orders_page = paginator.page(page)
        except PageNotAnInteger:
            return JsonResponse({ 'error': 'Page is not an integer'}, status=400)
        except EmptyPage:
            return JsonResponse({'error': 'Page out of range', 'total_pages': paginator.num_pages}, status=404)
        
        orders_data = []
        
        for eu in orders_page.object_list:
            orders_data.append({
                'user_name': f"{eu.first_name} {eu.last_name}",
                'payment_id': eu.payment.payment_id if eu.payment else "N/A",
                'order_number': eu.order_number,
                'total_amount': eu.total_amount,
                'status': eu.status,
                'created_at': eu.created_at,
            })

        return JsonResponse({
            'orders': orders_data,
            'total_pages': paginator.num_pages,
            'current_page': page
        }, status=200)

    except Exception as e:
        logger.exception('unhandled error in orders_api view')
        return JsonResponse({
            'error': 'Something went wrong. Please try again later'
        }, status=500)