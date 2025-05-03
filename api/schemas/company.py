from pydantic import BaseModel
from typing import Optional, List
import datetime
from .office import Office  # Import the full Office schema


# Forward declaration for Office schema if needed
class Office(BaseModel):  # Define minimal Office here if needed for circular refs
    office_id: int
    name: str

    class Config:
        from_attributes = True


# --- Company Schemas ---
class CompanyBase(BaseModel):
    name: str


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    name: Optional[str] = None


class CompanyInDBBase(CompanyBase):
    company_id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True


class Company(CompanyInDBBase):
    offices: List[Office] = []  # Now uses the imported Office schema


class CompanyInDB(CompanyInDBBase):
    pass
