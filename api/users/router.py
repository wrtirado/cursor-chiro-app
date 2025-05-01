from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from api.database.session import get_db
from api.schemas.user import User, UserUpdate
from api.crud import crud_user
from api.auth.dependencies import require_role # Import the dependency
from api.core.config import RoleType # Import RoleType

router = APIRouter()

# Define required roles for management endpoints
MANAGER_ROLES = [RoleType.OFFICE_MANAGER, RoleType.BILLING_ADMIN] # Example: Allow Office Managers and Billing Admins

@router.get("/", response_model=List[User])
def read_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(MANAGER_ROLES))
):
    """Retrieve a list of users. Requires manager roles."""
    users = crud_user.get_users(db, skip=skip, limit=limit)
    return users

@router.get("/{user_id}", response_model=User)
def read_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(MANAGER_ROLES))
):
    """Retrieve a specific user by ID. Requires manager roles."""
    db_user = crud_user.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user

@router.put("/{user_id}", response_model=User)
def update_existing_user(
    user_id: int,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(MANAGER_ROLES))
):
    """Update a user by ID. Requires manager roles."""
    db_user = crud_user.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if email is being updated and if it's already taken by another user
    if user_in.email and user_in.email != db_user.email:
        existing_user = crud_user.get_user_by_email(db, email=user_in.email)
        if existing_user and existing_user.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered by another user."
            )

    updated_user = crud_user.update_user(db, db_user=db_user, user_in=user_in)
    return updated_user

@router.delete("/{user_id}", response_model=User)
def delete_existing_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(MANAGER_ROLES))
):
    """Delete a user by ID. Requires manager roles."""
    deleted_user = crud_user.delete_user(db, user_id=user_id)
    if deleted_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return deleted_user

# Additional endpoints mentioned in Task 4 details (placeholders):
# - Add/remove patients associated with chiropractors
# - Manage chiropractor accounts within an office
# - Generate join codes (maybe better handled during creation or specific endpoint) 