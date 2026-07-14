from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse
from course.models import EnrolledUser
import logging

logger = logging.getLogger(__name__)  # Optional: for logging errors in production


# enrolled user api- getting all the enrolled users
def enrolledUsers_api(request):
    """!
    @brief Administrative API endpoint to retrieve a comprehensive list of all course enrollments.
    @details Aggregates granular student data, including financial status (installments), 
             access validity windows, and direct links to generated invoices.

    @param request (HttpRequest) DRF/Django Request with 'page' and 'limit' query params.

    @return JsonResponse Paginated data of all enrolled users and their statuses (200).
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
        
        enrolledusers = EnrolledUser.objects.all().order_by('-created_at')
        
        # Paginate enrolled users
        paginator = Paginator(enrolledusers, limit)
        
        try:
            enrolledusers_page = paginator.page(page)
        except PageNotAnInteger:
            return JsonResponse({ 'error': 'Page is not an integer'}, status=400)
        except EmptyPage:
            return JsonResponse({'error': 'Page out of range', 'total_pages': paginator.num_pages}, status=404)
        
        enrolled_users_data = []
        
        for eu in enrolledusers_page.object_list:
            enrolled_users_data.append({
                'id': eu.id,
                'user_id': eu.user.id,
                'user_name': eu.user.first_name,
                'user_email': eu.user.email,
                'course_id': eu.course.id,
                'course_title': eu.course.title,
                'order_number': eu.order.order_number if eu.order else None,
                'payment_Id': eu.payment.payment_id if eu.payment else None,
                'course_price': eu.course_price,
                'enrolled': eu.enrolled,
                'created_at': eu.created_at,
                'end_at': eu.end_at,
                'full_access_flag': eu.full_access_flag,
                'no_of_installments': eu.no_of_installments,
                'first_installments': eu.first_installments,
                'second_installments': eu.second_installments,
                'third_installments': eu.third_installments,
                'serial_number': eu.serial_number,
                'invoice': eu.invoice.url if eu.invoice else None,
            })
            
        # print("enrolled User_:", json.dumps(enrolled_users_data, indent=4, default=str))
        return JsonResponse({
            'all_users': enrolled_users_data,
            'total_pages': paginator.num_pages,
            'current_page': page
        }, status=200)
    
    except Exception as e:
        # Optional: log unexpected errors
        logger.exception('Unhandled error in enrolled_users_api view')
        
        return JsonResponse({
            'error': 'Something went wrong. Please try again later'
        }, status=500)
        
  