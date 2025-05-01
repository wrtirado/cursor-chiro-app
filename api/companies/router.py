from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from api.database.session import get_db
from api.schemas.company import Company, CompanyCreate, CompanyUpdate
from api.schemas.office import Office, OfficeCreate # Need OfficeCreate
from api.crud import crud_company, crud_office # Need crud_office
from api.auth.dependencies import require_role
from api.core.config import RoleType
from api.models.base import User # Import User model for type hinting

router = APIRouter()

ADMIN_ROLE = [RoleType.ADMIN]

@router.post("/", response_model=Company, status_code=status.HTTP_201_CREATED)
def create_new_company(
    company_in: CompanyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN_ROLE))
):
    """Create a new company. Requires ADMIN role."""
    return crud_company.create_company(db=db, company=company_in)

@router.get("/", response_model=List[Company])
def read_all_companies(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    # Allow more roles to view companies if needed, e.g. managers
    # current_user: User = Depends(require_role([RoleType.ADMIN, RoleType.OFFICE_MANAGER]))
    current_user: User = Depends(require_role(ADMIN_ROLE))
):
    """Retrieve all companies. Requires ADMIN role."""
    companies = crud_company.get_companies(db, skip=skip, limit=limit)
    return companies

@router.get("/{company_id}", response_model=Company)
def read_single_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN_ROLE))
):
    """Retrieve a specific company by ID. Requires ADMIN role."""
    db_company = crud_company.get_company(db, company_id=company_id)
    if db_company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return db_company

@router.put("/{company_id}", response_model=Company)
def update_existing_company(
    company_id: int,
    company_in: CompanyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN_ROLE))
):
    """Update a company by ID. Requires ADMIN role."""
    db_company = crud_company.get_company(db, company_id=company_id)
    if db_company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return crud_company.update_company(db=db, db_company=db_company, company_in=company_in)

@router.delete("/{company_id}", response_model=Company)
def delete_single_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN_ROLE))
):
    """Delete a company by ID. Requires ADMIN role."""
    deleted_company = crud_company.delete_company(db, company_id=company_id)
    if deleted_company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return deleted_company

# --- Nested Office Endpoints --- #

@router.post("/{company_id}/offices/", response_model=Office, status_code=status.HTTP_201_CREATED)
def create_new_office_for_company(
    company_id: int,
    office_in: OfficeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN_ROLE))
):
    """Create a new office within a specific company. Requires ADMIN role."""
    db_company = crud_company.get_company(db, company_id=company_id)
    if db_company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return crud_office.create_office(db=db, office=office_in, company_id=company_id)

@router.get("/{company_id}/offices/", response_model=List[Office])
def read_offices_for_company(
    company_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADMIN_ROLE))
):
    """Retrieve all offices for a specific company. Requires ADMIN role."""
    db_company = crud_company.get_company(db, company_id=company_id)
    if db_company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    offices = crud_office.get_offices_by_company(db, company_id=company_id, skip=skip, limit=limit)
    return offices 