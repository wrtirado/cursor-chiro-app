import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func  # For server-side default timestamp

from api.database.session import Base  # Assuming your Base is here

# from ..database.base import Base # If used from a sub-module structure


class BillingAuditLog(Base):
    __tablename__ = "billing_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    event_type = Column(
        String(255), nullable=False, index=True
    )  # e.g., SUBSCRIPTION_CREATED, STATUS_CHANGED

    office_id = Column(
        Integer, ForeignKey("offices.office_id"), nullable=False, index=True
    )
    office = relationship(
        "Office"
    )  # Optional: if you want to navigate from log to office easily

    # user_id can be null if the action was performed by the system (e.g., automated billing)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True, index=True)
    user = relationship("User")  # Optional: if you want to navigate from log to user

    source = Column(
        String(255), nullable=True
    )  # e.g., API_ENDPOINT, WEBHOOK_STRIPE, ADMIN_PANEL
    outcome = Column(String(50), nullable=False)  # e.g., SUCCESS, FAILURE, INFO

    # JSON for flexible, structured details. Can also use Text if preferred and parse later.
    # For libSQL/SQLite, JSON is often stored as TEXT and handled by the driver/SQLAlchemy.
    details = Column(JSON, nullable=True)

    # Example of details content:
    # For STATUS_CHANGED: {"old_status": "trialing", "new_status": "active", "reason": "trial_ended"}
    # For PAYMENT_ATTEMPT: {"amount": 2900, "currency": "usd", "payment_provider_txn_id": "pi_xxx"}
    # For PAYMENT_FAILURE: {"amount": 2900, "currency": "usd", "error_message": "card_declined"}

    def __repr__(self):
        return f"<BillingAuditLog(id={self.id}, event='{self.event_type}', office_id={self.office_id}, outcome='{self.outcome}')>"


# To ensure this model is recognized by SQLAlchemy's Base and `create_all()`:
# You'll need to import this module (api.models.audit) somewhere in your application
# before `Base.metadata.create_all()` is called, typically where other models are imported,
# or ensure your `api.models.base` (or wherever Base is defined) somehow picks up models from this file.
# A simple way is to add `import api.models.audit` in your `api/models/base.py` or `api/main.py`
# where other models like `User`, `Office` are imported.
