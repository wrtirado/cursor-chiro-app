# api/progress/router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from api.database.session import get_db
from api.schemas.progress import Progress, BatchProgressUpdate
from api.crud import crud_progress, crud_user # Import crud_user for patient check
from api.auth.dependencies import require_role, get_current_active_user
from api.core.config import RoleType
from api.models.base import User # Import User model

router = APIRouter()

PATIENT_ROLE = [RoleType.PATIENT]
CHIROPRACTOR_ROLE = [RoleType.CHIROPRACTOR]

@router.post("/", response_model=List[Progress], status_code=status.HTTP_200_OK)
def update_progress_batch(
    progress_in: BatchProgressUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(PATIENT_ROLE))
):
    """
    Allows a patient to submit a batch of progress updates for their assigned exercises.
    Requires PATIENT role.
    """
    try:
        # Pass the current user's ID to ensure they only update their own progress
        updated_records = crud_progress.upsert_progress_batch(
            db=db,
            progress_updates=progress_in.updates,
            patient_id=current_user.user_id
        )
        return updated_records
    except ValueError as ve:
        # Catch potential errors from CRUD if invalid data is passed
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        # Log error details
        print(f"Error during progress update: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An error occurred processing progress updates.")

@router.get("/{patient_id}", response_model=List[Progress])
def read_patient_progress(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(CHIROPRACTOR_ROLE))
):
    """
    Allows a chiropractor to view the progress records for a specific patient.
    Requires CHIROPRACTOR role.
    (Further authorization: Check if patient is in chiro's office?)
    """
    # Optional: Check if the patient exists
    patient = crud_user.get_user(db, patient_id)
    if not patient or not patient.role or patient.role.name != RoleType.PATIENT.value:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    # Optional: Authorization check - Does this chiro have access to this patient?
    # e.g., check if patient.office_id == current_user.office_id
    if patient.office_id != current_user.office_id:
         raise HTTPException(
             status_code=status.HTTP_403_FORBIDDEN,
             detail="Chiropractor does not have access to this patient's progress (different office)."
         )

    progress_records = crud_progress.get_progress_for_patient(db, patient_id=patient_id)
    return progress_records 