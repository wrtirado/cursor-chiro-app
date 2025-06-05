from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware  # Import CORS Middleware
import logging
import os
from fastapi.exceptions import HTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.core.config import settings
from api.core.exceptions import http_exception_handler, starlette_exception_handler
from api.companies.router import router as companies_router
from api.auth.router import router as auth_router
from api.plans.router import router as plans_router
from api.progress.router import router as progress_router
from api.media.router import router as media_router
from api.offices.router import router as offices_router  # Import offices router
from api.users.router import router as users_router
from api.branding.router import router as branding_router
from api.roles.router import router as roles_router  # Import roles router

from api.core.middleware import SecureHeadersMiddleware  # Import the new middleware
from api.core.security_validator import (
    payment_security_validator,
)  # Import security validator

# Set up logging configuration
log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
log_format = "[%(asctime)s] %(levelname)s in %(name)s: %(message)s"

# Configure root logger
logging.basicConfig(
    level=log_level,
    format=log_format,
    handlers=[
        logging.StreamHandler(),  # Console output
        logging.FileHandler(settings.APP_LOG_FILE, mode="a"),  # File output
    ],
)

# Configure audit logging
audit_logger = logging.getLogger("audit")
audit_handler = logging.FileHandler(settings.AUDIT_LOG_FILE, mode="a")
audit_handler.setFormatter(logging.Formatter(log_format))
audit_logger.addHandler(audit_handler)
audit_logger.setLevel(logging.INFO)

# Import after logging setup to ensure loggers are configured
from api.database.session import engine, Base
from api.models import base
from api.core.audit_logger import log_application_startup

# Create all tables (SQLAlchemy create_all method)
# This replaces Alembic migrations for now
Base.metadata.create_all(bind=engine)

# Also call the startup audit log function
log_application_startup()

# Configuration note: CORS is applied here instead of per-router
# because it's a cross-cutting concern that affects all routes.

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    # Additional FastAPI configs for production security
    docs_url=(
        "/docs" if os.getenv("ENVIRONMENT", "development") == "development" else None
    ),
    redoc_url=(
        "/redoc" if os.getenv("ENVIRONMENT", "development") == "development" else None
    ),
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # Uses the origins from settings
    allow_credentials=True,
    allow_methods=["*"],  # Can be more specific: ["GET", "POST", "PUT", "DELETE"]
    allow_headers=["*"],  # Can be more specific if needed
)

# Add the Secure Headers Middleware
app.add_middleware(SecureHeadersMiddleware)

# Exception handlers
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(StarletteHTTPException, starlette_exception_handler)

# Include routers
app.include_router(
    companies_router, prefix=settings.API_V1_STR + "/companies", tags=["companies"]
)
app.include_router(auth_router, prefix=settings.API_V1_STR + "/auth", tags=["auth"])
app.include_router(plans_router, prefix=settings.API_V1_STR + "/plans", tags=["plans"])
app.include_router(
    progress_router, prefix=settings.API_V1_STR + "/progress", tags=["progress"]
)
app.include_router(media_router, prefix=settings.API_V1_STR + "/media", tags=["media"])
app.include_router(
    offices_router, prefix=settings.API_V1_STR + "/offices", tags=["offices"]
)
app.include_router(users_router, prefix=settings.API_V1_STR + "/users", tags=["users"])
app.include_router(
    branding_router, prefix=settings.API_V1_STR + "/branding", tags=["branding"]
)
app.include_router(roles_router, prefix=settings.API_V1_STR + "/roles", tags=["roles"])


@app.on_event("startup")
async def startup_event():
    """Run security validation on application startup."""
    logger.info("Running security validation on startup...")

    try:
        # Run payment security validation
        results = payment_security_validator.validate_all()
        summary = payment_security_validator.get_summary()

        # Log summary
        logger.info(f"Security validation completed: {summary['overall_status']}")
        logger.info(f"Checks: {summary['passed']}/{summary['total_checks']} passed")

        if summary["critical_issues"] > 0:
            logger.error(
                f"CRITICAL SECURITY ISSUES FOUND: {summary['critical_issues_list']}"
            )
            # Note: We don't exit here to allow development/staging with warnings
            # In production, you might want to exit on critical issues

        if summary["warnings"] > 0:
            logger.warning(f"Security warnings: {summary['warning_issues_list']}")

        # Log detailed results
        payment_security_validator.log_results()

    except Exception as e:
        logger.error(f"Security validation failed: {e}")


@app.get("/")
def read_root():
    return {"message": "Welcome to the Tirado Chiropractic API"}


@app.get("/health")
def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "healthy", "environment": settings.ENVIRONMENT}


@app.get("/security-status")
def security_status():
    """Get current security configuration status."""
    try:
        summary = payment_security_validator.get_summary()
        return {
            "security_status": summary,
            "environment": settings.ENVIRONMENT,
            "timestamp": logging.Formatter().formatTime(
                logging.LogRecord("", 0, "", 0, "", (), None)
            ),
        }
    except Exception as e:
        logger.error(f"Failed to get security status: {e}")
        return {"error": "Failed to retrieve security status"}


# Conditional middleware and configurations can also be set based on environment
# if settings.ENVIRONMENT == "production":
#     # Additional production-specific middleware or configs
#     pass

# Old CORS setup
# from fastapi.middleware.cors import CORSMiddleware

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React & Vite defaults
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )
