from pydantic import BaseModel
from typing import Optional, List


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class AssociateRequest(BaseModel):
    join_code: str


# Enhanced token response with user info for frontend convenience
class TokenWithUser(Token):
    """Token response that includes basic user information and roles"""

    user_id: int
    name: str
    email: str
    office_id: Optional[int] = None
    role_names: List[str] = []  # List of role names for frontend convenience
