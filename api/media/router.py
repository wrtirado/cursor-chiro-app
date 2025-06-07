# api/media/router.py
import io
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from sqlalchemy.orm import Session
from typing import List

from api.database.session import get_db
from api.core import s3_client
from api.auth.dependencies import require_role, get_current_active_user
from api.core.config import RoleType, settings
from api.schemas.media import MediaMetadata, MediaUploadResponse
from api.models.base import User
from api.services.media_service import upload_media, get_media_metadata

router = APIRouter()

# Define allowed roles (e.g., Care Providers can upload media for plans)
CARE_PROVIDER_ROLE = [RoleType.CARE_PROVIDER]

# Define allowed content types
ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",  # Example
    # Add other allowed types
}


@router.post(
    "/upload", response_model=MediaUploadResponse, status_code=status.HTTP_201_CREATED
)
def upload_plan_media(
    file: UploadFile = File(...),
    plan_id: int = None,  # Optional plan association
    exercise_id: int = None,  # Optional exercise association
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(CARE_PROVIDER_ROLE)),
):
    """
    Upload media (image/video) for therapy plans or exercises.
    Requires CARE_PROVIDER role.
    """
    # Implementation here would use the media service
    # This is a placeholder for the media upload logic

    # Validate file type and size
    allowed_types = ["image/jpeg", "image/png", "video/mp4", "video/avi"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {file.content_type} not allowed. Allowed types: {allowed_types}",
        )

    # Upload using media service
    try:
        media_url = upload_media(file, plan_id, exercise_id, current_user.user_id)
        return MediaUploadResponse(
            url=media_url,
            plan_id=plan_id,
            exercise_id=exercise_id,
            uploaded_by=current_user.user_id,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}",
        )


@router.get("/url/{object_name:path}")
def get_media_url(
    object_name: str,
    current_user: User = Depends(get_current_active_user),  # Require logged-in user
):
    """
    Generates a pre-signed URL for accessing a media file.
    Requires authentication.
    `object_name` should include the path within the bucket (e.g., 'exercises/uuid.jpg').
    """
    # Basic check to prevent accessing unexpected paths
    if not object_name or ".." in object_name:
        raise HTTPException(status_code=400, detail="Invalid object name")

    try:
        presigned_url = s3_client.get_presigned_url_for_s3_object(
            object_name=object_name
        )

        if not presigned_url:
            # Could be object not found or S3 error
            raise HTTPException(
                status_code=404,
                detail="Could not generate URL for object, it may not exist.",
            )

        return {"url": presigned_url}
    except HTTPException as http_exc:
        # Re-raise HTTPExceptions from s3_client initialization
        raise http_exc
    except Exception as e:
        print(f"Error generating presigned URL: {e}")  # Replace with proper logging
        raise HTTPException(
            status_code=500, detail="Could not generate URL for object."
        )
