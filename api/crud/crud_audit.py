from sqlalchemy.orm import Session

from api.models.audit import BillingAuditLog
from api.schemas.audit import BillingAuditLogCreate

# --- Billing Audit Log CRUD Operations ---


def create_billing_audit_log_entry(
    db: Session,
    log_entry_in: BillingAuditLogCreate,
    office_id: int,  # Explicitly pass office_id to ensure it's set correctly
    user_id: int | None = None,  # Optional user_id
) -> BillingAuditLog:
    """
    Create a new billing audit log entry.

    Args:
        db: SQLAlchemy database session.
        log_entry_in: Pydantic schema containing the log entry data.
                       It's expected that log_entry_in.office_id is consistent
                       with the office_id parameter passed to this function.
        office_id: The ID of the office this log entry pertains to. This will be used.
        user_id: The ID of the user who performed the action (if applicable). This will be used.

    Returns:
        The created BillingAuditLog SQLAlchemy object.
    """

    data_for_sql_model = log_entry_in.model_dump(exclude_unset=True)

    # Prioritize explicit parameters for critical foreign keys
    data_for_sql_model["office_id"] = office_id
    data_for_sql_model["user_id"] = user_id

    # If user_id is None and you prefer not to pass `user_id=None` to the model constructor,
    # you could remove it from the dictionary. However, SQLAlchemy models typically handle None for nullable fields.
    # Example: if user_id is None and 'user_id' in data_for_sql_model and data_for_sql_model['user_id'] is None:
    #     del data_for_sql_model['user_id']

    db_log_entry = BillingAuditLog(**data_for_sql_model)

    db.add(db_log_entry)
    db.commit()
    db.refresh(db_log_entry)
    return db_log_entry


# Future considerations (not for immediate implementation unless requested):
# - get_billing_audit_log_entry(db: Session, log_id: int) -> BillingAuditLog | None:
# - get_billing_audit_logs_for_office(
#       db: Session, office_id: int, skip: int = 0, limit: int = 100
#   ) -> list[BillingAuditLog]:
# - get_billing_audit_logs(
#       db: Session, skip: int = 0, limit: int = 100
#   ) -> list[BillingAuditLog]:
