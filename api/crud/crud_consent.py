"""
CRUD operations for consent records for HIPAA compliance.
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from api.models.consent_record import ConsentRecord
from api.models.base import User
from api.schemas.consent import (
    ConsentRecordCreate,
    ConsentRecordUpdate,
    ConsentSearchFilters,
    ConsentStatus,
    PatientConsentOverview,
    ConsentSummary,
)


def create_consent_record(
    db: Session, consent_data: ConsentRecordCreate, granted_by_user_id: int
) -> ConsentRecord:
    """Create a new consent record."""
    # Convert third_party_entities list to JSON string if provided
    third_party_entities = None
    if consent_data.third_party_entities:
        import json

        third_party_entities = json.dumps(consent_data.third_party_entities)

    consent_record = ConsentRecord(
        patient_id=consent_data.patient_id,
        consent_type=consent_data.consent_type,
        consent_version=consent_data.consent_version,
        consent_text=consent_data.consent_text,
        purpose=consent_data.purpose,
        scope=consent_data.scope,
        granted_by_id=granted_by_user_id,
        expiry_date=consent_data.expiry_date,
        third_party_sharing_allowed=consent_data.third_party_sharing_allowed,
        third_party_entities=third_party_entities,
    )

    db.add(consent_record)
    db.commit()
    db.refresh(consent_record)
    return consent_record


def get_consent_record(db: Session, consent_id: int) -> Optional[ConsentRecord]:
    """Get a consent record by ID."""
    return (
        db.query(ConsentRecord).filter(ConsentRecord.consent_id == consent_id).first()
    )


def get_consent_records_by_patient(
    db: Session,
    patient_id: int,
    status: Optional[ConsentStatus] = None,
    consent_type: Optional[str] = None,
    active_only: bool = False,
) -> List[ConsentRecord]:
    """Get all consent records for a specific patient."""
    query = db.query(ConsentRecord).filter(ConsentRecord.patient_id == patient_id)

    if status:
        query = query.filter(ConsentRecord.status == status.value)

    if consent_type:
        query = query.filter(ConsentRecord.consent_type == consent_type)

    if active_only:
        query = query.filter(
            and_(
                ConsentRecord.status == "granted",
                or_(
                    ConsentRecord.expiry_date.is_(None),
                    ConsentRecord.expiry_date > datetime.now(),
                ),
            )
        )

    return query.order_by(desc(ConsentRecord.granted_date)).all()


def search_consent_records(
    db: Session, filters: ConsentSearchFilters, skip: int = 0, limit: int = 100
) -> List[ConsentRecord]:
    """Search consent records with filtering."""
    query = db.query(ConsentRecord)

    if filters.patient_id:
        query = query.filter(ConsentRecord.patient_id == filters.patient_id)

    if filters.consent_type:
        query = query.filter(ConsentRecord.consent_type == filters.consent_type)

    if filters.status:
        query = query.filter(ConsentRecord.status == filters.status.value)

    if filters.granted_after:
        query = query.filter(ConsentRecord.granted_date >= filters.granted_after)

    if filters.granted_before:
        query = query.filter(ConsentRecord.granted_date <= filters.granted_before)

    if filters.expires_after:
        query = query.filter(ConsentRecord.expiry_date >= filters.expires_after)

    if filters.expires_before:
        query = query.filter(ConsentRecord.expiry_date <= filters.expires_before)

    if filters.third_party_sharing_allowed is not None:
        query = query.filter(
            ConsentRecord.third_party_sharing_allowed
            == filters.third_party_sharing_allowed
        )

    return (
        query.order_by(desc(ConsentRecord.granted_date)).offset(skip).limit(limit).all()
    )


def update_consent_record(
    db: Session, consent_id: int, consent_update: ConsentRecordUpdate
) -> Optional[ConsentRecord]:
    """Update a consent record."""
    consent_record = get_consent_record(db, consent_id)
    if not consent_record:
        return None

    update_data = consent_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(consent_record, field, value)

    db.commit()
    db.refresh(consent_record)
    return consent_record


def revoke_consent_record(
    db: Session, consent_id: int, revoked_by_user_id: int
) -> Optional[ConsentRecord]:
    """Revoke a specific consent record."""
    consent_record = get_consent_record(db, consent_id)
    if not consent_record:
        return None

    consent_record.revoke_consent(revoked_by_user_id)
    db.commit()
    db.refresh(consent_record)
    return consent_record


def revoke_consents_by_type(
    db: Session, patient_id: int, consent_type: str, revoked_by_user_id: int
) -> List[ConsentRecord]:
    """Revoke all active consents of a specific type for a patient."""
    active_consents = (
        db.query(ConsentRecord)
        .filter(
            and_(
                ConsentRecord.patient_id == patient_id,
                ConsentRecord.consent_type == consent_type,
                ConsentRecord.status == "granted",
            )
        )
        .all()
    )

    revoked_consents = []
    for consent in active_consents:
        consent.revoke_consent(revoked_by_user_id)
        revoked_consents.append(consent)

    db.commit()
    return revoked_consents


def expire_old_consents(db: Session) -> int:
    """Mark expired consents as expired. Returns count of expired consents."""
    expired_consents = (
        db.query(ConsentRecord)
        .filter(
            and_(
                ConsentRecord.status == "granted",
                ConsentRecord.expiry_date.isnot(None),
                ConsentRecord.expiry_date <= datetime.now(),
            )
        )
        .all()
    )

    count = 0
    for consent in expired_consents:
        consent.expire_consent()
        count += 1

    db.commit()
    return count


def get_active_consent_by_type(
    db: Session, patient_id: int, consent_type: str
) -> Optional[ConsentRecord]:
    """Get the most recent active consent of a specific type for a patient."""
    return (
        db.query(ConsentRecord)
        .filter(
            and_(
                ConsentRecord.patient_id == patient_id,
                ConsentRecord.consent_type == consent_type,
                ConsentRecord.status == "granted",
                or_(
                    ConsentRecord.expiry_date.is_(None),
                    ConsentRecord.expiry_date > datetime.now(),
                ),
            )
        )
        .order_by(desc(ConsentRecord.granted_date))
        .first()
    )


def check_patient_consent(db: Session, patient_id: int, consent_type: str) -> bool:
    """Check if a patient has active consent for a specific type."""
    active_consent = get_active_consent_by_type(db, patient_id, consent_type)
    return active_consent is not None


def get_patient_consent_overview(
    db: Session, patient_id: int
) -> PatientConsentOverview:
    """Get a comprehensive overview of all consents for a patient."""
    all_consents = get_consent_records_by_patient(db, patient_id)

    total_consents = len(all_consents)
    active_consents = len([c for c in all_consents if c.is_active])
    revoked_consents = len([c for c in all_consents if c.status == "revoked"])
    expired_consents = len([c for c in all_consents if c.status == "expired"])

    # Create consent summaries
    consent_summaries = []
    for consent in all_consents:
        summary = ConsentSummary(
            consent_type=consent.consent_type,
            status=consent.status,
            granted_date=consent.granted_date,
            expiry_date=consent.expiry_date,
            is_active=consent.is_active,
            third_party_sharing_allowed=consent.third_party_sharing_allowed,
        )
        consent_summaries.append(summary)

    return PatientConsentOverview(
        patient_id=patient_id,
        total_consents=total_consents,
        active_consents=active_consents,
        revoked_consents=revoked_consents,
        expired_consents=expired_consents,
        consent_summary=consent_summaries,
    )


def get_consents_expiring_soon(
    db: Session, days_ahead: int = 30, office_id: Optional[int] = None
) -> List[ConsentRecord]:
    """Get consents that are expiring within the specified number of days."""
    future_date = datetime.now() + timedelta(days=days_ahead)

    query = db.query(ConsentRecord).filter(
        and_(
            ConsentRecord.status == "granted",
            ConsentRecord.expiry_date.isnot(None),
            ConsentRecord.expiry_date <= future_date,
            ConsentRecord.expiry_date > datetime.now(),
        )
    )

    if office_id:
        query = query.join(User).filter(User.office_id == office_id)

    return query.order_by(ConsentRecord.expiry_date).all()


def bulk_create_consents(
    db: Session, consents_data: List[ConsentRecordCreate], granted_by_user_id: int
) -> List[ConsentRecord]:
    """Create multiple consent records in a single transaction."""
    created_consents = []

    for consent_data in consents_data:
        consent_record = create_consent_record(db, consent_data, granted_by_user_id)
        created_consents.append(consent_record)

    return created_consents


def delete_consent_record(db: Session, consent_id: int) -> bool:
    """Delete a consent record (use with caution - typically consents should be revoked, not deleted)."""
    consent_record = get_consent_record(db, consent_id)
    if not consent_record:
        return False

    db.delete(consent_record)
    db.commit()
    return True
