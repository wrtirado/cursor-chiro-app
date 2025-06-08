"""
SQLAlchemy model for the consent_records table for HIPAA compliance.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Text,
    ForeignKey,
    Boolean,
    CheckConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from typing import Optional
import json

from api.database.session import Base


class ConsentRecord(Base):
    """
    Consent record model for HIPAA-compliant consent tracking.

    This table stores all patient consent records for regulatory compliance,
    providing a comprehensive audit trail of consent grants, revocations, and updates.

    Supports:
    - Consent versioning for tracking changes over time
    - Multiple consent types (treatment, data sharing, marketing, etc.)
    - Third-party sharing permissions with entity tracking
    - Automatic expiration and revocation handling
    """

    __tablename__ = "consent_records"

    consent_id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    consent_type = Column(String(255), nullable=False, index=True)
    consent_version = Column(Integer, nullable=False, default=1)
    consent_text = Column(Text, nullable=False)
    purpose = Column(Text, nullable=False)
    scope = Column(Text)

    # Consent status and timing
    status = Column(String(50), nullable=False, default="granted", index=True)
    granted_date = Column(DateTime, nullable=False, default=func.now(), index=True)
    granted_by_id = Column(
        Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=False
    )
    revoked_date = Column(DateTime)
    revoked_by_id = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"))
    expiry_date = Column(DateTime, index=True)

    # Third party sharing permissions
    third_party_sharing_allowed = Column(Boolean, nullable=False, default=False)
    third_party_entities = Column(Text)  # JSON string for list of entities

    # Audit fields
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    patient = relationship(
        "User", foreign_keys=[patient_id], back_populates="consent_records"
    )
    granted_by = relationship("User", foreign_keys=[granted_by_id])
    revoked_by = relationship("User", foreign_keys=[revoked_by_id])

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('granted', 'revoked', 'expired')", name="check_consent_status"
        ),
    )

    @property
    def is_active(self) -> bool:
        """Check if the consent is currently active (granted and not expired)."""
        from datetime import datetime

        if self.status != "granted":
            return False

        if self.expiry_date and self.expiry_date <= datetime.now():
            return False

        return True

    @property
    def third_party_entities_list(self) -> list:
        """Get the list of third-party entities as a Python list."""
        if not self.third_party_entities:
            return []
        try:
            return json.loads(self.third_party_entities)
        except (json.JSONDecodeError, TypeError):
            return []

    @third_party_entities_list.setter
    def third_party_entities_list(self, entities: list):
        """Set the third-party entities list as JSON string."""
        if entities:
            self.third_party_entities = json.dumps(entities)
        else:
            self.third_party_entities = None

    def revoke_consent(self, revoked_by_user_id: int) -> None:
        """Revoke this consent record."""
        from datetime import datetime

        self.status = "revoked"
        self.revoked_date = datetime.now()
        self.revoked_by_id = revoked_by_user_id

    def expire_consent(self) -> None:
        """Mark this consent as expired."""
        self.status = "expired"

    def __repr__(self):
        return (
            f"<ConsentRecord(consent_id={self.consent_id}, "
            f"patient_id={self.patient_id}, "
            f"consent_type='{self.consent_type}', "
            f"status='{self.status}', "
            f"granted_date='{self.granted_date}')>"
        )
