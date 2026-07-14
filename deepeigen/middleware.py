from django.shortcuts import reverse, redirect
from django.conf import settings


class MaintenanceModeMiddleware:
    """!
    @brief Middleware to intercept and redirect traffic during platform maintenance.
    @details Monitors the global 'MAINTENANCE_MODE' setting. If enabled, it redirects 
             all incoming requests to the designated maintenance landing page, 
             excluding the maintenance view itself to avoid infinite loops.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.META.get('PATH_INFO', "")

        if settings.MAINTENANCE_MODE and path!= reverse("maintenance"):
            response = redirect(reverse("maintenance"))
            return response

        response = self.get_response(request)

        return response