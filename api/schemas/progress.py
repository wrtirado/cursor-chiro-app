# api/schemas/progress.py
from pydantic import BaseModel, Field
from typing import Optional, List
import datetime


# Schema for a single progress update item (used in batch update)
class ProgressUpdateItem(BaseModel):
    assignment_id: int
    plan_exercise_id: int
    completed_at: Optional[datetime.datetime] = (
        None  # Mark as complete (timestamp) or incomplete (null)
    )
    notes: Optional[str] = None


# Schema for the batch progress update request
class BatchProgressUpdate(BaseModel):
    updates: List[ProgressUpdateItem]


# Base schema for Progress data stored/returned
class ProgressBase(BaseModel):
    assignment_id: int
    plan_exercise_id: int
    completed_at: Optional[datetime.datetime] = None
    notes: Optional[str] = None


class ProgressInDBBase(ProgressBase):
    progress_id: int

    class Config:
        from_attributes = True


# Schema for returning Progress data
class Progress(ProgressInDBBase):
    # Optionally include related exercise or assignment info if needed
    # exercise: Optional[PlanExercise] = None # Requires PlanExercise import
    pass
