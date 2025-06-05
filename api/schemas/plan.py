# api/schemas/plan.py
from pydantic import BaseModel, Field
from typing import Optional, List
import datetime

# --- PlanExercise Schemas ---


class PlanExerciseBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    instructions: Optional[str] = None
    sequence_order: int = Field(..., gt=0)
    image_url: Optional[str] = None  # URLs added in Task 7
    video_url: Optional[str] = None  # URLs added in Task 7


class PlanExerciseCreate(PlanExerciseBase):
    pass  # No extra fields needed for creation from base


class PlanExerciseUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    instructions: Optional[str] = None
    sequence_order: Optional[int] = Field(None, gt=0)
    image_url: Optional[str] = None
    video_url: Optional[str] = None


class PlanExerciseInDBBase(PlanExerciseBase):
    plan_exercise_id: int
    plan_id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True


class PlanExercise(PlanExerciseInDBBase):
    pass


# --- TherapyPlan Schemas ---


class TherapyPlanBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class TherapyPlanCreate(TherapyPlanBase):
    exercises: List[PlanExerciseCreate] = []  # Allow creating exercises with the plan


class TherapyPlanUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    # Note: Updating exercises might require separate endpoints or more complex logic
    # For simplicity, this update schema doesn't directly handle exercise updates.
    # Consider adding/updating/deleting exercises via dedicated endpoints or a more complex payload.


class TherapyPlanInDBBase(TherapyPlanBase):
    plan_id: int
    care_provider_id: int  # Updated from chiropractor_id to care_provider_id
    version: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True


class TherapyPlan(TherapyPlanInDBBase):
    # Include exercises when returning a plan
    exercises: List[PlanExercise] = []


# --- PlanAssignment Schemas ---


class PlanAssignmentBase(BaseModel):
    patient_id: int
    start_date: Optional[datetime.date] = None
    end_date: Optional[datetime.date] = None


class PlanAssignmentCreate(PlanAssignmentBase):
    plan_id: int  # Required during creation via endpoint


class PlanAssignmentUpdate(BaseModel):
    # What can be updated? Maybe only dates?
    start_date: Optional[datetime.date] = None
    end_date: Optional[datetime.date] = None


class PlanAssignmentInDBBase(PlanAssignmentBase):
    assignment_id: int
    plan_id: int
    assigned_by_id: Optional[int] = None  # User ID of assigner
    assigned_at: datetime.datetime

    class Config:
        from_attributes = True


class PlanAssignment(PlanAssignmentInDBBase):
    # Optionally include plan details or patient details if needed
    plan: Optional[TherapyPlan] = None
    # patient: Optional[User] = None # Requires User schema import
    pass


# Schema specifically for the POST /plans/{id}/assign endpoint
class AssignPlanRequest(BaseModel):
    patient_id: int
    start_date: Optional[datetime.date] = None
    end_date: Optional[datetime.date] = None
