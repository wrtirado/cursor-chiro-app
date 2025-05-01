from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError
from typing import List

from api.core import security
from api.schemas.token import TokenData
from api.crud import crud_user
from api.database.session import get_db
from api.models.base import User
from api.core.config import settings, RoleType

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = security.decode_access_token(token)
    if payload is None:
        raise credentials_exception
    email: str = payload.get("sub")
    if email is None:
        raise credentials_exception
    token_data = TokenData(email=email)

    user = crud_user.get_user_by_email(db, email=token_data.email)
    if user is None:
        raise credentials_exception
    if not user.role:
        pass

    return user

def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    # Add logic here if users can be deactivated
    # if not current_user.is_active:
    #     raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# Dependency to check for specific roles
def require_role(required_roles: List[RoleType]):
    """Dependency factory to check if the current user has one of the required roles."""
    def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if not current_user.role or RoleType(current_user.role.name) not in required_roles:
            role_names = [role.value for role in required_roles]
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User does not have required role(s): {', '.join(role_names)}"
            )
        return current_user
    return role_checker 