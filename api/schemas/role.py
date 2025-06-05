from pydantic import BaseModel
from typing import Optional, List
import datetime


# Schema for Role data
class RoleBase(BaseModel):
    name: str


class RoleCreate(RoleBase):
    """Schema for creating a new role"""

    pass


class RoleUpdate(BaseModel):
    """Schema for updating an existing role"""

    name: Optional[str] = None


# Schema for Role read from DB (includes ID)
class Role(RoleBase):
    role_id: int

    class Config:
        from_attributes = True


# Schema for UserRole association (junction table)
class UserRoleBase(BaseModel):
    user_id: int
    role_id: int
    is_active: bool = True


class UserRoleCreate(UserRoleBase):
    assigned_by_id: Optional[int] = None


class UserRoleUpdate(BaseModel):
    is_active: Optional[bool] = None


class UserRole(UserRoleBase):
    user_role_id: int
    assigned_at: datetime.datetime
    assigned_by_id: Optional[int] = None

    # Include related data for responses
    role: Optional[Role] = None

    class Config:
        from_attributes = True


# Schema for role assignment operations
class RoleAssignmentRequest(BaseModel):
    """Request to assign roles to a user"""

    user_id: int
    role_ids: List[int]
    assigned_by_id: Optional[int] = None


class RoleUnassignmentRequest(BaseModel):
    """Request to unassign roles from a user"""

    user_id: int
    role_ids: List[int]


class RoleAssignmentResponse(BaseModel):
    """Response for role assignment operations"""

    user_id: int
    assigned_roles: List[Role]
    unassigned_roles: List[Role] = []
    message: str

    class Config:
        from_attributes = True


# Simple role reference for user schemas
class RoleReference(BaseModel):
    """Simplified role representation for user responses"""

    role_id: int
    name: str

    class Config:
        from_attributes = True
