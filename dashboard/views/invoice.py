from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse
from course.models import Invoice_Registrant
import logging
import json

logger = logging.getLogger(__name__)  # Optional: for logging errors in production
  

# Invoice Registration api
def invoiceRegistrant_api(request):
    """!
    @brief Administrative API endpoint to audit registration-based invoices.
    @details Provides a searchable/paginated list of invoice records, mapping student 
             identities to specific order numbers and serials.

    @param request (HttpRequest) DRF/Django Request with 'page' and 'limit' query params.

    @return JsonResponse Paginated list of invoice registrant records (200).
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
        
        invoiceRegistrant = Invoice_Registrant.objects.all()
        
        # Paginate enrolled users
        paginator = Paginator(invoiceRegistrant, limit)
        
        try:
            invoiceRegistrant_page = paginator.page(page)
        except PageNotAnInteger:
            return JsonResponse({ 'error': 'Page is not an integer'}, status=400)
        except EmptyPage:
            return JsonResponse({'error': 'Page out of range', 'total_pages': paginator.num_pages}, status=404)
        
        invoiceRegistrant_data = []
        
        for eu in invoiceRegistrant_page.object_list:
            invoiceRegistrant_data.append({
                'id': eu.id,
                'user_email': eu.name.user.email,
                'order_number': eu.order.order_number,
                'serial_no': eu.serial_no,
                'invoice': eu.invoice.url if eu.invoice else None,
            })
            
        return JsonResponse({
            'invoiceRegistrant': invoiceRegistrant_data,
            'total_pages': paginator.num_pages,
            'current_page': page
        }, status=200)
    except Exception as e:
        # Optional: log unexpected errors
        logger.exception('unhandled error in assignment_api view')
        
        return JsonResponse({
            'error': 'Something went wrong. Please try again later'         
        }, status=400)
        
  