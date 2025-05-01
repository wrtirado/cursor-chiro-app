from sqlalchemy.orm import Session
from typing import List, Optional

from api.models.base import Progress, PlanAssignment, User, PlanExercise
from api.schemas.progress import ProgressUpdateItem
from api.core.config import RoleType # Import RoleType

def upsert_progress_batch(db: Session, progress_updates: List[ProgressUpdateItem], patient_id: int) -> List[Progress]:
    """
    Updates or creates progress records for a given patient based on a batch of updates.
    Ensures the assignment belongs to the specified patient.
    Returns the list of upserted Progress records.
    """
    upserted_progress_records = []
    assignment_ids = {item.assignment_id for item in progress_updates}

    # Verify all assignments belong to the current patient to prevent unauthorized updates
    valid_assignments = db.query(PlanAssignment.assignment_id).filter(
        PlanAssignment.assignment_id.in_(assignment_ids),
        PlanAssignment.patient_id == patient_id
    ).all()
    valid_assignment_ids = {a.assignment_id for a in valid_assignments}

    if len(valid_assignment_ids) != len(assignment_ids):
        # Find the invalid ones for a better error message if needed
        invalid_ids = assignment_ids - valid_assignment_ids
        print(f"Warning/Error: Attempt to update progress for assignments not belonging to patient {patient_id}. Invalid assignment IDs: {invalid_ids}")
        # Decide handling: raise exception, skip invalid, etc. Let's skip for now.
        # raise ValueError(f"Invalid assignment IDs provided for patient {patient_id}")

    for item in progress_updates:
        if item.assignment_id not in valid_assignment_ids:
            print(f"Skipping progress update for assignment {item.assignment_id} (invalid for patient {patient_id})")
            continue

        # Check if the exercise exists for the given assignment (optional but good practice)
        # This requires joining PlanAssignment and PlanExercise - potentially complex query
        # Simple check: Assume exercise ID is valid if assignment is valid for now.

        # Try to find existing progress record
        db_progress = db.query(Progress).filter(
            Progress.assignment_id == item.assignment_id,
            Progress.plan_exercise_id == item.plan_exercise_id
        ).first()

        if db_progress:
            # Update existing record
            db_progress.completed_at = item.completed_at
            db_progress.notes = item.notes
        else:
            # Create new progress record
            db_progress = Progress(
                assignment_id=item.assignment_id,
                plan_exercise_id=item.plan_exercise_id,
                completed_at=item.completed_at,
                notes=item.notes
            )
            db.add(db_progress)

        upserted_progress_records.append(db_progress)

    db.commit()
    # Refresh objects to get updated state/IDs
    for record in upserted_progress_records:
        if record in db.new or record in db.dirty:
             db.refresh(record)

    return upserted_progress_records

def get_progress_for_patient(db: Session, patient_id: int) -> List[Progress]:
    """Retrieves all progress records for a specific patient."""
    return (
        db.query(Progress)
        .join(Progress.assignment) # Join Progress -> PlanAssignment
        .filter(PlanAssignment.patient_id == patient_id)
        # Optionally join further to get exercise details or plan details
        # .options(joinedload(Progress.exercise))
        .order_by(Progress.assignment_id, Progress.plan_exercise_id) # Consistent ordering
        .all()
    ) 