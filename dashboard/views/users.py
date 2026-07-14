from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse
from accounts.models import Account
import logging
import json

logger = logging.getLogger(__name__)  # Optional: for logging errors in production

def users_api(request):
    """!
    @brief Administrative API endpoint to retrieve and filter all registered user accounts.
    @details Facilitates user management by providing paginated access to primary account 
             data, supporting filtering by active/inactive status.

    @param request (HttpRequest) DRF/Django Request with 'page', 'limit', and 'is_active' query params.

    @return JsonResponse Paginated collection of registered user records (200).
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

        is_active = request.GET.get('is_active')

        # Fetch and optionally filter users
        users = Account.objects.all().order_by('-date_joined')

        if is_active in ['true', 'false']:
            users = users.filter(is_active=(is_active == 'true'))

        # Paginate users
        paginator = Paginator(users, limit)

        try:
            users_page = paginator.page(page)
        except PageNotAnInteger:
            return JsonResponse({'error': 'Page is not an integer'}, status=400)
        except EmptyPage:
            return JsonResponse({'error': 'Page out of range', 'total_pages': paginator.num_pages}, status=404)

        users_data = list(users_page.object_list.values())

        # print("users:", json.dumps(users_data, indent=4, default=str))

        return JsonResponse({
            'all_users': users_data,
            'total_pages': paginator.num_pages,
            'current_page': page,
        }, status=200)

    except Exception as e:
        # Optional: log unexpected errors
        logger.exception("Unhandled error in users_api view")

        return JsonResponse({
            'error': 'Something went wrong. Please try again later.'
        }, status=500)

