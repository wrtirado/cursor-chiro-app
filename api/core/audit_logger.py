from typing import Optional, Dict, Any
from fastapi import Request

# Import the configured logger instance
from api.core.logging_config import audit_log
from api.models.base import User  # To get user ID easily


# Define standard audit event types (can be expanded)
class AuditEvent:
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILURE = "LOGIN_FAILURE"
    LOGOUT = "LOGOUT"
    REGISTER_SUCCESS = "REGISTER_SUCCESS"
    PASSWORD_CHANGE_SUCCESS = "PASSWORD_CHANGE_SUCCESS"
    PASSWORD_RESET_REQUEST = "PASSWORD_RESET_REQUEST"
    PASSWORD_RESET_SUCCESS = "PASSWORD_RESET_SUCCESS"
    USER_CREATE = "USER_CREATE"
    USER_UPDATE = "USER_UPDATE"
    USER_DELETE = "USER_DELETE"
    USER_VIEW = "USER_VIEW"
    PLAN_CREATE = "PLAN_CREATE"
    PLAN_UPDATE = "PLAN_UPDATE"
    PLAN_DELETE = "PLAN_DELETE"
    PLAN_VIEW = "PLAN_VIEW"
    PLAN_ASSIGN = "PLAN_ASSIGN"
    # Add more specific events as needed...
    MEDIA_UPLOAD = "MEDIA_UPLOAD"
    MEDIA_DOWNLOAD = "MEDIA_DOWNLOAD"
    MEDIA_DELETE = "MEDIA_DELETE"
    PROGRESS_UPDATE = "PROGRESS_UPDATE"
    COMPANY_CREATE = "COMPANY_CREATE"
    COMPANY_UPDATE = "COMPANY_UPDATE"
    OFFICE_CREATE = "OFFICE_CREATE"
    OFFICE_UPDATE = "OFFICE_UPDATE"
    AUTHORIZATION_FAILURE = "AUTHORIZATION_FAILURE"


def log_audit_event(
    request: Optional[Request] = None,
    user: Optional[User] = None,
    event_type: str = "GENERIC_EVENT",
    outcome: str = "SUCCESS",  # Or "FAILURE"
    resource_type: Optional[str] = None,
    resource_id: Optional[Any] = None,
    details: Optional[Dict[str, Any]] = None,
):
    """Helper function to log structured audit events."""
    props: Dict[str, Any] = {
        "event_type": event_type,
        "outcome": outcome,
    }

    # Add user info if available
    if user:
        props["user_id"] = user.user_id
        props["user_email"] = user.email
    else:
        # Maybe get user ID from token if user object not passed?
        props["user_id"] = None  # Or indicate anonymous/system action

    # Add request info if available
    if request:
        props["source_ip"] = request.client.host if request.client else None
        props["user_agent"] = request.headers.get("user-agent")
        props["request_path"] = request.url.path
        props["request_method"] = request.method

    # Add resource info if available
    if resource_type:
        props["resource_type"] = resource_type
    if resource_id is not None:
        props["resource_id"] = str(resource_id)  # Ensure ID is string/serializable

    # Add extra details
    if details:
        props["details"] = details  # Ensure details are JSON serializable

    # Construct the main log message
    message = f"Audit event: {event_type}"
    if user:
        message += f" by user {user.user_id}"
    if resource_type:
        message += f" on {resource_type}"
        if resource_id is not None:
            message += f" {resource_id}"
    message += f" - {outcome}"

    # Log using the configured audit logger
    # Pass structured data via the 'extra' dictionary
    if outcome == "FAILURE":
        audit_log.warning(message, extra={"props": props})
    else:
        audit_log.info(message, extra={"props": props})
