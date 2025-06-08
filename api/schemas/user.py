from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from .role import RoleReference


# Base User Schema (updated for multi-role support)
class UserBase(BaseModel):
    email: EmailStr
    name: str = Field(..., max_length=255)
    office_id: Optional[int] = None


# Schema for User Creation (supports multiple roles)
class UserCreate(UserBase):
    password: str
    role_ids: List[int] = Field(
        ..., min_items=1, description="List of role IDs to assign to the user"
    )

    @validator("role_ids")
    def validate_role_ids(cls, v):
        if not v or len(v) == 0:
            raise ValueError("At least one role must be assigned")
        if len(v) != len(set(v)):
            raise ValueError("Duplicate role IDs are not allowed")
        return v


# Schema for User Creation (backward compatibility)
class UserCreateLegacy(UserBase):
    """Legacy schema for backward compatibility - single role_id"""

    password: str
    role_id: int


# Schema for User Update (supports multiple roles)
class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    password: Optional[str] = None  # Represents the NEW password
    current_password: Optional[str] = None  # Add field for current password validation
    office_id: Optional[int] = None
    role_ids: Optional[List[int]] = None  # Optional for updates
    # Billing status fields
    is_active_for_billing: Optional[bool] = None
    activated_at: Optional[datetime] = None
    deactivated_at: Optional[datetime] = None
    last_billed_cycle: Optional[datetime] = None

    @validator("role_ids")
    def validate_role_ids(cls, v):
        if v is not None:
            if len(v) == 0:
                raise ValueError("If provided, at least one role must be assigned")
            if len(v) != len(set(v)):
                raise ValueError("Duplicate role IDs are not allowed")
        return v


# Schema for User Update (backward compatibility)
class UserUpdateLegacy(BaseModel):
    """Legacy schema for backward compatibility - single role_id"""

    email: Optional[EmailStr] = None
    name: Optional[str] = None
    password: Optional[str] = None
    current_password: Optional[str] = None
    role_id: Optional[int] = None
    office_id: Optional[int] = None
    # Billing status fields
    is_active_for_billing: Optional[bool] = None
    activated_at: Optional[datetime] = None
    deactivated_at: Optional[datetime] = None
    last_billed_cycle: Optional[datetime] = None


# Schema for User stored in DB (includes multiple roles)
class UserInDBBase(UserBase):
    user_id: int
    join_code: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    # Multiple roles instead of single role_id
    roles: List[RoleReference] = []
    # Billing status fields
    is_active_for_billing: bool = False
    activated_at: Optional[datetime] = None
    deactivated_at: Optional[datetime] = None
    last_billed_cycle: Optional[datetime] = None

    class Config:
        from_attributes = True


# Schema for returning User data to clients (omits password, includes roles)
class User(UserInDBBase):
    pass


# Schema for returning User data to clients (backward compatibility with single role)
class UserLegacy(UserBase):
    """Legacy response schema for backward compatibility"""

    user_id: int
    role_id: Optional[int] = None  # Primary role for backward compatibility
    join_code: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    # Billing status fields
    is_active_for_billing: bool = False
    activated_at: Optional[datetime] = None
    deactivated_at: Optional[datetime] = None
    last_billed_cycle: Optional[datetime] = None

    class Config:
        from_attributes = True


# Schema for user data stored in DB (including hashed password)
class UserInDB(UserInDBBase):
    password_hash: str


# Schema for billing status operations
class UserBillingStatusUpdate(BaseModel):
    """Schema for updating user billing status"""

    is_active_for_billing: bool
    activated_at: Optional[datetime] = None
    deactivated_at: Optional[datetime] = None

    def dict(self, **kwargs):
        """Override dict to set activated_at or deactivated_at based on status"""
        data = super().dict(**kwargs)
        now = datetime.datetime.utcnow()

        if self.is_active_for_billing:
            # If activating and no activated_at provided, set it to now
            if data.get("activated_at") is None:
                data["activated_at"] = now
            # Clear deactivated_at when activating
            data["deactivated_at"] = None
        else:
            # If deactivating and no deactivated_at provided, set it to now
            if data.get("deactivated_at") is None:
                data["deactivated_at"] = now

        return data


class UserBillingStatusResponse(BaseModel):
    """Schema for billing status API responses"""

    user_id: int
    is_active_for_billing: bool
    activated_at: Optional[datetime]
    deactivated_at: Optional[datetime]
    last_billed_cycle: Optional[datetime]

    class Config:
        from_attributes = True


# Schema for user role management operations
class UserRoleUpdateRequest(BaseModel):
    """Request to update a user's roles"""

    role_ids: List[int] = Field(
        ..., min_items=1, description="New list of role IDs for the user"
    )

    @validator("role_ids")
    def validate_role_ids(cls, v):
        if not v or len(v) == 0:
            raise ValueError("At least one role must be assigned")
        if len(v) != len(set(v)):
            raise ValueError("Duplicate role IDs are not allowed")
        return v


class UserRoleUpdateResponse(BaseModel):
    message: str
    user: "User"  # Forward reference to avoid circular import
    updated_roles: List[str]
    action_performed_by: str
    timestamp: datetime

    class Config:
        from_attributes = True


# Enhanced password and security schemas for Task 23.3
class PasswordValidationResponse(BaseModel):
    """Response for password validation feedback"""

    is_valid: bool
    errors: List[str] = []
    strength_score: Optional[int] = None
    strength_category: Optional[str] = None
    feedback: List[str] = []


class PasswordChangeRequest(BaseModel):
    """Request for changing password with validation"""

    current_password: str
    new_password: str

    class Config:
        schema_extra = {
            "example": {
                "current_password": "currentPassword123!",
                "new_password": "NewSecurePassword456#",
            }
        }


class PasswordChangeResponse(BaseModel):
    """Response for password change operation"""

    message: str
    password_changed_at: datetime
    next_required_change: Optional[datetime] = None

    class Config:
        from_attributes = True


class AccountSecurityStatus(BaseModel):
    """User account security status information"""

    user_id: int
    email: str
    password_changed_at: Optional[datetime] = None
    failed_login_attempts: int = 0
    last_failed_login: Optional[datetime] = None
    account_locked_until: Optional[datetime] = None
    last_successful_login: Optional[datetime] = None
    is_locked: bool = False
    lockout_remaining_minutes: int = 0
    password_age_days: Optional[int] = None

    class Config:
        from_attributes = True


class BulkPasswordResetRequest(BaseModel):
    """Request for administrative bulk password reset"""

    user_ids: List[int]
    temporary_password_length: int = 16
    require_change_on_login: bool = True
    notify_users: bool = True


class BulkPasswordResetResponse(BaseModel):
    """Response for bulk password reset operation"""

    message: str
    successful_resets: List[int]
    failed_resets: List[Dict[str, Any]]
    temporary_passwords: Dict[int, str]  # Only returned if notify_users=False


class SecurityAuditSummary(BaseModel):
    """Summary of security events for reporting"""

    total_users: int
    locked_accounts: int
    recent_login_failures: int
    recent_password_changes: int
    weak_passwords_detected: int
    accounts_requiring_password_change: int
    summary_period_days: int = 30
