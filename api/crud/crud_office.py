from sqlalchemy.orm import Session, joinedload
from typing import Optional, List
from enum import Enum  # Import Enum for isinstance check

from api.models.base import Office, User  # Import User
from api.schemas.office import (
    OfficeCreate,
    OfficeUpdate,
    SubscriptionStatus,
)  # Import SubscriptionStatus Enum
from api.crud.crud_user import get_user  # Import get_user
from api.core.config import RoleType  # Import RoleType

# Imports for audit logging
from api.schemas.audit import BillingAuditLogCreate
from api.crud.crud_audit import create_billing_audit_log_entry


def get_office(db: Session, office_id: int) -> Optional[Office]:
    return db.query(Office).filter(Office.office_id == office_id).first()


def get_offices_by_company(
    db: Session, company_id: int, skip: int = 0, limit: int = 100
) -> List[Office]:
    return (
        db.query(Office)
        .filter(Office.company_id == company_id)
        .offset(skip)
        .limit(limit)
        .all()
    )


def create_office(db: Session, office: OfficeCreate, company_id: int) -> Office:
    db_office = Office(**office.dict(), company_id=company_id)
    # Potentially log initial subscription status here if applicable
    # For example, if office.subscription_status is set by OfficeCreate schema default
    # create_billing_audit_log_entry(
    #     db=db,
    #     log_entry_in=BillingAuditLogCreate(
    #         event_type="SUBSCRIPTION_INITIALIZED",
    #         outcome="SUCCESS",
    #         details={"status": db_office.subscription_status, "initial_company_id": company_id}
    #     ),
    #     office_id=db_office.office_id, # This needs db_office to be created first or assign after commit
    #     user_id=None # Assuming system action or user_id passed in
    # )
    # For now, focusing on update. Initial log can be added if office_id is available post-creation before return.
    db.add(db_office)
    db.commit()
    db.refresh(db_office)

    # Log initial subscription status after office is created and has an ID
    if db_office.subscription_status:
        create_billing_audit_log_entry(
            db=db,
            log_entry_in=BillingAuditLogCreate(
                event_type="SUBSCRIPTION_INITIALIZED",
                office_id=db_office.office_id,
                outcome="SUCCESS",
                source="OFFICE_CREATION_ENDPOINT",
                details={
                    "status": db_office.subscription_status,
                    "company_id": company_id,
                },
            ),
            office_id=db_office.office_id,
            user_id=None,
        )

    return db_office


def update_office(
    db: Session,
    db_office: Office,  # SQLAlchemy model instance (current state from DB)
    office_in: OfficeUpdate,  # Pydantic model with updates from request
    current_user_id: Optional[int] = None,
) -> Office:
    office_data = office_in.model_dump(exclude_unset=True)  # Fields from request
    changed_fields = {}  # To store actual changes

    # Iterate through fields provided in the request (office_data)
    for key, new_value_from_request in office_data.items():
        if hasattr(db_office, key):
            current_db_value = getattr(db_office, key)

            is_different = False
            if key == "subscription_status":
                # Ensure comparison is between string representations or enum vs enum value
                # current_db_value is a string. new_value_from_request is SubscriptionStatus enum.
                is_different = str(current_db_value) != str(
                    new_value_from_request.value
                    if isinstance(new_value_from_request, Enum)
                    else new_value_from_request
                )
            else:
                is_different = current_db_value != new_value_from_request

            if is_different:
                # Store the original DB value and the new value from the request
                changed_fields[key] = {
                    "old": current_db_value,
                    "new": new_value_from_request,
                }

            # Apply the update to the SQLAlchemy model instance
            # If new_value is an enum (like SubscriptionStatus), its .value should be stored if the DB column is String
            if (
                isinstance(new_value_from_request, Enum)
                and key == "subscription_status"
            ):  # Be specific for subscription_status
                setattr(db_office, key, new_value_from_request.value)
            else:
                setattr(db_office, key, new_value_from_request)

    if changed_fields:  # Only commit if there were actual changes to persist
        db.add(db_office)  # Mark db_office as dirty
        db.commit()  # Persist changes to DB
        db.refresh(db_office)  # Refresh db_office with its state from DB

    # Audit logging for subscription_status change
    if "subscription_status" in changed_fields:
        old_status_val = changed_fields["subscription_status"][
            "old"
        ]  # This was the string from DB
        new_status_enum_member = changed_fields["subscription_status"][
            "new"
        ]  # This was the Enum member from request

        create_billing_audit_log_entry(
            db=db,
            log_entry_in=BillingAuditLogCreate(
                event_type="SUBSCRIPTION_STATUS_CHANGED",
                office_id=db_office.office_id,  # office_id of the office being updated
                outcome="SUCCESS",
                source="OFFICE_UPDATE_ENDPOINT",
                details={
                    "old_status": str(old_status_val),
                    "new_status": str(
                        new_status_enum_member.value
                        if isinstance(new_status_enum_member, Enum)
                        else new_status_enum_member
                    ),
                    "changed_by_user_id": current_user_id,
                },
            ),
            office_id=db_office.office_id,  # Pass to CRUD function signature
            user_id=current_user_id,
        )
    return db_office


def delete_office(db: Session, office_id: int) -> Optional[Office]:
    db_office = db.query(Office).filter(Office.office_id == office_id).first()
    if db_office:
        db.delete(db_office)
        db.commit()
    return db_office


def assign_manager_to_office(
    db: Session, db_office: Office, manager_user_id: int
) -> Optional[Office]:
    """Assigns a user with the Office Manager role to an office."""
    manager = get_user(db, user_id=manager_user_id)

    if not manager:
        return None  # Manager user not found

    # Verify the user has the correct role (e.g., OFFICE_MANAGER)
    # This assumes manager.role relationship is loaded or accessible
    if not manager.role or manager.role.name != RoleType.OFFICE_MANAGER.value:
        return None  # User is not an office manager

    # Check if manager is already assigned to this or another office (optional, depending on rules)
    # if manager.office_id is not None and manager.office_id != db_office.office_id:
    #     return None # Manager already assigned elsewhere

    # Assign the manager to the office by setting their office_id
    manager.office_id = db_office.office_id
    db.add(manager)
    # We don't strictly need to commit here if the calling endpoint commits,
    # but doing it here makes the function self-contained.
    db.commit()
    db.refresh(manager)
    db.refresh(db_office)  # Refresh office to reflect relationship changes if needed

    return db_office
