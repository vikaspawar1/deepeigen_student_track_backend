"""
Custom middleware for the accounts app.
"""
from django.http import HttpResponseForbidden
from django.urls import reverse
from admin_honeypot import urls

class RestrictAdminHoneypotMiddleware:
    """
    Middleware to restrict access to the Admin Honeypot dashboard.

    Only superadmins are allowed to view the honeypot login attempts.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        """
        Processes the request and checks for honeypot access restrictions.

        Args:
            request: HttpRequest object.

        Returns:
            HttpResponse: The processed response or a 403 Forbidden error.
        """
        response = self.get_response(request)
        honeypot_url = '/adminsecurelogin/admin_honeypot/loginattempt/'
        
        if request.path == honeypot_url and not request.user.is_superadmin:
            return HttpResponseForbidden("<h2>Access Forbidden </h2>")
        return response
    