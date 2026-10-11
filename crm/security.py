from django.conf import settings


class SecurityHeadersMiddleware:
    """Set a conservative policy for the first-party CRM interface."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        form_action = "form-action 'self'"
        if settings.DEBUG:
            # allauth can build the Google endpoint from the Django Site record.
            # Permit both local development hostnames while retaining a strict
            # same-origin policy for every deployed environment.
            form_action += " http://127.0.0.1:8000 http://localhost:8000"
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; "
            f"{form_action}; img-src 'self' data:; font-src 'self'; style-src 'self'; "
            "script-src 'self'; connect-src 'self'; upgrade-insecure-requests",
        )
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        return response
