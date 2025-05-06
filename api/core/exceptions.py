from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException

from api.core.logging_config import app_log  # Use the configured app logger


async def generic_exception_handler(request: Request, exc: Exception):
    """Handles unexpected server errors, logging the real error but returning a generic response."""
    app_log.error(
        f"Unhandled exception during request to {request.url.path}: {exc}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error. Please contact support if the issue persists."
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    """Handles FastAPI's HTTPException, logging details and returning standard response."""
    # Log the exception detail for internal review (could potentially contain info)
    # Be cautious if exc.detail might contain PHI in some custom exceptions.
    app_log.warning(
        f"HTTPException during request to {request.url.path}: Status={exc.status_code}, Detail='{exc.detail}'"
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},  # Return the original detail to the client
        headers=exc.headers,  # Include any custom headers from the exception
    )


# You can add handlers for other specific exception types if needed
# e.g., RequestValidationError for Pydantic validation errors
# from fastapi.exceptions import RequestValidationError
# async def validation_exception_handler(request: Request, exc: RequestValidationError):
#     app_log.warning(f"Validation error for {request.url.path}: {exc.errors()}")
#     return JSONResponse(
#         status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
#         content={"detail": exc.errors()},
#     )
