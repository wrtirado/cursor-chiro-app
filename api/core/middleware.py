from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import os
import logging

logger = logging.getLogger(__name__)


class SecureHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Basic security headers for all requests
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

        # Enhanced security for payment-related endpoints
        if self._is_payment_endpoint(request.url.path):
            # Cache-Control for sensitive payment data
            response.headers["Cache-Control"] = (
                "no-store, no-cache, must-revalidate, private"
            )
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

            # Additional payment security headers
            response.headers["X-Payment-Secure"] = "true"

            # Log payment endpoint access for audit
            logger.info(
                f"Payment endpoint accessed: {request.method} {request.url.path} "
                f"from IP: {self._get_client_ip(request)}"
            )

        # Strict-Transport-Security (HSTS) - Only effective over HTTPS.
        # Enable in production environments
        environment = os.getenv("ENVIRONMENT", "development")
        if environment in ["staging", "production"]:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

            # Enforce HTTPS in production
            if not self._is_secure_request(request) and environment == "production":
                logger.warning(
                    f"Insecure request to production environment: {request.url}"
                )

        # Referrer-Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions-Policy (prevents features like geolocation, microphone, etc., unless allowed)
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=()"
        )

        return response

    def _is_payment_endpoint(self, path: str) -> bool:
        """
        Check if the request path is a payment-related endpoint.

        Args:
            path: The request path to check

        Returns:
            bool: True if it's a payment endpoint
        """
        payment_patterns = [
            "/api/v1/offices",  # Office endpoints may contain payment data
            "/billing",
            "/payment",
            "/subscription",
            "/invoice",
            "/stripe",
        ]

        return any(pattern in path.lower() for pattern in payment_patterns)

    def _is_secure_request(self, request: Request) -> bool:
        """
        Check if the request is using HTTPS.

        Args:
            request: The FastAPI request object

        Returns:
            bool: True if using HTTPS
        """
        # Check if request is HTTPS
        if request.url.scheme == "https":
            return True

        # Check for forwarded protocol headers (for reverse proxy scenarios)
        forwarded_proto = request.headers.get("X-Forwarded-Proto", "").lower()
        if forwarded_proto == "https":
            return True

        return False

    def _get_client_ip(self, request: Request) -> str:
        """
        Get the client IP address, considering reverse proxies.

        Args:
            request: The FastAPI request object

        Returns:
            str: The client IP address
        """
        # Check for forwarded IP headers (for reverse proxy scenarios)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For can contain multiple IPs, take the first one
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fallback to direct client
        return request.client.host if request.client else "unknown"
