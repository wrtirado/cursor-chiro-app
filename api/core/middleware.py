from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class SecureHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        # Content-Security-Policy is complex and requires careful tuning.
        # Allow resources required by Swagger UI (/docs)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' cdn.jsdelivr.net 'unsafe-inline'; "  # Allow swagger JS and inline script
            "style-src 'self' cdn.jsdelivr.net 'unsafe-inline'; "  # Allow swagger CSS and inline styles
            "img-src 'self' fastapi.tiangolo.com data:; "  # Allow self, FastAPI favicon, and data URIs
            # "connect-src 'self'; " # Might be needed if Swagger UI makes calls back to the API
        )
        # Strict-Transport-Security (HSTS) - Only effective over HTTPS.
        # Browsers will ignore this header if the site is accessed via HTTP.
        # Enable this once HTTPS is enforced in production.
        # response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

        # Referrer-Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions-Policy (prevents features like geolocation, microphone, etc., unless allowed)
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=()"
        )

        return response
