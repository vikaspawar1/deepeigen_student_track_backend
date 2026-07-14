"""
Custom decorators for API endpoints and views.
"""
from functools import wraps
from django.http import JsonResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.views.decorators.csrf import csrf_exempt
import logging

logger = logging.getLogger(__name__)


def api_login_required(view_func):
    """!
    @brief Custom decorator to enforce JWT authentication on API views.
    @details Manually executes the rest_framework_simplejwt authentication flow to ensure the 
             request user is populated and authenticated. Specifically designed for hybrid 
             functional views where standard DRF middleware might be bypassed.

    @param view_func (callable) The target view function to be wrapped.

    @return callable Wrapped view with injection of authenticated user or 401 response.
    """
    @wraps(view_func)
    @csrf_exempt
    def wrapper(request, *args, **kwargs):
        # Allow CORS preflight requests
        if request.method == 'OPTIONS':
            return view_func(request, *args, **kwargs)
        
        # Implement JWT Authentication Loader
        jwt_authenticator = JWTAuthentication()
        try:
            # Fallback for standard HttpRequest mapping HTTP_AUTHORIZATION
            # DRF's get_header relies on request.META
            auth_result = jwt_authenticator.authenticate(request)
            if auth_result is not None:
                user, token = auth_result
                request.user = user
                
            if not request.user.is_authenticated:
                client_ip = request.META.get('REMOTE_ADDR', 'unknown')
                logger.warning(
                    f"Unauthorized API access attempt from {client_ip} to {request.path} {request.method}"
                )
                return JsonResponse(
                    {
                        "detail": "Authentication required",
                        "code": "AUTH_REQUIRED"
                    },
                    status=401
                )
        except AuthenticationFailed as e:
            return JsonResponse(
                {
                    "detail": str(e),
                    "code": "AUTH_REQUIRED"
                },
                status=401
            )
            
        return view_func(request, *args, **kwargs)
    
    return wrapper
