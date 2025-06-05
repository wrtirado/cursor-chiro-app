from fastapi import Depends, HTTPException, status, Request
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
from api.core.audit_logger import log_role_access_check

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
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

    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    # Add logic here if users can be deactivated
    # if not current_user.is_active:
    #     raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


# Dependency to check for specific roles
def require_role(required_roles: List[RoleType]):
    """Dependency factory to check if the current user has one of the required roles."""

    def role_checker(
        request: Request,
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db),  # Add database session for audit logging
    ) -> User:
        required_role_names = [role.value for role in required_roles]
        user_role_names = (
            [role.name for role in current_user.roles] if current_user.roles else []
        )

        # Check if user has any roles assigned
        if not current_user.roles:
            # Log failed access attempt for audit
            log_role_access_check(
                user_id=current_user.user_id,
                required_roles=required_role_names,
                user_roles=[],
                granted=False,
                request=request,
                resource_type="endpoint",
                resource_id=request.url.path,
                db_session=db,
            )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User has no roles assigned. Required role(s): {', '.join(required_role_names)}",
            )

        # Check if user has any of the required roles using the new many-to-many relationship
        user_role_names_set = {role.name for role in current_user.roles}
        required_role_names_set = {role.value for role in required_roles}

        access_granted = bool(user_role_names_set.intersection(required_role_names_set))

        # Log the access attempt for HIPAA audit compliance
        log_role_access_check(
            user_id=current_user.user_id,
            required_roles=required_role_names,
            user_roles=user_role_names,
            granted=access_granted,
            request=request,
            resource_type="endpoint",
            resource_id=request.url.path,
            db_session=db,
        )

        if not access_granted:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User does not have required role(s): {', '.join(required_role_names)}",
            )

        return current_user

    return role_checker
