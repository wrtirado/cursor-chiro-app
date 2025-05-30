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


# Schema for User stored in DB (includes hashed password)
class UserInDBBase(UserBase):
    user_id: int
    join_code: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True


# Schema for returning User data to clients (omits password)
class User(UserInDBBase):
    pass


# Schema for user data stored in DB (including hashed password)
class UserInDB(UserInDBBase):
    password_hash: str
