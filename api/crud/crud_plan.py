from sqlalchemy.orm import Session, joinedload, contains_eager
from typing import Optional, List

from api.models.base import TherapyPlan, PlanExercise, PlanAssignment, User
from api.schemas.plan import (
    TherapyPlanCreate,
    TherapyPlanUpdate,
    PlanExerciseCreate,
    PlanExerciseUpdate,
    PlanAssignmentCreate,
    PlanAssignmentUpdate,
    AssignPlanRequest,
)
from api.core.config import RoleType

# --- TherapyPlan CRUD --- #


def get_plan(db: Session, plan_id: int) -> Optional[TherapyPlan]:
    return (
        db.query(TherapyPlan)
        .options(joinedload(TherapyPlan.exercises))
        .filter(TherapyPlan.plan_id == plan_id)
        .first()
    )


def get_plans_by_care_provider(
    db: Session, care_provider_id: int, skip: int = 0, limit: int = 100
) -> List[TherapyPlan]:
    return (
        db.query(TherapyPlan)
        .filter(TherapyPlan.care_provider_id == care_provider_id)
        .options(joinedload(TherapyPlan.exercises))
        .order_by(TherapyPlan.updated_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_plans_assigned_to_patient(
    db: Session, patient_id: int, skip: int = 0, limit: int = 100
) -> List[TherapyPlan]:
    # This query joins Assignment -> Plan -> Exercises
    return (
        db.query(TherapyPlan)
        .join(TherapyPlan.assignments)
        .filter(PlanAssignment.patient_id == patient_id)
        .options(
            contains_eager(TherapyPlan.assignments), joinedload(TherapyPlan.exercises)
        )
        .order_by(PlanAssignment.assigned_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def create_plan(
    db: Session, plan: TherapyPlanCreate, care_provider_id: int
) -> TherapyPlan:
    db_plan = TherapyPlan(
        title=plan.title,
        description=plan.description,
        care_provider_id=care_provider_id,
    )
    db.add(db_plan)
    db.flush()  # Flush to get the db_plan.plan_id for exercises

    created_exercises = []
    for exercise_in in plan.exercises:
        db_exercise = PlanExercise(**exercise_in.dict(), plan_id=db_plan.plan_id)
        db.add(db_exercise)
        created_exercises.append(db_exercise)

    db.commit()
    db.refresh(db_plan)
    # Manually attach created exercises to the returned object if ORM config doesn't handle it
    db_plan.exercises = created_exercises
    return db_plan


def update_plan(
    db: Session, db_plan: TherapyPlan, plan_in: TherapyPlanUpdate
) -> TherapyPlan:
    plan_data = plan_in.dict(exclude_unset=True)
    # Increment version on update? Task details mention versioning.
    # Simple increment:
    db_plan.version = (db_plan.version or 0) + 1

    for key, value in plan_data.items():
        setattr(db_plan, key, value)

    db.add(db_plan)
    db.commit()
    db.refresh(db_plan)
    # Reload exercises relationship
    db.refresh(db_plan, attribute_names=["exercises"])
    return db_plan


def delete_plan(db: Session, plan_id: int) -> Optional[TherapyPlan]:
    db_plan = db.query(TherapyPlan).filter(TherapyPlan.plan_id == plan_id).first()
    if db_plan:
        db.delete(db_plan)
        db.commit()
    return db_plan


# --- PlanAssignment CRUD --- #


def assign_plan_to_patient(
    db: Session, plan_id: int, assign_request: AssignPlanRequest, assigner_id: int
) -> Optional[PlanAssignment]:
    # Check if plan exists
    db_plan = get_plan(db, plan_id)
    if not db_plan:
        return None  # Plan not found

    # Check if patient exists (requires crud_user.get_user)
    from api.crud.crud_user import get_user

    patient = get_user(db, user_id=assign_request.patient_id)
    if not patient or not patient.role or patient.role.name != RoleType.PATIENT.value:
        return None  # Patient not found or user is not a patient

    # Check if already assigned (optional, prevents duplicates if needed)
    existing_assignment = (
        db.query(PlanAssignment)
        .filter(
            PlanAssignment.plan_id == plan_id,
            PlanAssignment.patient_id == assign_request.patient_id,
        )
        .first()
    )
    if existing_assignment:
        # Decide how to handle: update dates? raise error? return existing?
        # For now, let's prevent duplicate assignments
        return None  # Or raise HTTPException in the router

    db_assignment = PlanAssignment(
        plan_id=plan_id,
        patient_id=assign_request.patient_id,
        assigned_by_id=assigner_id,
        start_date=assign_request.start_date,
        end_date=assign_request.end_date,
    )
    db.add(db_assignment)
    db.commit()
    db.refresh(db_assignment)
    return db_assignment


# --- PlanExercise CRUD (Optional - Might be handled via Plan updates/separate endpoints) --- #


# Example: Function to add an exercise to an existing plan
def add_exercise_to_plan(
    db: Session, plan_id: int, exercise: PlanExerciseCreate
) -> Optional[PlanExercise]:
    db_plan = get_plan(db, plan_id)
    if not db_plan:
        return None
    db_exercise = PlanExercise(**exercise.dict(), plan_id=plan_id)
    db.add(db_exercise)
    db.commit()
    db.refresh(db_exercise)
    return db_exercise


# Update/Delete exercise functions would follow similar patterns
