from django.shortcuts import reverse, redirect
from django.conf import settings
from django.db import connection, OperationalError


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


_RDS_CLOSED_MSGS = (
    "server closed the connection unexpectedly",
    "connection already closed",
    "ssl connection has been closed unexpectedly",
    "terminating connection due to administrator command",
)


class DBRetryMiddleware:
    """
    Retries a request once when RDS drops an idle TCP connection mid-request.

    RDS (and AWS NLB/NAT) silently close idle TCP connections after ~350s.
    Django receives an OperationalError on the very next query that tries to
    reuse the dead socket. This middleware catches that specific error on safe
    (idempotent) HTTP methods, closes the stale Django connection, and retries
    the request once with a fresh connection.

    POST/PUT/PATCH/DELETE are NOT retried — a partial DB write is unsafe to
    silently repeat.
    """

    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except OperationalError as exc:
            msg = str(exc).lower()
            is_stale = any(m in msg for m in _RDS_CLOSED_MSGS)
            if is_stale and request.method in self.SAFE_METHODS:
                # Close the dead socket so Django opens a brand-new connection
                try:
                    connection.close()
                except Exception:
                    pass
                # Retry once — if it fails again, the real exception propagates
                return self.get_response(request)
            raise