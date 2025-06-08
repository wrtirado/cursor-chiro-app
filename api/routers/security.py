"""
Enhanced Security Management Router for HIPAA Compliance
Implements Task 23.3 - Enhance Secure Credential Handling
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from datetime import datetime, timedelta
import json

from api.database.session import get_db
from api.auth.dependencies import get_current_active_user, require_role
from api.core.security import (
    validate_password_complexity,
    calculate_password_strength,
    is_account_locked,
    get_lockout_remaining_time,
    hash_password_for_history,
    get_password_hash,
    PASSWORD_HISTORY_COUNT,
)
from api.core.audit_logger import log_audit_event
from api.crud import crud_user
from api.models.base import User
from api.schemas.user import (
    PasswordValidationResponse,
    PasswordChangeRequest,
    PasswordChangeResponse,
    AccountSecurityStatus,
    BulkPasswordResetRequest,
    BulkPasswordResetResponse,
    SecurityAuditSummary,
)
from api.core.utils import generate_random_code

router = APIRouter()


@router.post("/validate-password", response_model=PasswordValidationResponse)
async def validate_password(
    password: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Validate password complexity and strength.
    Provides real-time feedback for password creation/updates.
    """
    # Validate complexity
    validation_result = validate_password_complexity(password)

    # Calculate strength
    strength_analysis = calculate_password_strength(password)

    # Check against user's password history if available
    history_conflict = False
    if current_user.password_history:
        try:
            password_history = json.loads(current_user.password_history)
            history_conflict = hash_password_for_history(password) in password_history
        except (json.JSONDecodeError, TypeError):
            pass

    if history_conflict:
        validation_result.errors.append(
            f"Password was recently used. Last {PASSWORD_HISTORY_COUNT} passwords cannot be reused."
        )
        validation_result.is_valid = False

    return PasswordValidationResponse(
        is_valid=validation_result.is_valid,
        errors=validation_result.errors,
        strength_score=strength_analysis["score"],
        strength_category=strength_analysis["strength"],
        feedback=strength_analysis["feedback"],
    )


@router.post("/change-password", response_model=PasswordChangeResponse)
async def change_password(
    password_request: PasswordChangeRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Change user password with enhanced security validation.
    Enforces password complexity, history, and audit logging.
    """
    # Use the enhanced update_user function which handles all validation
    from api.schemas.user import UserUpdate

    user_update = UserUpdate(
        password=password_request.new_password,
        current_password=password_request.current_password,
    )

    try:
        updated_user = crud_user.update_user(db, current_user, user_update)

        return PasswordChangeResponse(
            message="Password changed successfully",
            password_changed_at=updated_user.password_changed_at,
            next_required_change=None,  # Could implement password expiry here
        )
    except HTTPException as e:
        # Re-raise HTTPExceptions from CRUD layer
        raise e
    except Exception as e:
        # Log unexpected errors
        log_audit_event(
            event_type="PASSWORD_CHANGE_ERROR",
            outcome="FAILURE",
            details={"user_id": current_user.user_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while changing password",
        )


@router.get("/account-status", response_model=AccountSecurityStatus)
async def get_account_security_status(
    current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)
):
    """
    Get current user's account security status.
    Includes lockout info, password age, and security metrics.
    """
    # Calculate password age
    password_age_days = None
    if current_user.password_changed_at:
        age_delta = datetime.utcnow() - current_user.password_changed_at
        password_age_days = age_delta.days

    # Check if account is currently locked
    is_locked = is_account_locked(
        current_user.failed_login_attempts, current_user.last_failed_login
    )
    lockout_remaining = 0
    if is_locked and current_user.last_failed_login:
        lockout_remaining = get_lockout_remaining_time(current_user.last_failed_login)

    return AccountSecurityStatus(
        user_id=current_user.user_id,
        email=current_user.email,
        password_changed_at=current_user.password_changed_at,
        failed_login_attempts=current_user.failed_login_attempts,
        last_failed_login=current_user.last_failed_login,
        account_locked_until=current_user.account_locked_until,
        last_successful_login=current_user.last_successful_login,
        is_locked=is_locked,
        lockout_remaining_minutes=lockout_remaining,
        password_age_days=password_age_days,
    )


@router.post("/unlock-account/{user_id}")
async def unlock_user_account(
    user_id: int,
    current_user: User = Depends(require_role(["admin", "office_manager"])),
    db: Session = Depends(get_db),
):
    """
    Administratively unlock a user account.
    Requires admin or office_manager role.
    """
    target_user = crud_user.get_user(db, user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Reset failed login attempts and lockout
    target_user.failed_login_attempts = 0
    target_user.last_failed_login = None
    target_user.account_locked_until = None

    db.add(target_user)
    db.commit()

    # Log the unlock action
    log_audit_event(
        event_type="ACCOUNT_UNLOCKED",
        outcome="SUCCESS",
        details={
            "target_user_id": user_id,
            "target_email": target_user.email,
            "unlocked_by": current_user.user_id,
            "unlocked_at": datetime.utcnow().isoformat(),
        },
    )

    return {"message": f"Account for {target_user.email} has been unlocked"}


@router.get("/security-summary", response_model=SecurityAuditSummary)
async def get_security_audit_summary(
    days: int = 30,
    current_user: User = Depends(require_role(["admin", "office_manager"])),
    db: Session = Depends(get_db),
):
    """
    Get security audit summary for the organization.
    Shows locked accounts, failed logins, and security metrics.
    """
    # Get basic user counts
    total_users = db.query(User).count()

    # Count locked accounts
    locked_accounts = db.query(User).filter(User.failed_login_attempts >= 5).count()

    # Count recent failed login attempts (last X days)
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    recent_failures = (
        db.query(User).filter(User.last_failed_login >= cutoff_date).count()
    )

    # Count recent password changes
    recent_password_changes = (
        db.query(User).filter(User.password_changed_at >= cutoff_date).count()
    )

    # Count old passwords (potentially weak - over 90 days old)
    old_password_cutoff = datetime.utcnow() - timedelta(days=90)
    accounts_needing_change = (
        db.query(User).filter(User.password_changed_at < old_password_cutoff).count()
    )

    return SecurityAuditSummary(
        total_users=total_users,
        locked_accounts=locked_accounts,
        recent_login_failures=recent_failures,
        recent_password_changes=recent_password_changes,
        weak_passwords_detected=0,  # Would require password strength analysis
        accounts_requiring_password_change=accounts_needing_change,
        summary_period_days=days,
    )


@router.post("/force-password-reset/{user_id}")
async def force_password_reset(
    user_id: int,
    temporary_password_length: int = 16,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """
    Administratively reset a user's password to a temporary password.
    Requires admin role.
    """
    target_user = crud_user.get_user(db, user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Generate secure temporary password
    import secrets
    import string

    # Ensure password meets complexity requirements
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    temp_password = "".join(
        secrets.choice(alphabet) for _ in range(temporary_password_length)
    )

    # Ensure it meets requirements by construction
    if temporary_password_length >= 12:
        temp_password = (
            secrets.choice(string.ascii_uppercase)
            + secrets.choice(string.ascii_lowercase)
            + secrets.choice(string.digits)
            + secrets.choice("!@#$%^&*")
            + "".join(
                secrets.choice(alphabet) for _ in range(temporary_password_length - 4)
            )
        )

    # Update password
    target_user.password_hash = get_password_hash(temp_password)
    target_user.password_changed_at = datetime.utcnow()

    # Clear password history to allow any new password
    target_user.password_history = json.dumps([])

    # Reset any lockout status
    target_user.failed_login_attempts = 0
    target_user.last_failed_login = None
    target_user.account_locked_until = None

    db.add(target_user)
    db.commit()

    # Log the password reset
    log_audit_event(
        event_type="PASSWORD_RESET_ADMIN",
        outcome="SUCCESS",
        details={
            "target_user_id": user_id,
            "target_email": target_user.email,
            "reset_by": current_user.user_id,
            "reset_at": datetime.utcnow().isoformat(),
        },
    )

    return {
        "message": f"Password reset for {target_user.email}",
        "temporary_password": temp_password,
        "user_must_change_on_login": True,
    }
