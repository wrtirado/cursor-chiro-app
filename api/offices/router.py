from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from api.database.session import get_db
from api.schemas.office import Office, OfficeUpdate, AssignManagerRequest
from api.crud import crud_office
from api.auth.dependencies import require_role
from api.core.config import RoleType
from api.models.base import User # Import User model

router = APIRouter()

ADMIN_ROLE = [RoleType.ADMIN]
MANAGER_ROLE = [RoleType.OFFICE_MANAGER]
ADMIN_OR_MANAGER = [RoleType.ADMIN, RoleType.OFFICE_MANAGER]

@router.get("/{office_id}", response_model=Office)
def read_single_office(
    office_id: int,
    db: Session = Depends(get_db),
    # Allow admin or the assigned office manager to view?
    current_user: User = Depends(require_role(ADMIN_OR_MANAGER))
):
    """Retrieve a specific office by ID. Requires ADMIN or Office Manager role."""
    db_office = crud_office.get_office(db, office_id=office_id)
    if db_office is None:
        raise HTTPException(status_code=404, detail="Office not found")
    # Optional: Add check if manager is requesting their own office
    # if RoleType(current_user.role.name) == RoleType.OFFICE_MANAGER and current_user.office_id != office_id:
    #     raise HTTPException(status_code=403, detail="Office manager can only view their own office")
    return db_office

@router.put("/{office_id}", response_model=Office)
def update_existing_office(
    office_id: int,
    office_in: OfficeUpdate,
    db: Session = Depends(get_db),
    # Allow admin or the assigned office manager to update?
    current_user: User = Depends(require_role(ADMIN_OR_MANAGER))
):
    """Update an office by ID. Requires ADMIN or Office Manager role."""
    db_office = crud_office.get_office(db, office_id=office_id)
    if db_office is None:
        raise HTTPException(status_code=404, detail="Office not found")

    # Optional: Add check if manager is updating their own office
    # if RoleType(current_user.role.name) == RoleType.OFFICE_MANAGER and current_user.office_id != office_id:
    #     raise HTTPException(status_code=403, detail="Office manager can only update their own office")

    return crud_office.update_office(db=db, db_office=db_office, office_in=office_in)

@router.delete("/{office_id}", response_model=Office)
def delete_single_office(
    office_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN_ROLE))
):
    """Delete an office by ID. Requires ADMIN role."""
    deleted_office = crud_office.delete_office(db, office_id=office_id)
    if deleted_office is None:
        raise HTTPException(status_code=404, detail="Office not found")
    return deleted_office

@router.put("/{office_id}/manager", response_model=Office)
def assign_manager(
    office_id: int,
    request: AssignManagerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN_ROLE))
):
    """Assign an Office Manager role user to an office. Requires ADMIN role."""
    db_office = crud_office.get_office(db, office_id=office_id)
    if db_office is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Office not found")

    assigned_office = crud_office.assign_manager_to_office(db, db_office=db_office, manager_user_id=request.manager_user_id)

    if assigned_office is None:
        # This could be because user doesn't exist or isn't an office manager
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID or user is not an Office Manager")

    return assigned_office 