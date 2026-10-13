from django.conf import settings


class SecurityHeadersMiddleware:
    """Set a conservative policy for the first-party CRM interface."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.headers["Cache-Control"] = "private, no-store, max-age=0"
        form_action_sources = ["'self'"]
        if settings.DEBUG:
            form_action_sources.extend(("http://127.0.0.1:8000", "http://localhost:8000"))
        # OAuth login forms may use an absolute URL based on the configured
        # deployment host. Permit only origins Django already trusts for CSRF.
        form_action_sources.extend(
            origin.rstrip("/")
            for origin in settings.CSRF_TRUSTED_ORIGINS
            if origin.startswith(("https://", "http://"))
        )
        form_action = "form-action " + " ".join(dict.fromkeys(form_action_sources))
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; "
            f"{form_action}; img-src 'self' data:; font-src 'self' data:; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; connect-src 'self'; upgrade-insecure-requests",
        )
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        return response
