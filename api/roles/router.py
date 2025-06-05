"""
Role management router with HIPAA-compliant audit logging.

This router provides endpoints for managing user roles including:
- Assigning and removing roles from users
- Viewing role assignment history
- Managing role definitions
- Complete audit trail for all role changes
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from api.database.session import get_db
from api.auth.dependencies import get_current_active_user, require_role
from api.core.config import RoleType
from api.models.base import User, Role, UserRole
from api.schemas.role import (
    Role as RoleSchema,
    RoleCreate,
    RoleUpdate,
    UserRole as UserRoleSchema,
    RoleAssignmentRequest,
    RoleUnassignmentRequest,
    RoleAssignmentResponse,
)
from api.crud.crud_role import crud_role, crud_user_role

router = APIRouter()

# Define role requirements
ADMIN_ROLE = [RoleType.ADMIN]
OFFICE_MANAGER_ROLE = [RoleType.OFFICE_MANAGER]
ADMIN_OR_OFFICE_MANAGER = [RoleType.ADMIN, RoleType.OFFICE_MANAGER]


@router.post("/assign", response_model=RoleAssignmentResponse)
def assign_roles_to_user(
    request: Request,
    assignment_request: RoleAssignmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN_OR_OFFICE_MANAGER)),
):
    """
    Assign roles to a user with comprehensive audit logging.

    Requires ADMIN or OFFICE_MANAGER role.
    All role assignments are logged for HIPAA compliance.
    """
    # Verify target user exists
    from api.crud.crud_user import get_user

    target_user = get_user(db, user_id=assignment_request.user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Verify all roles exist
    roles = db.query(Role).filter(Role.role_id.in_(assignment_request.role_ids)).all()
    if len(roles) != len(assignment_request.role_ids):
        found_ids = {role.role_id for role in roles}
        missing_ids = set(assignment_request.role_ids) - found_ids
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role IDs: {list(missing_ids)}",
        )

    # Assign roles with audit logging
    assigned_user_roles = crud_user_role.assign_roles(
        db=db,
        user_id=assignment_request.user_id,
        role_ids=assignment_request.role_ids,
        assigned_by_id=current_user.user_id,
        request=request,
    )

    # Build response
    assigned_roles = [
        user_role.role for user_role in assigned_user_roles if user_role.role
    ]

    return RoleAssignmentResponse(
        user_id=assignment_request.user_id,
        assigned_roles=assigned_roles,
        message=f"Successfully assigned {len(assigned_roles)} role(s) to user {assignment_request.user_id}",
    )


@router.post("/unassign", response_model=RoleAssignmentResponse)
def unassign_roles_from_user(
    request: Request,
    unassignment_request: RoleUnassignmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN_OR_OFFICE_MANAGER)),
):
    """
    Remove roles from a user with comprehensive audit logging.

    Requires ADMIN or OFFICE_MANAGER role.
    Uses soft deletion to preserve audit history.
    """
    # Verify target user exists
    from api.crud.crud_user import get_user

    target_user = get_user(db, user_id=unassignment_request.user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Remove roles with audit logging
    unassigned_user_roles = crud_user_role.unassign_roles(
        db=db,
        user_id=unassignment_request.user_id,
        role_ids=unassignment_request.role_ids,
        removed_by_id=current_user.user_id,
        request=request,
    )

    # Build response
    unassigned_roles = [
        user_role.role for user_role in unassigned_user_roles if user_role.role
    ]

    return RoleAssignmentResponse(
        user_id=unassignment_request.user_id,
        assigned_roles=[],  # Empty for unassignment
        unassigned_roles=unassigned_roles,
        message=f"Successfully removed {len(unassigned_roles)} role(s) from user {unassignment_request.user_id}",
    )


@router.get("/users/{user_id}/roles", response_model=List[UserRoleSchema])
def get_user_roles(
    user_id: int,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN_OR_OFFICE_MANAGER)),
):
    """
    Get all roles assigned to a user.

    Includes audit information (assigned_at, assigned_by_id).
    """
    user_roles = crud_user_role.get_user_roles(
        db=db, user_id=user_id, active_only=not include_inactive
    )

    return user_roles


@router.get("/users/{user_id}/roles/history", response_model=List[UserRoleSchema])
def get_user_role_history(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN_ROLE)),
):
    """
    Get complete role assignment history for a user (for audit purposes).

    Requires ADMIN role due to sensitive audit information.
    """
    return crud_user_role.get_assignment_history(db=db, user_id=user_id)


@router.get("/roles", response_model=List[RoleSchema])
def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN_OR_OFFICE_MANAGER)),
):
    """List all available roles."""
    return crud_role.get_multi(db=db)


@router.post("/roles", response_model=RoleSchema)
def create_role(
    request: Request,
    role_in: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN_ROLE)),
):
    """
    Create a new role with audit logging.

    Requires ADMIN role.
    """
    # Check if role already exists
    existing = crud_role.get_by_name(db=db, name=role_in.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role '{role_in.name}' already exists",
        )

    return crud_role.create(
        db=db, obj_in=role_in, user_id=current_user.user_id, request=request
    )


@router.put("/roles/{role_id}", response_model=RoleSchema)
def update_role(
    request: Request,
    role_id: int,
    role_in: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN_ROLE)),
):
    """
    Update a role with audit logging.

    Requires ADMIN role.
    """
    db_role = crud_role.get(db=db, role_id=role_id)
    if not db_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role not found"
        )

    return crud_role.update(
        db=db,
        db_obj=db_role,
        obj_in=role_in,
        user_id=current_user.user_id,
        request=request,
    )


@router.delete("/roles/{role_id}")
def delete_role(
    request: Request,
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN_ROLE)),
):
    """
    Delete a role with audit logging.

    Requires ADMIN role. Cannot delete roles that are currently assigned.
    """
    success = crud_role.delete(
        db=db, role_id=role_id, user_id=current_user.user_id, request=request
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete role: either not found or still assigned to users",
        )

    return {"message": "Role deleted successfully"}


@router.get("/roles/{role_id}/assignments", response_model=List[UserRoleSchema])
def get_role_assignments(
    role_id: int,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN_OR_OFFICE_MANAGER)),
):
    """
    Get all users assigned to a specific role.

    Includes audit information for each assignment.
    """
    return crud_user_role.get_role_assignments(
        db=db, role_id=role_id, active_only=not include_inactive
    )
