from sqlalchemy.orm import Session
from typing import Optional, List

from api.models.base import User
from api.schemas.user import UserCreate, UserUpdate
from api.core.security import get_password_hash
from api.core.utils import generate_random_code
from api.core.config import RoleType

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()

def get_user(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.user_id == user_id).first()

def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    return db.query(User).offset(skip).limit(limit).all()

def get_user_by_join_code(db: Session, join_code: str) -> Optional[User]:
    # Ensure join_code is not None or empty before querying
    if not join_code:
        return None
    return db.query(User).filter(User.join_code == join_code).first()

def create_user(db: Session, user: UserCreate) -> User:
    hashed_password = get_password_hash(user.password)
    db_user = User(
        email=user.email,
        name=user.name,
        password_hash=hashed_password,
        role_id=user.role_id,
        office_id=user.office_id
    )

    # Generate join code only for chiropractors initially
    # We need to fetch the Role object or compare role_id if we know the ID mapping
    # Assuming role_id 2 corresponds to chiropractor based on our init_schema.sql INSERT order
    # A better way would be to query the Role table or use the RoleType enum if role_id is predictable
    temp_chiro_role_id = 2 # Fragile: Assumes ID from seed
    if user.role_id == temp_chiro_role_id:
        while True:
            join_code = generate_random_code()
            existing_user = get_user_by_join_code(db, join_code)
            if not existing_user:
                db_user.join_code = join_code
                break

    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user(db: Session, db_user: User, user_in: UserUpdate) -> User:
    user_data = user_in.dict(exclude_unset=True)
    if "password" in user_data and user_data["password"]:
        hashed_password = get_password_hash(user_data["password"])
        db_user.password_hash = hashed_password
        del user_data["password"] # Remove plain password before updating

    for key, value in user_data.items():
        setattr(db_user, key, value)

    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def delete_user(db: Session, user_id: int) -> Optional[User]:
    db_user = db.query(User).filter(User.user_id == user_id).first()
    if db_user:
        db.delete(db_user)
        db.commit()
    return db_user

# Function to associate a user (patient) using a join code - Placeholder for logic
def associate_user_with_chiro(db: Session, patient: User, chiro: User) -> User:
    # Logic to link patient to chiropractor/office based on chiro's info
    # This might involve updating patient's office_id or creating a linking record
    # depending on the exact association model.
    # For now, let's assume we link the patient to the chiro's office
    if chiro.office_id:
        patient.office_id = chiro.office_id
        db.add(patient)
        db.commit()
        db.refresh(patient)
    return patient 