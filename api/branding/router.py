"""
Branding API Router

This module implements API endpoints for office branding customization,
including logo URLs and color schemes with proper HIPAA compliance.
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

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
from api.core.audit_logger import log_audit_event
import logging
from api.core.config import RoleType

logger = logging.getLogger(__name__)

router = APIRouter()

# Define role groups for branding operations
BRANDING_MODIFY_ROLES = [RoleType.ADMIN, RoleType.CHIROPRACTOR]
BRANDING_VIEW_ROLES = [RoleType.ADMIN, RoleType.CHIROPRACTOR, RoleType.OFFICE_MANAGER]
ADMIN_ONLY_ROLES = [RoleType.ADMIN]


def check_office_access(current_user: User, office_id: int) -> None:
    """
    Check if user has access to the specified office.
    Admins can access any office, others can only access their own.

    Raises HTTPException if access is denied.
    """
    if (
        current_user.role.name != RoleType.ADMIN.value
        and current_user.office_id != office_id
    ):
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
    """
    # Check office access permission
    check_office_access(current_user, office_id)

    try:
        effective_branding = crud_branding.get_effective_branding(
            db=db, office_id=office_id
        )

        return BrandingResponseWithDefaults(**effective_branding)

    except Exception as e:
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
