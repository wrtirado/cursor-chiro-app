"""
Branding API Router

This module implements API endpoints for office branding customization,
including logo URLs and color schemes with proper HIPAA compliance.
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from sqlalchemy.orm import Session
import io
import uuid
import logging

from api.database.session import get_db
from api.auth.dependencies import get_current_user, require_role
from api.models.base import User
from api.schemas.branding import (
    BrandingCreate,
    BrandingUpdate,
    BrandingResponse,
    BrandingResponseWithDefaults,
)
from api.crud.crud_branding import crud_branding
from api.core.audit_logger import log_audit_event, AuditEvent
from api.core.config import RoleType
from api.core import s3_client

logger = logging.getLogger(__name__)

router = APIRouter()

# Define role groups for branding operations
BRANDING_MODIFY_ROLES = [RoleType.ADMIN, RoleType.CARE_PROVIDER]
BRANDING_VIEW_ROLES = [RoleType.ADMIN, RoleType.CARE_PROVIDER, RoleType.OFFICE_MANAGER]
ADMIN_ONLY_ROLES = [RoleType.ADMIN]

# Define allowed logo content types for security
ALLOWED_LOGO_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}

# Maximum file size for logo uploads (2MB)
MAX_LOGO_FILE_SIZE = 2 * 1024 * 1024  # 2MB in bytes


def check_office_access(current_user: User, office_id: int) -> None:
    """
    Check if the current user has access to branding for the specified office.

    Admins can access any office.
    Other users can only access their own office's branding.

    Raises HTTPException if access is denied.
    """
    if not current_user.has_role("admin") and current_user.office_id != office_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access branding for your own office",
        )


@router.post("/", response_model=BrandingResponse)
def create_branding(
    *,
    db: Session = Depends(get_db),
    branding_in: BrandingCreate,
    current_user: User = Depends(require_role(BRANDING_MODIFY_ROLES)),
) -> BrandingResponse:
    """
    Create custom branding for an office.

    Requires admin or chiropractor role.
    """
    # Check office access permission
    check_office_access(current_user, branding_in.office_id)

    try:
        branding = crud_branding.create(
            db=db, obj_in=branding_in, user_id=current_user.user_id
        )

        logger.info(
            f"User {current_user.user_id} created branding for office {branding_in.office_id}"
        )

        return BrandingResponse.from_orm(branding)

    except ValueError as e:
        # Handle specific business logic errors
        if "already exists" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            )
        elif "not found" in str(e):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
    except Exception as e:
        logger.error(f"Error creating branding: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while creating branding",
        )


@router.put("/{office_id}", response_model=BrandingResponse)
def update_branding(
    *,
    db: Session = Depends(get_db),
    office_id: int,
    branding_in: BrandingUpdate,
    current_user: User = Depends(require_role(BRANDING_MODIFY_ROLES)),
) -> BrandingResponse:
    """
    Update or create branding for an office.

    This endpoint uses upsert logic - if branding doesn't exist, it creates it.
    Requires admin or chiropractor role.
    """
    # Check office access permission
    check_office_access(current_user, office_id)

    try:
        branding = crud_branding.create_or_update(
            db=db, office_id=office_id, obj_in=branding_in, user_id=current_user.user_id
        )

        logger.info(
            f"User {current_user.user_id} updated branding for office {office_id}"
        )

        return BrandingResponse.from_orm(branding)

    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
    except Exception as e:
        logger.error(f"Error updating branding for office {office_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while updating branding",
        )


@router.get("/{office_id}", response_model=BrandingResponseWithDefaults)
def get_branding(
    *,
    db: Session = Depends(get_db),
    office_id: int,
    current_user: User = Depends(require_role(BRANDING_VIEW_ROLES)),
) -> BrandingResponseWithDefaults:
    """
    Get effective branding for an office with default fallbacks.

    Returns the custom branding if it exists, otherwise returns default branding.
    Requires authenticated user with branding view permissions.
    Implements HIPAA-compliant audit logging for all branding access.
    """
    # Check office access permission
    check_office_access(current_user, office_id)

    try:
        effective_branding = crud_branding.get_effective_branding(
            db=db, office_id=office_id
        )

        # Audit branding access for HIPAA compliance
        log_audit_event(
            user=current_user,
            event_type=AuditEvent.BRANDING_VIEWED,
            outcome="SUCCESS",
            resource_type="branding",
            resource_id=office_id,
            details={
                "office_id": office_id,
                "has_custom_logo": effective_branding.get("has_custom_logo", False),
                "has_custom_colors": effective_branding.get("has_custom_colors", False),
                "access_type": "effective_branding",
            },
        )

        return BrandingResponseWithDefaults(**effective_branding)

    except Exception as e:
        # Audit failed access
        log_audit_event(
            user=current_user,
            event_type=AuditEvent.BRANDING_VIEWED,
            outcome="FAILURE",
            resource_type="branding",
            resource_id=office_id,
            details={
                "office_id": office_id,
                "error": "Failed to retrieve branding",
                "error_details": str(e),
            },
        )
        logger.error(f"Error getting branding for office {office_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while retrieving branding",
        )


@router.get("/{office_id}/raw", response_model=Optional[BrandingResponse])
def get_raw_branding(
    *,
    db: Session = Depends(get_db),
    office_id: int,
    current_user: User = Depends(require_role(ADMIN_ONLY_ROLES)),
) -> Optional[BrandingResponse]:
    """
    Get raw custom branding for an office (without defaults).

    Returns None if no custom branding exists.
    Requires admin role for security.
    """
    # Admins can access any office, so no additional check needed

    try:
        branding = crud_branding.get_by_office_id(db=db, office_id=office_id)

        if branding:
            return BrandingResponse.from_orm(branding)
        return None

    except Exception as e:
        logger.error(f"Error getting raw branding for office {office_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while retrieving raw branding",
        )


@router.delete("/{office_id}")
def delete_branding(
    *,
    db: Session = Depends(get_db),
    office_id: int,
    current_user: User = Depends(require_role(BRANDING_MODIFY_ROLES)),
) -> Dict[str, str]:
    """
    Delete custom branding for an office.

    After deletion, the office will use default branding.
    Requires admin or chiropractor role.
    """
    # Check office access permission
    check_office_access(current_user, office_id)

    try:
        branding = crud_branding.get_by_office_id(db=db, office_id=office_id)

        if not branding:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No custom branding found for office {office_id}",
            )

        crud_branding.remove(
            db=db, branding_id=branding.branding_id, user_id=current_user.user_id
        )

        logger.info(
            f"User {current_user.user_id} deleted branding for office {office_id}"
        )

        return {"message": f"Branding deleted for office {office_id}"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting branding for office {office_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while deleting branding",
        )


@router.post("/logo/{office_id}", response_model=Dict[str, str])
async def upload_logo(
    *,
    office_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(BRANDING_MODIFY_ROLES)),
) -> Dict[str, str]:
    """
    Upload a secure logo file for branding.

    Implements HIPAA-compliant file handling with:
    - File type validation
    - Size restrictions
    - Secure storage with encryption
    - Comprehensive audit logging
    """
    try:
        # Check office access permissions
        check_office_access(current_user, office_id)

        # Validate file is provided
        if not file:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="No logo file provided"
            )

        # Validate file content type
        if file.content_type not in ALLOWED_LOGO_CONTENT_TYPES:
            log_audit_event(
                user=current_user,
                event_type=AuditEvent.MEDIA_UPLOAD,
                outcome="FAILURE",
                resource_type="branding_logo",
                resource_id=office_id,
                details={
                    "office_id": office_id,
                    "error": "Invalid file type",
                    "attempted_type": file.content_type,
                    "allowed_types": list(ALLOWED_LOGO_CONTENT_TYPES.keys()),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_LOGO_CONTENT_TYPES.keys())}",
            )

        # Read and validate file size
        file_content = await file.read()
        file_size = len(file_content)

        if file_size > MAX_LOGO_FILE_SIZE:
            log_audit_event(
                user=current_user,
                event_type=AuditEvent.MEDIA_UPLOAD,
                outcome="FAILURE",
                resource_type="branding_logo",
                resource_id=office_id,
                details={
                    "office_id": office_id,
                    "error": "File too large",
                    "file_size": file_size,
                    "max_size": MAX_LOGO_FILE_SIZE,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size: {MAX_LOGO_FILE_SIZE // (1024*1024)}MB",
            )

        # Generate secure object name with office context
        file_extension = ALLOWED_LOGO_CONTENT_TYPES[file.content_type]
        object_name = f"branding/office_{office_id}/logo_{uuid.uuid4()}{file_extension}"

        # Create file stream for upload
        file_stream = io.BytesIO(file_content)

        # Upload to secure storage with encryption
        uploaded_object_name = s3_client.upload_file_to_s3(
            file_stream=file_stream,
            object_name=object_name,
            content_type=file.content_type,
        )

        if not uploaded_object_name:
            log_audit_event(
                user=current_user,
                event_type=AuditEvent.MEDIA_UPLOAD,
                outcome="FAILURE",
                resource_type="branding_logo",
                resource_id=office_id,
                details={
                    "office_id": office_id,
                    "error": "Storage upload failed",
                    "object_name": object_name,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload logo to secure storage",
            )

        # Generate secure access URL
        logo_url = f"/api/v1/branding/logo-url/{uploaded_object_name}"

        # Audit successful upload
        log_audit_event(
            user=current_user,
            event_type=AuditEvent.MEDIA_UPLOAD,
            outcome="SUCCESS",
            resource_type="branding_logo",
            resource_id=office_id,
            details={
                "office_id": office_id,
                "object_name": uploaded_object_name,
                "file_size": file_size,
                "file_type": file.content_type,
                "secure_path": object_name,
            },
        )

        logger.info(
            f"Successfully uploaded logo for office {office_id} by user {current_user.user_id}"
        )

        return {
            "object_name": uploaded_object_name,
            "logo_url": logo_url,
            "message": "Logo uploaded successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error uploading logo for office {office_id}: {e}")
        log_audit_event(
            user=current_user,
            event_type=AuditEvent.MEDIA_UPLOAD,
            outcome="FAILURE",
            resource_type="branding_logo",
            resource_id=office_id,
            details={
                "office_id": office_id,
                "error": "Unexpected error",
                "error_details": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during logo upload",
        )
    finally:
        await file.close()


@router.get("/logo-url/{object_name:path}")
def get_secure_logo_url(
    object_name: str,
    current_user: User = Depends(require_role(BRANDING_VIEW_ROLES)),
) -> Dict[str, str]:
    """
    Generate a secure, time-limited URL for accessing a branding logo.

    Implements HIPAA-compliant access controls with:
    - Authentication requirement
    - Path traversal protection
    - Audit logging of access
    - Time-limited URLs
    """
    try:
        # Validate object name for security
        if (
            not object_name
            or ".." in object_name
            or not object_name.startswith("branding/")
        ):
            log_audit_event(
                user=current_user,
                event_type=AuditEvent.AUTHORIZATION_FAILURE,
                outcome="FAILURE",
                resource_type="branding_logo",
                details={
                    "error": "Invalid object name",
                    "attempted_path": object_name,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid logo path"
            )

        # Extract office ID from path for access control
        try:
            # Expected format: branding/office_{office_id}/logo_uuid.ext
            path_parts = object_name.split("/")
            if len(path_parts) >= 2 and path_parts[1].startswith("office_"):
                office_id = int(path_parts[1].replace("office_", ""))
                # Check if user has access to this office's branding
                check_office_access(current_user, office_id)
            else:
                # Allow admins to access any logo, others need office context
                if not current_user.has_role("admin"):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied to logo resource",
                    )
        except (ValueError, IndexError):
            # If we can't parse office ID, only allow admin access
            if not current_user.has_role("admin"):
                log_audit_event(
                    user=current_user,
                    event_type=AuditEvent.AUTHORIZATION_FAILURE,
                    outcome="FAILURE",
                    resource_type="branding_logo",
                    details={
                        "error": "Cannot determine office access",
                        "object_name": object_name,
                    },
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to logo resource",
                )

        # Generate secure presigned URL
        presigned_url = s3_client.get_presigned_url_for_s3_object(
            object_name=object_name, expiry_hours=1  # Short expiration for security
        )

        if not presigned_url:
            log_audit_event(
                user=current_user,
                event_type=AuditEvent.MEDIA_DOWNLOAD,
                outcome="FAILURE",
                resource_type="branding_logo",
                details={
                    "error": "Could not generate secure URL",
                    "object_name": object_name,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Logo not found or could not generate secure access URL",
            )

        # Audit successful access
        log_audit_event(
            user=current_user,
            event_type=AuditEvent.MEDIA_DOWNLOAD,
            outcome="SUCCESS",
            resource_type="branding_logo",
            details={
                "object_name": object_name,
                "expiry_hours": 1,
            },
        )

        return {"url": presigned_url}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error generating logo URL for {object_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not generate secure logo URL",
        )
