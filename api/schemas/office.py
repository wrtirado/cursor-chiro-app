from pydantic import BaseModel
from typing import Optional, List
import datetime

# --- Office Schemas ---
class OfficeBase(BaseModel):
    name: str
    address: Optional[str] = None
    # company_id will be taken from path parameter during creation typically

class OfficeCreate(OfficeBase):
    pass

class OfficeUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None

class OfficeInDBBase(OfficeBase):
    office_id: int
    company_id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        orm_mode = True

class Office(OfficeInDBBase):
    pass # Add related fields like users if needed in responses

class OfficeInDB(OfficeInDBBase):
    pass

class AssignManagerRequest(BaseModel):
    manager_user_id: int 