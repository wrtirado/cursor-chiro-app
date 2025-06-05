"""
SQLAlchemy model for the audit_logs table for HIPAA compliance.
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from api.database.session import Base


class AuditLog(Base):
    """
    Audit log model for HIPAA-compliant database logging.

    This table stores all audit events for regulatory compliance,
    providing a searchable and queryable record of all system activities.
    """

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    user_id = Column(
        Integer, ForeignKey("users.user_id", ondelete="SET NULL"), index=True
    )
    event_type = Column(String(255), nullable=False, index=True)
    resource_type = Column(String(255), index=True)
    resource_id = Column(String(255))
    outcome = Column(String(50), nullable=False, default="SUCCESS", index=True)
    source_ip = Column(String(45))  # IPv6 max length
    user_agent = Column(Text)
    request_path = Column(String(1024))
    request_method = Column(String(10))
    message = Column(Text, nullable=False)
    props = Column(Text)  # JSON string for additional structured data

    # Relationship to user (optional, nullable)
    user = relationship("User", back_populates="audit_logs")

    def __repr__(self):
        return f"<AuditLog(id={self.id}, event_type='{self.event_type}', user_id={self.user_id}, outcome='{self.outcome}')>"
