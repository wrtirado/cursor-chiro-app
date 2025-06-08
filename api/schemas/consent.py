"""
Pydantic schemas for consent records for HIPAA compliance.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ConsentStatus(str, Enum):
    """Valid consent status values."""

    GRANTED = "granted"
    REVOKED = "revoked"
    EXPIRED = "expired"


class ConsentType(str, Enum):
    """Common consent types for healthcare applications."""

    TREATMENT = "treatment"
    DATA_SHARING = "data_sharing"
    MARKETING = "marketing"
    RESEARCH = "research"
    THIRD_PARTY_COMMUNICATION = "third_party_communication"
    BILLING_COMMUNICATION = "billing_communication"
    APPOINTMENT_REMINDERS = "appointment_reminders"


# Base schema for consent records
class ConsentRecordBase(BaseModel):
    consent_type: str = Field(..., description="Type of consent being tracked")
    consent_text: str = Field(..., description="Full text of the consent agreement")
    purpose: str = Field(..., description="Purpose for which consent is being obtained")
    scope: Optional[str] = Field(
        None, description="Scope or limitations of the consent"
    )
    expiry_date: Optional[datetime] = Field(
        None, description="When the consent expires (if applicable)"
    )
    third_party_sharing_allowed: bool = Field(
        default=False, description="Whether third-party sharing is allowed"
    )
    third_party_entities: Optional[List[str]] = Field(
        default=None, description="List of authorized third-party entities"
    )


# Schema for creating new consent records
class ConsentRecordCreate(ConsentRecordBase):
    patient_id: int = Field(..., description="ID of the patient granting consent")
    consent_version: int = Field(
        default=1, description="Version of the consent agreement"
    )

    @validator("consent_type")
    def validate_consent_type(cls, v):
        """Validate consent type is not empty."""
        if not v or not v.strip():
            raise ValueError("Consent type cannot be empty")
        return v.strip()

    @validator("consent_text")
    def validate_consent_text(cls, v):
        """Validate consent text is substantial."""
        if not v or len(v.strip()) < 10:
            raise ValueError("Consent text must be at least 10 characters long")
        return v.strip()

    @validator("purpose")
    def validate_purpose(cls, v):
        """Validate purpose is not empty."""
        if not v or not v.strip():
            raise ValueError("Purpose cannot be empty")
        return v.strip()


# Schema for updating consent records (mainly for revocation)
class ConsentRecordUpdate(BaseModel):
    status: Optional[ConsentStatus] = None
    revoked_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    scope: Optional[str] = None


# Schema for consent record responses
class ConsentRecordResponse(ConsentRecordBase):
    consent_id: int
    patient_id: int
    consent_version: int
    status: ConsentStatus
    granted_date: datetime
    granted_by_id: int
    revoked_date: Optional[datetime] = None
    revoked_by_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    # Computed field
    is_active: bool = Field(..., description="Whether the consent is currently active")

    class Config:
        from_attributes = True


# Schema for consent revocation requests
class ConsentRevocationRequest(BaseModel):
    consent_id: int = Field(..., description="ID of the consent to revoke")
    reason: Optional[str] = Field(None, description="Reason for revoking consent")


# Schema for bulk consent operations
class BulkConsentRequest(BaseModel):
    patient_id: int = Field(..., description="ID of the patient")
    consents: List[ConsentRecordCreate] = Field(
        ..., description="List of consents to create"
    )


# Schema for consent search/filtering
class ConsentSearchFilters(BaseModel):
    patient_id: Optional[int] = None
    consent_type: Optional[str] = None
    status: Optional[ConsentStatus] = None
    granted_after: Optional[datetime] = None
    granted_before: Optional[datetime] = None
    expires_after: Optional[datetime] = None
    expires_before: Optional[datetime] = None
    third_party_sharing_allowed: Optional[bool] = None


# Schema for consent summary (for patient dashboards)
class ConsentSummary(BaseModel):
    consent_type: str
    status: ConsentStatus
    granted_date: datetime
    expiry_date: Optional[datetime]
    is_active: bool
    third_party_sharing_allowed: bool

    class Config:
        from_attributes = True


# Schema for patient consent overview
class PatientConsentOverview(BaseModel):
    patient_id: int
    total_consents: int
    active_consents: int
    revoked_consents: int
    expired_consents: int
    consent_summary: List[ConsentSummary]
