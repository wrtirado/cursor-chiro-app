import datetime
from typing import Optional, Any
from pydantic import BaseModel

# --- Billing Audit Log Schemas ---


class BillingAuditLogBase(BaseModel):
    event_type: str
    office_id: int
    user_id: Optional[int] = None
    source: Optional[str] = None
    outcome: str  # e.g., SUCCESS, FAILURE, INFO
    details: Optional[dict[str, Any]] = None

    class Config:
        # This was 'orm_mode = True' in Pydantic v1
        # For Pydantic v2, it's 'from_attributes = True'
        from_attributes = True


class BillingAuditLogCreate(BillingAuditLogBase):
    # Timestamp is usually handled by the database server_default
    # or set within the CRUD operation if needed client-side before DB.
    # For creation, we typically don't expect it from the client.
    pass


class BillingAuditLogRead(BillingAuditLogBase):
    id: int
    timestamp: datetime.datetime  # Should be present when reading from DB

    # If you have relationships defined in your SQLAlchemy model (like 'office' or 'user')
    # and want to include their data when reading audit logs, you might add them here
    # with their respective schemas, e.g.:
    # office: Optional[OfficeRead] = None # Assuming OfficeRead schema exists
    # user: Optional[UserRead] = None   # Assuming UserRead schema exists
    # This requires SQLAlchemy to be configured for eager loading or for the relationships
    # to be loaded when the audit log is fetched.


# Example usage (not part of the file content, just for illustration):
# audit_entry_data = BillingAuditLogCreate(
#     event_type="SUBSCRIPTION_STATUS_CHANGED",
#     office_id=123,
#     user_id=1, # or None if system event
#     source="API_ENDPOINT:/offices/123/status",
#     outcome="SUCCESS",
#     details={"old_status": "trialing", "new_status": "active"}
# )
