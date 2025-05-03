from pydantic import BaseModel


# Schema for Role data
class RoleBase(BaseModel):
    name: str


# Schema for Role read from DB (includes ID)
class Role(RoleBase):
    role_id: int

    class Config:
        from_attributes = True
