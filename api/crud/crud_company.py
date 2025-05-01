from sqlalchemy.orm import Session, joinedload
from typing import Optional, List

from api.models.base import Company, Office
from api.schemas.company import CompanyCreate, CompanyUpdate

def get_company(db: Session, company_id: int) -> Optional[Company]:
    return (
        db.query(Company)
        .options(joinedload(Company.offices)) # Eager load offices
        .filter(Company.company_id == company_id)
        .first()
    )

def get_companies(db: Session, skip: int = 0, limit: int = 100) -> List[Company]:
    return (
        db.query(Company)
        .options(joinedload(Company.offices))
        .offset(skip)
        .limit(limit)
        .all()
    )

def create_company(db: Session, company: CompanyCreate) -> Company:
    db_company = Company(name=company.name)
    db.add(db_company)
    db.commit()
    db.refresh(db_company)
    # Eager load offices for the returned object (will be empty initially)
    db_company.offices = []
    return db_company

def update_company(db: Session, db_company: Company, company_in: CompanyUpdate) -> Company:
    company_data = company_in.dict(exclude_unset=True)
    for key, value in company_data.items():
        setattr(db_company, key, value)
    db.add(db_company)
    db.commit()
    db.refresh(db_company)
    # Eager load offices after update
    db.query(Office).filter(Office.company_id == db_company.company_id).all()
    db.refresh(db_company, attribute_names=['offices'])
    return db_company

def delete_company(db: Session, company_id: int) -> Optional[Company]:
    db_company = db.query(Company).filter(Company.company_id == company_id).first()
    if db_company:
        db.delete(db_company)
        db.commit()
    return db_company 