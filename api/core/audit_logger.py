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
    # Billing events
    BILLING_USER_ACTIVATED = "BILLING_USER_ACTIVATED"
    BILLING_USER_DEACTIVATED = "BILLING_USER_DEACTIVATED"
    BILLING_STATUS_UPDATED = "BILLING_STATUS_UPDATED"
    BILLING_CYCLE_UPDATED = "BILLING_CYCLE_UPDATED"
    INVOICE_CREATED = "INVOICE_CREATED"
    INVOICE_UPDATED = "INVOICE_UPDATED"
    INVOICE_DELETED = "INVOICE_DELETED"
    LINE_ITEM_CREATED = "LINE_ITEM_CREATED"
    LINE_ITEM_UPDATED = "LINE_ITEM_UPDATED"
    LINE_ITEM_DELETED = "LINE_ITEM_DELETED"
    # Monthly billing events
    MONTHLY_INVOICES_GENERATED = "MONTHLY_INVOICES_GENERATED"
    MONTHLY_INVOICE_GENERATED_FOR_OFFICE = "MONTHLY_INVOICE_GENERATED_FOR_OFFICE"
    MONTHLY_BILLING_CYCLE_COMPLETED = "MONTHLY_BILLING_CYCLE_COMPLETED"
    BILLING_CYCLE_UPDATED_FOR_OFFICE = "BILLING_CYCLE_UPDATED_FOR_OFFICE"
    # One-off billing events
    ONE_OFF_CHARGE_CREATED = "ONE_OFF_CHARGE_CREATED"
    ONE_OFF_CHARGE_FAILED = "ONE_OFF_CHARGE_FAILED"
    ONE_OFF_LINE_ITEM_CREATED = "ONE_OFF_LINE_ITEM_CREATED"
    SETUP_FEE_CREATED = "SETUP_FEE_CREATED"
    BULK_SETUP_FEES_CREATED = "BULK_SETUP_FEES_CREATED"
    # Branding events
    BRANDING_CREATED = "BRANDING_CREATED"
    BRANDING_UPDATED = "BRANDING_UPDATED"
    BRANDING_DELETED = "BRANDING_DELETED"
    BRANDING_VIEWED = "BRANDING_VIEWED"


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


def log_application_startup():
    """Log application startup event for audit purposes."""
    import os

    props = {
        "event_type": "APPLICATION_STARTUP",
        "outcome": "SUCCESS",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "source_ip": "system",
        "user_agent": "system",
        "request_path": "startup",
        "request_method": "SYSTEM",
        "resource_type": "application",
        "resource_id": "api_server",
        "details": {"startup_time": "system_boot", "api_version": "v1"},
    }

    message = "Application startup completed successfully"
    audit_log.info(message, extra={"props": props})


def log_billing_event(
    action: str,
    office_id: Optional[int] = None,
    user_id: Optional[int] = None,
    patient_id: Optional[int] = None,
    invoice_id: Optional[int] = None,
    line_item_id: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
    outcome: str = "SUCCESS",
):
    """Helper function to log billing-related audit events with appropriate structure."""

    # Map common billing actions to audit event types
    action_event_map = {
        "user_billing_status_updated": AuditEvent.BILLING_STATUS_UPDATED,
        "user_activated_for_billing": AuditEvent.BILLING_USER_ACTIVATED,
        "user_deactivated_for_billing": AuditEvent.BILLING_USER_DEACTIVATED,
        "user_billed_cycle_updated": AuditEvent.BILLING_CYCLE_UPDATED,
        "invoice_created": AuditEvent.INVOICE_CREATED,
        "invoice_updated": AuditEvent.INVOICE_UPDATED,
        "invoice_deleted": AuditEvent.INVOICE_DELETED,
        "line_item_created": AuditEvent.LINE_ITEM_CREATED,
        "line_item_updated": AuditEvent.LINE_ITEM_UPDATED,
        "line_item_deleted": AuditEvent.LINE_ITEM_DELETED,
        # Monthly billing actions
        "monthly_invoices_generated": AuditEvent.MONTHLY_INVOICES_GENERATED,
        "monthly_invoice_generated_for_office": AuditEvent.MONTHLY_INVOICE_GENERATED_FOR_OFFICE,
        "monthly_billing_cycle_completed": AuditEvent.MONTHLY_BILLING_CYCLE_COMPLETED,
        "billing_cycle_updated_for_office": AuditEvent.BILLING_CYCLE_UPDATED_FOR_OFFICE,
        # One-off billing actions
        "one_off_charge_created": AuditEvent.ONE_OFF_CHARGE_CREATED,
        "one_off_charge_failed": AuditEvent.ONE_OFF_CHARGE_FAILED,
        "one_off_line_item_created": AuditEvent.ONE_OFF_LINE_ITEM_CREATED,
        "setup_fee_created": AuditEvent.SETUP_FEE_CREATED,
        "bulk_setup_fees_created": AuditEvent.BULK_SETUP_FEES_CREATED,
    }

    event_type = action_event_map.get(action, action.upper())

    # Build structured props
    props: Dict[str, Any] = {
        "event_type": event_type,
        "outcome": outcome,
        "source_ip": "system",  # Billing events are typically system-initiated
        "user_agent": "billing_system",
        "request_path": "billing_operation",
        "request_method": "SYSTEM",
    }

    # Add IDs if provided
    if user_id:
        props["user_id"] = user_id
    if office_id:
        props["office_id"] = office_id
    if patient_id:
        props["patient_id"] = patient_id
    if invoice_id:
        props["resource_type"] = "invoice"
        props["resource_id"] = str(invoice_id)
    elif line_item_id:
        props["resource_type"] = "line_item"
        props["resource_id"] = str(line_item_id)
    elif patient_id:
        props["resource_type"] = "user_billing"
        props["resource_id"] = str(patient_id)

    # Add details
    if details:
        props["details"] = details

    # Construct message
    message = f"Billing audit: {action}"
    if office_id:
        message += f" for office {office_id}"
    if patient_id and patient_id != user_id:
        message += f" affecting patient {patient_id}"
    if user_id:
        message += f" by user {user_id}"
    message += f" - {outcome}"

    # Log the event
    if outcome == "FAILURE":
        audit_log.warning(message, extra={"props": props})
    else:
        audit_log.info(message, extra={"props": props})
