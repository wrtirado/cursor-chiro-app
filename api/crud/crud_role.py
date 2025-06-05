"""
CRUD operations for Role and UserRole models with HIPAA-compliant audit logging.

This module provides comprehensive role management functionality including:
- Role assignment and removal with audit trails
- Role activation/deactivation tracking
- Historical role assignment preservation
- HIPAA-compliant logging of all role changes
"""

from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func
from datetime import datetime
from fastapi import Request

from api.models.base import Role, User, UserRole
from api.schemas.role import (
    RoleCreate,
    RoleUpdate,
    UserRoleCreate,
    RoleAssignmentRequest,
    RoleUnassignmentRequest,
    RoleAssignmentResponse,
)
from api.core.audit_logger import log_role_event, log_role_access_check


class CRUDRole:
    """CRUD operations for Role model with audit logging"""

    def create(
        self,
        db: Session,
        *,
        obj_in: RoleCreate,
        user_id: int,
        request: Optional[Request] = None,
    ) -> Role:
        """Create a new role with audit logging"""
        db_obj = Role(name=obj_in.name)
        db.add(db_obj)
        db.flush()  # Get the ID without committing

        # Log role creation for audit
        log_role_event(
            action="role_created",
            user_id=user_id,
            role_id=db_obj.role_id,
            role_name=db_obj.name,
            request=request,
            details={
                "role_name": db_obj.name,
                "created_by": user_id,
            },
            db_session=db,
        )

        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get(self, db: Session, role_id: int) -> Optional[Role]:
        """Get role by ID"""
        return db.query(Role).filter(Role.role_id == role_id).first()

    def get_by_name(self, db: Session, name: str) -> Optional[Role]:
        """Get role by name"""
        return db.query(Role).filter(Role.name == name).first()

    def get_multi(self, db: Session, *, skip: int = 0, limit: int = 100) -> List[Role]:
        """Get multiple roles"""
        return db.query(Role).offset(skip).limit(limit).all()

    def update(
        self,
        db: Session,
        *,
        db_obj: Role,
        obj_in: RoleUpdate,
        user_id: int,
        request: Optional[Request] = None,
    ) -> Role:
        """Update role with audit logging"""
        update_data = obj_in.dict(exclude_unset=True)

        # Track changes for audit
        changes = {}
        for field, value in update_data.items():
            old_value = getattr(db_obj, field)
            if old_value != value:
                changes[field] = {"old": old_value, "new": value}
                setattr(db_obj, field, value)

        if changes:
            # Log role update
            log_role_event(
                action="role_updated",
                user_id=user_id,
                role_id=db_obj.role_id,
                role_name=db_obj.name,
                request=request,
                details={
                    "changes": changes,
                    "updated_by": user_id,
                },
                db_session=db,
            )

            db.commit()
            db.refresh(db_obj)

        return db_obj

    def delete(
        self,
        db: Session,
        *,
        role_id: int,
        user_id: int,
        request: Optional[Request] = None,
    ) -> bool:
        """Delete role with audit logging"""
        db_obj = self.get(db, role_id=role_id)
        if not db_obj:
            return False

        # Check if role is assigned to any users
        user_count = (
            db.query(UserRole)
            .filter(and_(UserRole.role_id == role_id, UserRole.is_active == True))
            .count()
        )

        # Log role deletion attempt
        log_role_event(
            action="role_deleted",
            user_id=user_id,
            role_id=db_obj.role_id,
            role_name=db_obj.name,
            request=request,
            details={
                "role_name": db_obj.name,
                "users_with_role": user_count,
                "deleted_by": user_id,
            },
            outcome="SUCCESS" if user_count == 0 else "FAILURE",
            db_session=db,
        )

        if user_count > 0:
            # Don't delete roles that are still assigned
            return False

        db.delete(db_obj)
        db.commit()
        return True


class CRUDUserRole:
    """CRUD operations for UserRole model with comprehensive audit logging"""

    def assign_roles(
        self,
        db: Session,
        *,
        user_id: int,
        role_ids: List[int],
        assigned_by_id: int,
        request: Optional[Request] = None,
    ) -> List[UserRole]:
        """
        Assign multiple roles to a user with comprehensive audit logging.

        This function implements HIPAA-compliant role assignment tracking including:
        - Who assigned the roles (assigned_by_id)
        - When the roles were assigned (assigned_at)
        - Full audit trail of the assignment process
        """
        assigned_roles = []

        # Get role names for audit logging
        roles = db.query(Role).filter(Role.role_id.in_(role_ids)).all()
        role_dict = {role.role_id: role.name for role in roles}

        for role_id in role_ids:
            role_name = role_dict.get(role_id, f"Unknown (ID: {role_id})")

            # Check if assignment already exists
            existing = (
                db.query(UserRole)
                .filter(and_(UserRole.user_id == user_id, UserRole.role_id == role_id))
                .first()
            )

            if existing:
                if not existing.is_active:
                    # Reactivate existing role
                    existing.is_active = True
                    existing.assigned_at = func.now()
                    existing.assigned_by_id = assigned_by_id

                    log_role_event(
                        action="role_reactivated",
                        user_id=assigned_by_id,
                        target_user_id=user_id,
                        role_id=role_id,
                        role_name=role_name,
                        assigned_by_id=assigned_by_id,
                        request=request,
                        details={
                            "previous_assigned_at": (
                                existing.assigned_at.isoformat()
                                if existing.assigned_at
                                else None
                            ),
                            "reactivated_at": datetime.now().isoformat(),
                        },
                        db_session=db,
                    )
                    assigned_roles.append(existing)
                else:
                    # Role already active - log attempt
                    log_role_event(
                        action="role_assignment_attempt",
                        user_id=assigned_by_id,
                        target_user_id=user_id,
                        role_id=role_id,
                        role_name=role_name,
                        assigned_by_id=assigned_by_id,
                        request=request,
                        details={"reason": "role_already_assigned"},
                        outcome="FAILURE",
                        db_session=db,
                    )
            else:
                # Create new role assignment
                new_assignment = UserRole(
                    user_id=user_id,
                    role_id=role_id,
                    assigned_by_id=assigned_by_id,
                    is_active=True,
                )
                db.add(new_assignment)
                db.flush()  # Get the ID

                log_role_event(
                    action="role_assigned",
                    user_id=assigned_by_id,
                    target_user_id=user_id,
                    role_id=role_id,
                    role_name=role_name,
                    assigned_by_id=assigned_by_id,
                    request=request,
                    details={
                        "user_role_id": new_assignment.user_role_id,
                        "assigned_at": datetime.now().isoformat(),
                    },
                    db_session=db,
                )
                assigned_roles.append(new_assignment)

        db.commit()
        return assigned_roles

    def unassign_roles(
        self,
        db: Session,
        *,
        user_id: int,
        role_ids: List[int],
        removed_by_id: int,
        request: Optional[Request] = None,
    ) -> List[UserRole]:
        """
        Remove roles from a user with audit logging.

        Uses soft deletion (is_active=False) to preserve audit history.
        """
        unassigned_roles = []

        # Get role names for audit logging
        roles = db.query(Role).filter(Role.role_id.in_(role_ids)).all()
        role_dict = {role.role_id: role.name for role in roles}

        for role_id in role_ids:
            role_name = role_dict.get(role_id, f"Unknown (ID: {role_id})")

            assignment = (
                db.query(UserRole)
                .filter(
                    and_(
                        UserRole.user_id == user_id,
                        UserRole.role_id == role_id,
                        UserRole.is_active == True,
                    )
                )
                .first()
            )

            if assignment:
                # Soft delete - preserve audit trail
                assignment.is_active = False

                log_role_event(
                    action="role_unassigned",
                    user_id=removed_by_id,
                    target_user_id=user_id,
                    role_id=role_id,
                    role_name=role_name,
                    assigned_by_id=removed_by_id,
                    request=request,
                    details={
                        "user_role_id": assignment.user_role_id,
                        "original_assigned_at": (
                            assignment.assigned_at.isoformat()
                            if assignment.assigned_at
                            else None
                        ),
                        "original_assigned_by": assignment.assigned_by_id,
                        "removed_at": datetime.now().isoformat(),
                    },
                    db_session=db,
                )
                unassigned_roles.append(assignment)
            else:
                # Role not found or not active - log attempt
                log_role_event(
                    action="role_assignment_attempt",
                    user_id=removed_by_id,
                    target_user_id=user_id,
                    role_id=role_id,
                    role_name=role_name,
                    assigned_by_id=removed_by_id,
                    request=request,
                    details={"reason": "role_not_found_or_inactive"},
                    outcome="FAILURE",
                    db_session=db,
                )

        db.commit()
        return unassigned_roles

    def get_user_roles(
        self, db: Session, user_id: int, active_only: bool = True
    ) -> List[UserRole]:
        """Get all roles for a user with optional filtering"""
        query = (
            db.query(UserRole)
            .options(joinedload(UserRole.role))
            .filter(UserRole.user_id == user_id)
        )

        if active_only:
            query = query.filter(UserRole.is_active == True)

        return query.all()

    def get_role_assignments(
        self, db: Session, role_id: int, active_only: bool = True
    ) -> List[UserRole]:
        """Get all users assigned to a role"""
        query = (
            db.query(UserRole)
            .options(joinedload(UserRole.user))
            .filter(UserRole.role_id == role_id)
        )

        if active_only:
            query = query.filter(UserRole.is_active == True)

        return query.all()

    def get_assignment_history(self, db: Session, user_id: int) -> List[UserRole]:
        """Get complete role assignment history for a user (for audit purposes)"""
        return (
            db.query(UserRole)
            .options(joinedload(UserRole.role), joinedload(UserRole.assigned_by))
            .filter(UserRole.user_id == user_id)
            .order_by(UserRole.assigned_at.desc())
            .all()
        )


# Function to integrate with existing role checking
def log_role_check(
    user: User,
    required_roles: List[str],
    granted: bool,
    request: Optional[Request] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
):
    """
    Log role access checks for HIPAA audit compliance.

    This should be called from the existing role checking logic
    to ensure all access attempts are logged.
    """
    user_roles = [role.name for role in user.roles] if user.roles else []

    log_role_access_check(
        user_id=user.user_id,
        required_roles=required_roles,
        user_roles=user_roles,
        granted=granted,
        request=request,
        resource_type=resource_type,
        resource_id=resource_id,
    )


# Create instances for use in routers
crud_role = CRUDRole()
crud_user_role = CRUDUserRole()
