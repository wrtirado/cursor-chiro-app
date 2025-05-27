from pydantic import BaseModel, EmailStr, Field
from typing import Optional
import datetime


# Base User Schema
class UserBase(BaseModel):
    email: EmailStr
    name: str = Field(..., max_length=255)
    role_id: int
    office_id: Optional[int] = None


# Schema for User Creation (includes password)
class UserCreate(UserBase):
    password: str


# Schema for User Update
class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    password: Optional[str] = None  # Represents the NEW password
    current_password: Optional[str] = None  # Add field for current password validation
    role_id: Optional[int] = None
    office_id: Optional[int] = None
    # Billing status fields
    is_active_for_billing: Optional[bool] = None
    activated_at: Optional[datetime.datetime] = None
    deactivated_at: Optional[datetime.datetime] = None
    last_billed_cycle: Optional[datetime.datetime] = None


# Schema for User stored in DB (includes hashed password)
class UserInDBBase(UserBase):
    user_id: int
    join_code: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    # Billing status fields
    is_active_for_billing: bool = False
    activated_at: Optional[datetime.datetime] = None
    deactivated_at: Optional[datetime.datetime] = None
    last_billed_cycle: Optional[datetime.datetime] = None

    class Config:
        from_attributes = True


# Schema for returning User data to clients (omits password)
class User(UserInDBBase):
    pass


# Schema for user data stored in DB (including hashed password)
class UserInDB(UserInDBBase):
    password_hash: str


# Schema for billing status operations
class UserBillingStatusUpdate(BaseModel):
    """Schema for updating user billing status"""

    is_active_for_billing: bool
    activated_at: Optional[datetime.datetime] = None
    deactivated_at: Optional[datetime.datetime] = None

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
    activated_at: Optional[datetime.datetime]
    deactivated_at: Optional[datetime.datetime]
    last_billed_cycle: Optional[datetime.datetime]

    class Config:
        from_attributes = True
