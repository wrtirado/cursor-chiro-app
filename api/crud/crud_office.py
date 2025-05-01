from sqlalchemy.orm import Session, joinedload
from typing import Optional, List

from api.models.base import Office, User # Import User
from api.schemas.office import OfficeCreate, OfficeUpdate
from api.crud.crud_user import get_user # Import get_user
from api.core.config import RoleType # Import RoleType

def get_office(db: Session, office_id: int) -> Optional[Office]:
    return db.query(Office).filter(Office.office_id == office_id).first()

def get_offices_by_company(db: Session, company_id: int, skip: int = 0, limit: int = 100) -> List[Office]:
    return (
        db.query(Office)
        .filter(Office.company_id == company_id)
        .offset(skip)
        .limit(limit)
        .all()
    )

def create_office(db: Session, office: OfficeCreate, company_id: int) -> Office:
    db_office = Office(**office.dict(), company_id=company_id)
    db.add(db_office)
    db.commit()
    db.refresh(db_office)
    return db_office

def update_office(db: Session, db_office: Office, office_in: OfficeUpdate) -> Office:
    office_data = office_in.dict(exclude_unset=True)
    for key, value in office_data.items():
        setattr(db_office, key, value)
    db.add(db_office)
    db.commit()
    db.refresh(db_office)
    return db_office

def delete_office(db: Session, office_id: int) -> Optional[Office]:
    db_office = db.query(Office).filter(Office.office_id == office_id).first()
    if db_office:
        db.delete(db_office)
        db.commit()
    return db_office

def assign_manager_to_office(db: Session, db_office: Office, manager_user_id: int) -> Optional[Office]:
    """Assigns a user with the Office Manager role to an office."""
    manager = get_user(db, user_id=manager_user_id)

    if not manager:
        return None # Manager user not found

    # Verify the user has the correct role (e.g., OFFICE_MANAGER)
    # This assumes manager.role relationship is loaded or accessible
    if not manager.role or manager.role.name != RoleType.OFFICE_MANAGER.value:
        return None # User is not an office manager

    # Check if manager is already assigned to this or another office (optional, depending on rules)
    # if manager.office_id is not None and manager.office_id != db_office.office_id:
    #     return None # Manager already assigned elsewhere

    # Assign the manager to the office by setting their office_id
    manager.office_id = db_office.office_id
    db.add(manager)
    # We don't strictly need to commit here if the calling endpoint commits,
    # but doing it here makes the function self-contained.
    db.commit()
    db.refresh(manager)
    db.refresh(db_office) # Refresh office to reflect relationship changes if needed

    return db_office 