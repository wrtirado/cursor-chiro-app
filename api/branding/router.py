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

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/branding", response_model=BrandingResponse)
def create_branding(
    *,
    db: Session = Depends(get_db),
    branding_in: BrandingCreate,
    current_user: User = Depends(get_current_user),
) -> BrandingResponse:
    """
    Create custom branding for an office.

    Requires admin or chiropractor role.
    """
    # Check if user has permission to modify branding for this office
    if current_user.role.name not in ["admin", "chiropractor"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and chiropractors can create branding",
        )

    # For non-admin users, ensure they can only modify their own office
    if (
        current_user.role.name != "admin"
        and current_user.office_id != branding_in.office_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create branding for your own office",
        )

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


@router.put("/branding/{office_id}", response_model=BrandingResponse)
def update_branding(
    *,
    db: Session = Depends(get_db),
    office_id: int,
    branding_in: BrandingUpdate,
    current_user: User = Depends(get_current_user),
) -> BrandingResponse:
    """
    Update or create branding for an office.

    This endpoint uses upsert logic - if branding doesn't exist, it creates it.
    Requires admin or chiropractor role.
    """
    # Check permissions
    if current_user.role.name not in ["admin", "chiropractor"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and chiropractors can update branding",
        )

    # For non-admin users, ensure they can only modify their own office
    if current_user.role.name != "admin" and current_user.office_id != office_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update branding for your own office",
        )

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


@router.get("/branding/{office_id}", response_model=BrandingResponseWithDefaults)
def get_branding(
    *,
    db: Session = Depends(get_db),
    office_id: int,
    current_user: User = Depends(get_current_user),
) -> BrandingResponseWithDefaults:
    """
    Get effective branding for an office with default fallbacks.

    Returns the custom branding if it exists, otherwise returns default branding.
    Requires authenticated user.
    """
    # For non-admin users, ensure they can only view their own office
    if current_user.role.name != "admin" and current_user.office_id != office_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view branding for your own office",
        )

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


@router.get("/branding/{office_id}/raw", response_model=Optional[BrandingResponse])
def get_raw_branding(
    *,
    db: Session = Depends(get_db),
    office_id: int,
    current_user: User = Depends(get_current_user),
) -> Optional[BrandingResponse]:
    """
    Get raw custom branding for an office (without defaults).

    Returns None if no custom branding exists.
    Requires admin role for security.
    """
    if current_user.role.name != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view raw branding data",
        )

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


@router.delete("/branding/{office_id}")
def delete_branding(
    *,
    db: Session = Depends(get_db),
    office_id: int,
    current_user: User = Depends(get_current_user),
) -> Dict[str, str]:
    """
    Delete custom branding for an office.

    After deletion, the office will use default branding.
    Requires admin or chiropractor role.
    """
    # Check permissions
    if current_user.role.name not in ["admin", "chiropractor"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and chiropractors can delete branding",
        )

    # For non-admin users, ensure they can only modify their own office
    if current_user.role.name != "admin" and current_user.office_id != office_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete branding for your own office",
        )

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
