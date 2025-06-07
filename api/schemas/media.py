"""
Media-related Pydantic schemas for the care provider application.
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel


class MediaMetadata(BaseModel):
    """Schema for media metadata"""

    media_id: Optional[int] = None
    object_name: str
    content_type: str
    file_size: Optional[int] = None
    plan_id: Optional[int] = None
    exercise_id: Optional[int] = None
    uploaded_by: int
    uploaded_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MediaUploadResponse(BaseModel):
    """Schema for media upload response"""

    url: str
    plan_id: Optional[int] = None
    exercise_id: Optional[int] = None
    uploaded_by: int
    object_name: Optional[str] = None
    message: Optional[str] = None


class MediaUrlResponse(BaseModel):
    """Schema for media URL response"""

    url: str
