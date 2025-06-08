from typing import Optional, Dict, Any, List
from fastapi import Request
import json
from datetime import datetime
from enum import Enum

# Import the configured logger instance
from api.core.logging_config import audit_log
from api.models.base import User  # To get user ID easily

# Import AuditLog model for database logging (avoid circular imports)
try:
    from api.models.audit_log import AuditLog
except ImportError:
    AuditLog = None  # Fallback if model not available


# Define standard audit event types (can be expanded)
class AuditEvent(str, Enum):
    # User actions
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    USER_LOGIN = "user_login"

    # Authentication events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    AUTHENTICATION_SUCCESS = "authentication_success"
    AUTHENTICATION_FAILED = "authentication_failed"
    AUTHENTICATION_FAILED_LOCKED = "authentication_failed_locked"
    LOGOUT = "logout"
    TOKEN_REFRESH = "token_refresh"

    # Password and security events
    PASSWORD_CHANGED = "password_changed"
    PASSWORD_CHANGE_ERROR = "password_change_error"
    PASSWORD_RESET_ADMIN = "password_reset_admin"
    ACCOUNT_UNLOCKED = "account_unlocked"

    # Role and permission changes
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REMOVED = "role_removed"
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_REVOKED = "permission_revoked"

    # NEW: Role-specific audit events for HIPAA compliance
    ROLE_DEACTIVATED = "ROLE_DEACTIVATED"
    ROLE_REACTIVATED = "ROLE_REACTIVATED"
    ROLE_ASSIGNMENT_ATTEMPT = "ROLE_ASSIGNMENT_ATTEMPT"
    ROLE_ACCESS_GRANTED = "ROLE_ACCESS_GRANTED"
    ROLE_ACCESS_DENIED = "ROLE_ACCESS_DENIED"
    ROLE_CHECK_PERFORMED = "ROLE_CHECK_PERFORMED"
    MULTIPLE_ROLES_ACCESS = "MULTIPLE_ROLES_ACCESS"
    ROLE_CREATED = "ROLE_CREATED"
    ROLE_UPDATED = "ROLE_UPDATED"
    ROLE_DELETED = "ROLE_DELETED"

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

    # Consent tracking events for HIPAA compliance
    CONSENT_CREATED = "CONSENT_CREATED"
    CONSENT_GRANTED = "CONSENT_GRANTED"
    CONSENT_REVOKED = "CONSENT_REVOKED"
    CONSENT_EXPIRED = "CONSENT_EXPIRED"
    CONSENT_VIEWED = "CONSENT_VIEWED"
    CONSENT_UPDATED = "CONSENT_UPDATED"
    CONSENT_CHECKED = "CONSENT_CHECKED"
    CONSENT_BULK_CREATED = "CONSENT_BULK_CREATED"
    CONSENT_SEARCH_PERFORMED = "CONSENT_SEARCH_PERFORMED"
    CONSENT_OVERVIEW_VIEWED = "CONSENT_OVERVIEW_VIEWED"
    CONSENT_EXPIRING_CHECKED = "CONSENT_EXPIRING_CHECKED"
    CONSENT_OLD_EXPIRED = "CONSENT_OLD_EXPIRED"


def log_audit_event(
    request: Optional[Request] = None,
    user: Optional[User] = None,
    event_type: str = "GENERIC_EVENT",
    outcome: str = "SUCCESS",  # Or "FAILURE"
    resource_type: Optional[str] = None,
    resource_id: Optional[Any] = None,
    details: Optional[Dict[str, Any]] = None,
    db_session: Optional[Any] = None,  # SQLAlchemy session for database logging
):
    """
    Helper function to log structured audit events to both file and database.

    This dual logging approach ensures HIPAA compliance by providing:
    - File-based logs for real-time monitoring and debugging
    - Database logs for structured queries and compliance reporting
    """
    props: Dict[str, Any] = {
        "event_type": event_type,
        "outcome": outcome,
    }

    # Add user info if available
    if user:
        props["user_id"] = user.user_id
        props["user_email"] = user.email
    elif details and "user_id" in details:
        # Extract user_id from details if user object not provided
        props["user_id"] = details["user_id"]
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

    # Log to file using the configured audit logger
    # Pass structured data via the 'extra' dictionary
    if outcome == "FAILURE":
        audit_log.warning(message, extra={"props": props})
    else:
        audit_log.info(message, extra={"props": props})

    # Log to database for HIPAA compliance and structured querying
    if db_session and AuditLog:
        try:
            audit_entry = AuditLog(
                timestamp=datetime.now(),
                user_id=user.user_id if user else props.get("user_id"),
                event_type=event_type,
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id is not None else None,
                outcome=outcome,
                source_ip=props.get("source_ip"),
                user_agent=props.get("user_agent"),
                request_path=props.get("request_path"),
                request_method=props.get("request_method"),
                message=message,
                props=json.dumps(props),  # Store props as JSON string
            )

            db_session.add(audit_entry)
            try:
                db_session.commit()
                print(f"✅ Audit log saved to database: {event_type}")  # Debug print
            except Exception as commit_error:
                db_session.rollback()
                raise commit_error

        except Exception as e:
            # Don't let database logging failures break the application
            # Log the error but continue
            print(f"❌ Failed to write audit log to database: {e}")  # Debug print
            audit_log.error(
                f"Failed to write audit log to database: {e}",
                extra={"props": {"error": str(e)}},
            )
            if db_session:
                db_session.rollback()
    elif db_session and not AuditLog:
        print("⚠️ AuditLog model not available for database logging")  # Debug print


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


def log_role_event(
    action: str,
    user_id: Optional[int] = None,
    target_user_id: Optional[int] = None,
    role_id: Optional[int] = None,
    role_name: Optional[str] = None,
    assigned_by_id: Optional[int] = None,
    request: Optional[Request] = None,
    user: Optional[User] = None,
    details: Optional[Dict[str, Any]] = None,
    outcome: str = "SUCCESS",
    db_session: Optional[Any] = None,  # Database session for audit logging
):
    """
    Helper function to log role-related audit events for HIPAA compliance.

    Args:
        action: The role action performed (e.g., 'role_assigned', 'role_removed')
        user_id: ID of the user performing the action (if different from user object)
        target_user_id: ID of the user whose roles are being modified
        role_id: ID of the role being assigned/removed
        role_name: Name of the role (for readability)
        assigned_by_id: ID of the user who assigned the role
        request: FastAPI request object for IP/user-agent tracking
        user: User object performing the action
        details: Additional context details
        outcome: SUCCESS, FAILURE, or other outcome
    """

    # Map common role actions to audit event types
    action_event_map = {
        "role_assigned": AuditEvent.ROLE_ASSIGNED,
        "role_unassigned": AuditEvent.ROLE_REMOVED,
        "role_deactivated": AuditEvent.ROLE_DEACTIVATED,
        "role_reactivated": AuditEvent.ROLE_REACTIVATED,
        "role_assignment_attempt": AuditEvent.ROLE_ASSIGNMENT_ATTEMPT,
        "role_access_granted": AuditEvent.PERMISSION_GRANTED,
        "role_access_denied": AuditEvent.PERMISSION_REVOKED,
        "role_check_performed": AuditEvent.ROLE_CHECK_PERFORMED,
        "multiple_roles_access": AuditEvent.MULTIPLE_ROLES_ACCESS,
        "role_created": AuditEvent.ROLE_CREATED,
        "role_updated": AuditEvent.ROLE_UPDATED,
        "role_deleted": AuditEvent.ROLE_DELETED,
    }

    event_type = action_event_map.get(action, action.upper())

    # Build structured props for role events
    props: Dict[str, Any] = {
        "event_type": event_type,
        "outcome": outcome,
        "resource_type": "user_role",
    }

    # Add user info if available
    if user:
        props["user_id"] = user.user_id
        props["user_email"] = user.email
    elif user_id:
        props["user_id"] = user_id

    # Add request info if available
    if request:
        props["source_ip"] = request.client.host if request.client else None
        props["user_agent"] = request.headers.get("user-agent")
        props["request_path"] = request.url.path
        props["request_method"] = request.method
    else:
        props["source_ip"] = "system"
        props["user_agent"] = "system"
        props["request_path"] = "role_operation"
        props["request_method"] = "SYSTEM"

    # Add role-specific information
    if target_user_id:
        props["target_user_id"] = target_user_id
        props["resource_id"] = str(target_user_id)  # Primary resource being modified

    if role_id:
        props["role_id"] = role_id

    if role_name:
        props["role_name"] = role_name

    if assigned_by_id:
        props["assigned_by_id"] = assigned_by_id

    # Add details for HIPAA compliance
    if details:
        props["details"] = details

    # Construct message for role events
    message = f"Role audit: {action}"
    if target_user_id and target_user_id != user_id:
        message += f" for user {target_user_id}"
    if role_name:
        message += f" role '{role_name}'"
    elif role_id:
        message += f" role ID {role_id}"
    if assigned_by_id and user_id != assigned_by_id:
        message += f" by user {assigned_by_id}"
    message += f" - {outcome}"

    # Use centralized audit logging for both file and database
    log_audit_event(
        request=request,
        user=user,
        event_type=event_type,
        outcome=outcome,
        resource_type="user_role",
        resource_id=target_user_id,
        details=props,
        db_session=db_session,
    )


def log_role_access_check(
    user_id: int,
    required_roles: List[str],
    user_roles: List[str],
    granted: bool,
    request: Optional[Request] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    db_session: Optional[Any] = None,  # Database session for audit logging
):
    """
    Log role-based access control checks for HIPAA compliance.

    This specialized function logs both successful and failed role checks,
    providing the detailed audit trail required for HIPAA compliance.
    """
    outcome = "SUCCESS" if granted else "FAILURE"
    action = "role_access_granted" if granted else "role_access_denied"

    details = {
        "required_roles": required_roles,
        "user_roles": user_roles,
        "access_granted": granted,
        "request_details": {
            "path": request.url.path if request else None,
            "method": request.method if request else None,
        },
    }

    log_audit_event(
        request=request,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        outcome=outcome,
        db_session=db_session,
    )


def log_consent_event(
    action: str,
    user_id: int,
    patient_id: Optional[int] = None,
    consent_id: Optional[int] = None,
    consent_type: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    outcome: str = "SUCCESS",
    db_session: Optional[Any] = None,
):
    """
    Log consent-related events for HIPAA compliance.

    This specialized function logs consent operations with the appropriate
    structure for compliance and audit trail requirements.
    """
    # Build structured details
    event_details = {
        "user_id": user_id,  # Add user_id to details for log_audit_event
        "patient_id": patient_id,
        "consent_type": consent_type,
    }

    if details:
        event_details.update(details)

    # Determine resource info
    resource_type = "consent_record"
    resource_id = str(consent_id) if consent_id else None

    log_audit_event(
        event_type=action,
        outcome=outcome,
        resource_type=resource_type,
        resource_id=resource_id,
        details=event_details,
        db_session=db_session,
    )
