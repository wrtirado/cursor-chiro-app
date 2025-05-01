# api/media/router.py
import io
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from sqlalchemy.orm import Session

from api.database.session import get_db
from api.core import s3_client
from api.auth.dependencies import require_role, get_current_active_user
from api.core.config import RoleType
from api.models.base import User

router = APIRouter()

# Define allowed roles (e.g., Chiropractors can upload media for plans)
UPLOAD_ROLES = [RoleType.CHIROPRACTOR]

# Define allowed content types
ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov" # Example
    # Add other allowed types
}

@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_media(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UPLOAD_ROLES))
):
    """
    Uploads an image or video file to S3/MinIO storage.
    Requires CHIROPRACTOR role.
    Returns the object name (path) of the uploaded file in the bucket.
    """
    if not file:
        raise HTTPException(status_code=400, detail="No file provided")

    # Validate content type
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_CONTENT_TYPES.keys())}"
        )

    # Generate a unique object name (e.g., using UUID)
    file_extension = ALLOWED_CONTENT_TYPES[file.content_type]
    object_name = f"exercises/{uuid.uuid4()}{file_extension}"

    try:
        # Read file content into a BytesIO stream
        file_content = await file.read()
        file_stream = io.BytesIO(file_content)

        # Upload using the s3_client utility
        uploaded_object_name = s3_client.upload_file_to_s3(
            file_stream=file_stream,
            object_name=object_name,
            content_type=file.content_type
        )

        if not uploaded_object_name:
            raise HTTPException(status_code=500, detail="Failed to upload file to storage.")

        # Return the object name (path) - the client can construct the full URL or request presigned URLs
        # Or potentially return a presigned URL directly?
        # Let's return the object name for now, as URLs might be stored in DB
        return {"object_name": uploaded_object_name}

    except Exception as e:
        # Log the exception details
        print(f"Error during file upload: {e}") # Replace with proper logging
        raise HTTPException(status_code=500, detail="An error occurred during file upload.")
    finally:
        await file.close()

@router.get("/url/{object_name:path}")
def get_media_url(
    object_name: str,
    current_user: User = Depends(get_current_active_user) # Require logged-in user
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
        presigned_url = s3_client.get_presigned_url_for_s3_object(object_name=object_name)

        if not presigned_url:
            # Could be object not found or S3 error
            raise HTTPException(status_code=404, detail="Could not generate URL for object, it may not exist.")

        return {"url": presigned_url}
    except HTTPException as http_exc:
        # Re-raise HTTPExceptions from s3_client initialization
        raise http_exc
    except Exception as e:
        print(f"Error generating presigned URL: {e}") # Replace with proper logging
        raise HTTPException(status_code=500, detail="Could not generate URL for object.") 