"""
FastAPI endpoints for consent management (HIPAA compliance).
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from api.database.session import get_db
from api.auth.dependencies import get_current_user, require_role
from api.models.base import User
from api.crud import crud_consent
from api.schemas import consent
from api.core.audit_logger import log_consent_event

router = APIRouter(prefix="/consent", tags=["consent"])


@router.post("/", response_model=consent.ConsentRecordResponse)
def create_consent_record(
    consent_data: consent.ConsentRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "provider", "staff"])),
):
    """
    Create a new consent record for a patient.

    Requires admin, provider, or staff role.
    """
    try:
        # Verify the patient exists
        patient = db.query(User).filter(User.user_id == consent_data.patient_id).first()
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found"
            )

        # Create the consent record
        consent_record = crud_consent.create_consent_record(
            db, consent_data, current_user.user_id
        )

        # Log audit event
        log_consent_event(
            action="create_consent",
            user_id=current_user.user_id,
            patient_id=consent_data.patient_id,
            consent_id=consent_record.consent_id,
            consent_type=consent_data.consent_type,
            details={
                "purpose": consent_data.purpose,
                "third_party_sharing_allowed": consent_data.third_party_sharing_allowed,
            },
        )

        return consent_record

    except Exception as e:
        # Log error audit event
        log_consent_event(
            action="create_consent_failed",
            user_id=current_user.user_id,
            patient_id=consent_data.patient_id,
            consent_type=consent_data.consent_type,
            details={"error": str(e)},
            outcome="FAILURE",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating consent record: {str(e)}",
        )


@router.get("/{consent_id}", response_model=consent.ConsentRecordResponse)
def get_consent_record(
    consent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "provider", "staff"])),
):
    """
    Get a specific consent record by ID.

    Requires admin, provider, or staff role.
    """
    consent_record = crud_consent.get_consent_record(db, consent_id)
    if not consent_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Consent record not found"
        )

    # Log audit event
    log_consent_event(
        action="view_consent",
        user_id=current_user.user_id,
        patient_id=consent_record.patient_id,
        consent_id=consent_id,
        consent_type=consent_record.consent_type,
    )

    return consent_record


@router.get("/patient/{patient_id}", response_model=List[consent.ConsentRecordResponse])
def get_patient_consents(
    patient_id: int,
    status: Optional[consent.ConsentStatus] = None,
    consent_type: Optional[str] = None,
    active_only: bool = Query(False, description="Return only active consents"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "provider", "staff"])),
):
    """
    Get all consent records for a specific patient.

    Requires admin, provider, or staff role.
    """
    # Verify the patient exists
    patient = db.query(User).filter(User.user_id == patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found"
        )

    consents = crud_consent.get_consent_records_by_patient(
        db, patient_id, status, consent_type, active_only
    )

    # Log audit event
    log_consent_event(
        action="view_patient_consents",
        user_id=current_user.user_id,
        patient_id=patient_id,
        details={
            "filters": {
                "status": status.value if status else None,
                "consent_type": consent_type,
                "active_only": active_only,
            },
            "records_count": len(consents),
        },
    )

    return consents


@router.put("/{consent_id}/revoke", response_model=consent.ConsentRecordResponse)
def revoke_consent(
    consent_id: int,
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "provider", "staff"])),
):
    """
    Revoke a specific consent record.

    Requires admin, provider, or staff role.
    """
    consent_record = crud_consent.revoke_consent_record(
        db, consent_id, current_user.user_id
    )

    if not consent_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Consent record not found"
        )

    # Log audit event
    log_consent_event(
        action="revoke_consent",
        user_id=current_user.user_id,
        patient_id=consent_record.patient_id,
        consent_id=consent_id,
        consent_type=consent_record.consent_type,
        details={"reason": reason},
    )

    return consent_record


@router.put(
    "/patient/{patient_id}/revoke-type/{consent_type}",
    response_model=List[consent.ConsentRecordResponse],
)
def revoke_consents_by_type(
    patient_id: int,
    consent_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "provider", "staff"])),
):
    """
    Revoke all active consents of a specific type for a patient.

    Requires admin, provider, or staff role.
    """
    # Verify the patient exists
    patient = db.query(User).filter(User.user_id == patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found"
        )

    revoked_consents = crud_consent.revoke_consents_by_type(
        db, patient_id, consent_type, current_user.user_id
    )

    # Log audit event
    log_consent_event(
        action="revoke_consents_by_type",
        user_id=current_user.user_id,
        patient_id=patient_id,
        consent_type=consent_type,
        details={"revoked_count": len(revoked_consents)},
    )

    return revoked_consents


@router.get(
    "/patient/{patient_id}/overview", response_model=consent.PatientConsentOverview
)
def get_patient_consent_overview(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "provider", "staff"])),
):
    """
    Get a comprehensive overview of all consents for a patient.

    Requires admin, provider, or staff role.
    """
    # Verify the patient exists
    patient = db.query(User).filter(User.user_id == patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found"
        )

    overview = crud_consent.get_patient_consent_overview(db, patient_id)

    # Log audit event
    log_consent_event(
        action="view_consent_overview",
        user_id=current_user.user_id,
        patient_id=patient_id,
        details={
            "total_consents": overview.total_consents,
            "active_consents": overview.active_consents,
        },
    )

    return overview


@router.get("/patient/{patient_id}/check/{consent_type}")
def check_patient_consent(
    patient_id: int,
    consent_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "provider", "staff"])),
):
    """
    Check if a patient has active consent for a specific type.

    Returns {"has_consent": bool, "consent_record": ConsentRecordResponse|null}

    Requires admin, provider, or staff role.
    """
    # Verify the patient exists
    patient = db.query(User).filter(User.user_id == patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found"
        )

    has_consent = crud_consent.check_patient_consent(db, patient_id, consent_type)
    consent_record = None

    if has_consent:
        consent_record = crud_consent.get_active_consent_by_type(
            db, patient_id, consent_type
        )

    # Log audit event
    log_consent_event(
        action="check_patient_consent",
        user_id=current_user.user_id,
        patient_id=patient_id,
        consent_type=consent_type,
        details={"has_consent": has_consent},
    )

    return {"has_consent": has_consent, "consent_record": consent_record}


@router.post("/search", response_model=List[consent.ConsentRecordResponse])
def search_consent_records(
    filters: consent.ConsentSearchFilters,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "provider"])),
):
    """
    Search consent records with advanced filtering.

    Requires admin or provider role.
    """
    consents = crud_consent.search_consent_records(db, filters, skip, limit)

    # Log audit event
    log_consent_event(
        action="search_consents",
        user_id=current_user.user_id,
        details={
            "filters": filters.dict(exclude_unset=True),
            "skip": skip,
            "limit": limit,
            "results_count": len(consents),
        },
    )

    return consents


@router.post("/bulk", response_model=List[consent.ConsentRecordResponse])
def bulk_create_consents(
    bulk_request: consent.BulkConsentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "provider"])),
):
    """
    Create multiple consent records for a patient in a single transaction.

    Requires admin or provider role.
    """
    try:
        # Verify the patient exists
        patient = db.query(User).filter(User.user_id == bulk_request.patient_id).first()
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found"
            )

        consents = crud_consent.bulk_create_consents(
            db, bulk_request.consents, current_user.user_id
        )

        # Log audit event
        log_consent_event(
            action="bulk_create_consents",
            user_id=current_user.user_id,
            patient_id=bulk_request.patient_id,
            details={
                "consents_created": len(consents),
                "consent_types": [c.consent_type for c in bulk_request.consents],
            },
        )

        return consents

    except Exception as e:
        # Log error audit event
        log_consent_event(
            action="bulk_create_consents_failed",
            user_id=current_user.user_id,
            patient_id=bulk_request.patient_id,
            details={
                "error": str(e),
                "consents_attempted": len(bulk_request.consents),
            },
            outcome="FAILURE",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating consent records: {str(e)}",
        )


@router.get("/expiring", response_model=List[consent.ConsentRecordResponse])
def get_expiring_consents(
    days_ahead: int = Query(
        30, ge=1, le=365, description="Days ahead to check for expiring consents"
    ),
    office_id: Optional[int] = Query(None, description="Filter by office ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "provider"])),
):
    """
    Get consents that are expiring soon.

    Requires admin or provider role.
    """
    consents = crud_consent.get_consents_expiring_soon(db, days_ahead, office_id)

    # Log audit event
    log_consent_event(
        action="view_expiring_consents",
        user_id=current_user.user_id,
        details={
            "days_ahead": days_ahead,
            "office_id": office_id,
            "expiring_count": len(consents),
        },
    )

    return consents


@router.post("/expire-old", response_model=dict)
def expire_old_consents(
    db: Session = Depends(get_db), current_user: User = Depends(require_role(["admin"]))
):
    """
    Mark expired consents as expired (admin maintenance function).

    Requires admin role.
    """
    expired_count = crud_consent.expire_old_consents(db)

    # Log audit event
    log_consent_event(
        action="expire_old_consents",
        user_id=current_user.user_id,
        details={"expired_count": expired_count},
    )

    return {"expired_count": expired_count}
