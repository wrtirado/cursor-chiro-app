from sqlalchemy.orm import Session
from typing import Optional, List
from fastapi import HTTPException, status
from datetime import datetime

from api.models.base import User
from api.schemas.user import UserCreate, UserUpdate, UserBillingStatusUpdate
from api.core.security import get_password_hash, verify_password
from api.core.utils import generate_random_code
from api.core.config import RoleType
from api.core.audit_logger import log_billing_event

# Import billing service for automatic billing integration
try:
    from api.services.billing_service import billing_service

    BILLING_SERVICE_AVAILABLE = True
except ImportError:
    BILLING_SERVICE_AVAILABLE = False
    billing_service = None


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


def get_user(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.user_id == user_id).first()


def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    return db.query(User).offset(skip).limit(limit).all()


def get_user_by_join_code(db: Session, join_code: str) -> Optional[User]:
    # Ensure join_code is not None or empty before querying
    if not join_code:
        return None
    return db.query(User).filter(User.join_code == join_code).first()


def create_user(db: Session, user: UserCreate) -> User:
    hashed_password = get_password_hash(user.password)
    db_user = User(
        email=user.email,
        name=user.name,
        password_hash=hashed_password,
        role_id=user.role_id,
        office_id=user.office_id,
    )

    # Generate join code only for care providers initially
    # We need to fetch the Role object or compare role_id if we know the ID mapping
    # Assuming role_id 2 corresponds to care_provider based on our init_schema.sql INSERT order
    # A better way would be to query the Role table or use the RoleType enum if role_id is predictable
    temp_care_provider_role_id = 2  # Fragile: Assumes ID from seed
    if user.role_id == temp_care_provider_role_id:
        while True:
            join_code = generate_random_code()
            existing_user = get_user_by_join_code(db, join_code)
            if not existing_user:
                db_user.join_code = join_code
                break

    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user(db: Session, db_user: User, user_in: UserUpdate) -> User:
    user_data = user_in.dict(exclude_unset=True)

    # Handle password update with current password validation
    if "password" in user_data and user_data["password"]:
        if "current_password" not in user_data or not user_data["current_password"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is required to set a new password.",
            )

        if not verify_password(user_data["current_password"], db_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,  # Or 400? Let's use 401 for incorrect credentials
                detail="Incorrect current password.",
            )

        # If current password is correct, hash the new password
        hashed_password = get_password_hash(user_data["password"])
        db_user.password_hash = hashed_password

        # Remove password fields from user_data dictionary so they aren't processed below
        del user_data["password"]
        del user_data["current_password"]
    elif "current_password" in user_data:
        # Prevent setting current_password if new password isn't provided
        del user_data["current_password"]

    # Update remaining fields
    for key, value in user_data.items():
        setattr(db_user, key, value)

    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def delete_user(db: Session, user_id: int) -> Optional[User]:
    db_user = db.query(User).filter(User.user_id == user_id).first()
    if db_user:
        db.delete(db_user)
        db.commit()
    return db_user


# Function to associate a user (patient) using a join code - Placeholder for logic
def associate_user_with_care_provider(
    db: Session, patient: User, care_provider: User
) -> User:
    # Logic to link patient to care_provider/office based on care_provider's info
    # This might involve updating patient's office_id or creating a linking record
    # depending on the exact association model.
    # For now, let's assume we link the patient to the care_provider's office
    if care_provider.office_id:
        patient.office_id = care_provider.office_id
        db.add(patient)
        db.commit()
        db.refresh(patient)
    return patient


# Billing status operations
def update_user_billing_status(
    db: Session,
    user_id: int,
    billing_status: UserBillingStatusUpdate,
    admin_user_id: int,
) -> User:
    """Update user billing status with audit logging"""
    db_user = get_user(db, user_id)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Store original billing status for audit
    original_status = {
        "is_active_for_billing": db_user.is_active_for_billing,
        "activated_at": db_user.activated_at,
        "deactivated_at": db_user.deactivated_at,
        "last_billed_cycle": db_user.last_billed_cycle,
    }

    # Update billing status fields
    billing_data = billing_status.dict()
    for key, value in billing_data.items():
        if hasattr(db_user, key):
            setattr(db_user, key, value)

    # Log the billing status change
    log_billing_event(
        action="user_billing_status_updated",
        office_id=db_user.office_id,
        user_id=admin_user_id,
        patient_id=user_id,
        details={
            "original_status": original_status,
            "new_status": billing_data,
            "user_name": db_user.name,
            "user_email": db_user.email,
        },
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def activate_user_for_billing(db: Session, user_id: int, admin_user_id: int) -> User:
    """Activate a user for billing with automatic billing logic integration"""
    if BILLING_SERVICE_AVAILABLE and billing_service:
        # Use the comprehensive billing service
        try:
            billing_result = billing_service.activate_patient_for_billing(
                db=db,
                patient_id=user_id,
                admin_user_id=admin_user_id,
            )

            # Return the updated user
            return db.query(User).filter(User.user_id == user_id).first()

        except Exception as e:
            # Fall back to basic activation if billing service fails
            log_billing_event(
                action="billing_service_fallback",
                user_id=admin_user_id,
                patient_id=user_id,
                details={
                    "error": str(e),
                    "fallback_reason": "billing_service_activation_failed",
                },
            )
            # Continue with basic activation below

    # Basic activation without billing service (fallback)
    billing_status = UserBillingStatusUpdate(
        is_active_for_billing=True, activated_at=datetime.utcnow()
    )
    return update_user_billing_status(db, user_id, billing_status, admin_user_id)


def deactivate_user_for_billing(db: Session, user_id: int, admin_user_id: int) -> User:
    """Deactivate a user for billing with automatic billing logic integration"""
    if BILLING_SERVICE_AVAILABLE and billing_service:
        # Use the comprehensive billing service
        try:
            billing_result = billing_service.deactivate_patient_for_billing(
                db=db,
                patient_id=user_id,
                admin_user_id=admin_user_id,
                reason="manual_deactivation",
            )

            # Return the updated user
            return db.query(User).filter(User.user_id == user_id).first()

        except Exception as e:
            # Fall back to basic deactivation if billing service fails
            log_billing_event(
                action="billing_service_fallback",
                user_id=admin_user_id,
                patient_id=user_id,
                details={
                    "error": str(e),
                    "fallback_reason": "billing_service_deactivation_failed",
                },
            )
            # Continue with basic deactivation below

    # Basic deactivation without billing service (fallback)
    billing_status = UserBillingStatusUpdate(
        is_active_for_billing=False, deactivated_at=datetime.utcnow()
    )
    return update_user_billing_status(db, user_id, billing_status, admin_user_id)


def get_active_patients_for_billing(
    db: Session, office_id: Optional[int] = None
) -> List[User]:
    """Get all users/patients who are active for billing"""
    query = db.query(User).filter(User.is_active_for_billing == True)

    if office_id:
        query = query.filter(User.office_id == office_id)

    return query.all()


def get_patients_activated_since(
    db: Session, since_date: datetime, office_id: Optional[int] = None
) -> List[User]:
    """Get patients activated since a specific date"""
    query = db.query(User).filter(
        User.is_active_for_billing == True, User.activated_at >= since_date
    )

    if office_id:
        query = query.filter(User.office_id == office_id)

    return query.all()


def get_patients_needing_billing(
    db: Session, billing_cycle_start: datetime, office_id: Optional[int] = None
) -> List[User]:
    """Get patients who need to be billed for the current cycle"""
    query = db.query(User).filter(
        User.is_active_for_billing == True,
        # Either never billed or last billed before this cycle
        (
            User.last_billed_cycle.is_(None)
            | (User.last_billed_cycle < billing_cycle_start)
        ),
    )

    if office_id:
        query = query.filter(User.office_id == office_id)

    return query.all()


def update_last_billed_cycle(
    db: Session, user_ids: List[int], billing_cycle_date: datetime, admin_user_id: int
) -> int:
    """Update last_billed_cycle for multiple users and return count updated"""
    updated_count = 0

    for user_id in user_ids:
        db_user = get_user(db, user_id)
        if db_user:
            original_date = db_user.last_billed_cycle
            db_user.last_billed_cycle = billing_cycle_date

            # Log the billing cycle update
            log_billing_event(
                action="user_billed_cycle_updated",
                office_id=db_user.office_id,
                user_id=admin_user_id,
                patient_id=user_id,
                details={
                    "previous_billing_cycle": (
                        original_date.isoformat() if original_date else None
                    ),
                    "new_billing_cycle": billing_cycle_date.isoformat(),
                    "user_name": db_user.name,
                },
            )

            db.add(db_user)
            updated_count += 1

    db.commit()
    return updated_count
