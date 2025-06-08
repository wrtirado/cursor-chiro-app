from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from api.database.session import get_db
from api.schemas.token import Token, AssociateRequest
from api.schemas.user import User, UserCreate, UserUpdate
from api.crud import crud_user
from api.core import security
from api.auth.dependencies import get_current_active_user, require_role
from api.core.audit_logger import log_audit_event, AuditEvent
from api.core.security import is_account_locked, get_lockout_remaining_time

router = APIRouter()


@router.post("/login", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    """
    Authenticate user and return access token.
    Enhanced with HIPAA-compliant security features including account lockout.
    """
    # Use enhanced authentication with security features
    user = crud_user.authenticate_user(db, form_data.username, form_data.password)

    if not user:
        # Check if user exists to provide specific error message
        existing_user = crud_user.get_user_by_email(db, form_data.username)

        if existing_user:
            # Check if account is locked
            if is_account_locked(
                existing_user.failed_login_attempts, existing_user.last_failed_login
            ):
                remaining_time = get_lockout_remaining_time(
                    existing_user.last_failed_login
                )
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail={
                        "message": f"Account is temporarily locked due to multiple failed login attempts. Please try again in {remaining_time} minutes.",
                        "lockout_remaining_minutes": remaining_time,
                        "type": "account_locked",
                    },
                )
            else:
                # Account exists but wrong password
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "message": "Incorrect email or password",
                        "type": "invalid_credentials",
                    },
                    headers={"WWW-Authenticate": "Bearer"},
                )
        else:
            # User doesn't exist
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "message": "Incorrect email or password",
                    "type": "invalid_credentials",
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
def register_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    # Add dependency to restrict access, e.g., only office managers can register users
    # current_user: models.User = Depends(require_role("office_manager"))
):
    """
    Register a new user. Endpoint might need protection based on requirements.
    Requires: name, email, password, role_id, office_id (optional)
    Returns: Created user details.
    """
    db_user = crud_user.get_user_by_email(db, email=user_in.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Validate role_id and office_id exist if provided (add crud functions for roles/offices if needed)
    # Example validation (requires crud functions not yet created):
    # if not crud_role.get_role(db, user_in.role_id):
    #     raise HTTPException(status_code=400, detail="Invalid role_id")
    # if user_in.office_id and not crud_office.get_office(db, user_in.office_id):
    #     raise HTTPException(status_code=400, detail="Invalid office_id")

    created_user = crud_user.create_user(db=db, user=user_in)
    return created_user


@router.post("/associate", response_model=dict)
def associate_patient_with_care_provider(
    associate_request: AssociateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_role("patient")
    ),  # Only patients can associate
):
    """
    Associate a patient with a care provider/office using a join code.
    Requires: join_code
    Returns: care_provider_id and office_id of the associated care provider.
    """
    # Find the user (likely care provider) who owns the join code
    care_provider_user = crud_user.get_user_by_join_code(
        db, join_code=associate_request.join_code
    )

    if not care_provider_user or not care_provider_user.has_role("care_provider"):
        raise HTTPException(
            status_code=404, detail="Invalid or non-care-provider join code"
        )

    if not care_provider_user.office_id:
        raise HTTPException(
            status_code=400,
            detail="Care provider associated with join code has no office assigned",
        )

    # Associate the current patient user with the care provider's office
    crud_user.associate_user_with_care_provider(
        db, patient=current_user, care_provider=care_provider_user
    )

    return {
        "care_provider_id": care_provider_user.user_id,
        "office_id": care_provider_user.office_id,
    }


# Example protected endpoint
@router.get("/me", response_model=User)
def read_users_me(current_user: User = Depends(get_current_active_user)):
    """Get current logged in user details."""
    return current_user


@router.put("/me", response_model=User)
def update_user_me(
    *,  # Makes db and current_user keyword-only arguments
    db: Session = Depends(get_db),
    user_in: UserUpdate,  # Use the UserUpdate schema
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Update current logged in user details (name, email, password)."""
    # Check if email is being updated and if it's already taken
    if user_in.email and user_in.email != current_user.email:
        existing_user = crud_user.get_user_by_email(db, email=user_in.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered by another user.",
            )

    updated_user = crud_user.update_user(db, db_user=current_user, user_in=user_in)
    return updated_user
