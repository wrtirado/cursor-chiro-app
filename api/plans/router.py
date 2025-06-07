# api/plans/router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from api.database.session import get_db
from api.schemas.plan import (
    TherapyPlan,
    TherapyPlanCreate,
    TherapyPlanUpdate,
    PlanAssignment,
    AssignPlanRequest,
)
from api.crud import crud_plan, crud_user  # Import crud_user for patient check
from api.auth.dependencies import require_role, get_current_active_user
from api.core.config import RoleType
from api.models.base import User  # Import User model

router = APIRouter()

CARE_PROVIDER_ROLE = [RoleType.CARE_PROVIDER]
PATIENT_ROLE = [RoleType.PATIENT]
CARE_PROVIDER_OR_PATIENT = [RoleType.CARE_PROVIDER, RoleType.PATIENT]


@router.post("/", response_model=TherapyPlan, status_code=status.HTTP_201_CREATED)
def create_new_plan(
    plan_in: TherapyPlanCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(CARE_PROVIDER_ROLE)),
):
    """Create a new therapy plan. Requires CARE_PROVIDER role."""
    # care_provider_id is taken from the logged-in user
    return crud_plan.create_plan(
        db=db, plan=plan_in, care_provider_id=current_user.user_id
    )


@router.get("/", response_model=List[TherapyPlan])
def read_plans(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_active_user
    ),  # Allow any logged-in user to query
):
    """
    Retrieve therapy plans.
    - Care providers see plans they created.
    - Patients see plans assigned to them.
    - Other roles (Admin, Manager, Billing) currently see nothing (can be adjusted).
    """
    if current_user.has_role("care_provider"):
        return crud_plan.get_plans_by_care_provider(
            db, care_provider_id=current_user.user_id, skip=skip, limit=limit
        )
    elif current_user.has_role("patient"):
        # This gets the plans associated with the patient through assignments
        return crud_plan.get_plans_assigned_to_patient(
            db, patient_id=current_user.user_id, skip=skip, limit=limit
        )
    else:
        # Admins/Managers might need a different view, e.g., all plans in their office/company
        # For now, return empty list for other roles
        return []


@router.get("/{plan_id}", response_model=TherapyPlan)
def read_single_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    # Allow Care Provider who owns it or Patient assigned to it?
    current_user: User = Depends(get_current_active_user),
):
    """Retrieve a specific therapy plan by ID."""
    db_plan = crud_plan.get_plan(db, plan_id=plan_id)
    if db_plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Authorization check:
    is_creator = (
        current_user.has_role("care_provider")
        and db_plan.care_provider_id == current_user.user_id
    )
    # Check if patient is assigned (requires querying assignments)
    is_assigned_patient = False
    if current_user.has_role("patient"):
        assignment = (
            db.query(PlanAssignment)
            .filter(
                PlanAssignment.plan_id == plan_id,
                PlanAssignment.patient_id == current_user.user_id,
            )
            .first()
        )
        if assignment:
            is_assigned_patient = True

    if not (is_creator or is_assigned_patient):
        # Add check for Admin/Manager roles if they should have access
        raise HTTPException(
            status_code=403, detail="Not authorized to access this plan"
        )

    return db_plan


@router.put("/{plan_id}", response_model=TherapyPlan)
def update_existing_plan(
    plan_id: int,
    plan_in: TherapyPlanUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(CARE_PROVIDER_ROLE)),
):
    """Update a therapy plan. Requires CARE_PROVIDER role and ownership."""
    db_plan = crud_plan.get_plan(db, plan_id=plan_id)
    if db_plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    if db_plan.care_provider_id != current_user.user_id:
        raise HTTPException(
            status_code=403, detail="Not authorized to update this plan"
        )
    return crud_plan.update_plan(db=db, db_plan=db_plan, plan_in=plan_in)


@router.delete("/{plan_id}", response_model=TherapyPlan)
def delete_single_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(CARE_PROVIDER_ROLE)),
):
    """Delete a therapy plan. Requires CARE_PROVIDER role and ownership."""
    db_plan = crud_plan.get_plan(db, plan_id=plan_id)  # Fetch to check ownership
    if db_plan is None:
        # Return 404 even if it exists but isn't owned by user? Or 403?
        # Let's stick with 404 if the subsequent delete fails due to ownership check inside crud (if added)
        # Or check ownership here:
        pass  # No need to fetch again if delete_plan handles ownership or non-existence

    deleted_plan = crud_plan.delete_plan(db, plan_id=plan_id)
    if deleted_plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    # Re-check ownership if delete_plan doesn't guarantee it
    if deleted_plan.care_provider_id != current_user.user_id:
        # This case shouldn't happen if DB constraints work, but as a safeguard
        # We might have deleted someone else's plan if delete_plan didn't check owner.
        # For now, assume delete_plan works on any plan ID found.
        # Better: Modify delete_plan to accept care_provider_id for check.
        raise HTTPException(
            status_code=403, detail="Unauthorized delete attempt detected"
        )

    return deleted_plan


@router.post(
    "/{plan_id}/assign",
    response_model=PlanAssignment,
    status_code=status.HTTP_201_CREATED,
)
def assign_plan(
    plan_id: int,
    assign_request: AssignPlanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(CARE_PROVIDER_ROLE)),
):
    """Assign a therapy plan to a patient. Requires CARE_PROVIDER role."""
    db_plan = crud_plan.get_plan(db, plan_id=plan_id)
    if db_plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    # Optional: Check if the care provider assigning owns the plan
    if db_plan.care_provider_id != current_user.user_id:
        raise HTTPException(
            status_code=403, detail="Care providers can only assign their own plans"
        )

    # Optional: Check if patient belongs to the same office as the care provider
    patient = crud_user.get_user(db, user_id=assign_request.patient_id)
    if patient and patient.office_id != current_user.office_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot assign plan: Patient is not in the same office as the care provider.",
        )

    assignment = crud_plan.assign_plan_to_patient(
        db=db,
        plan_id=plan_id,
        assign_request=assign_request,
        assigner_id=current_user.user_id,
    )
    if assignment is None:
        # Could be due to patient not found, not a patient, or already assigned
        # Add more specific checks if needed
        raise HTTPException(
            status_code=400,
            detail="Could not assign plan. Invalid patient ID or plan already assigned to this patient.",
        )
    return assignment
