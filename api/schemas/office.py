from pydantic import BaseModel, validator
from typing import Optional, List
import datetime
from enum import Enum
from api.core.security_payment import PaymentReferenceSecurity


class SubscriptionStatus(str, Enum):
    active = "active"
    past_due = "past_due"
    canceled = "canceled"
    trialing = "trialing"
    inactive = "inactive"


# --- Office Schemas ---
class OfficeBase(BaseModel):
    name: str
    address: Optional[str] = None
    # Subscription and billing fields
    subscription_status: SubscriptionStatus = SubscriptionStatus.inactive
    payment_provider_customer_id: Optional[str] = None
    payment_provider_subscription_id: Optional[str] = None
    current_plan_id: Optional[int] = None
    billing_cycle_anchor_date: Optional[datetime.datetime] = None
    # company_id will be taken from path parameter during creation typically

    @validator("payment_provider_customer_id")
    def validate_customer_id(cls, v):
        """Validate Stripe customer ID format."""
        if v and not PaymentReferenceSecurity.validate_stripe_customer_id(v):
            raise ValueError(
                "Invalid Stripe customer ID format. Must match pattern: cus_[24 alphanumeric chars]"
            )
        return v

    @validator("payment_provider_subscription_id")
    def validate_subscription_id(cls, v):
        """Validate Stripe subscription ID format."""
        if v and not PaymentReferenceSecurity.validate_stripe_subscription_id(v):
            raise ValueError(
                "Invalid Stripe subscription ID format. Must match pattern: sub_[24 alphanumeric chars]"
            )
        return v


class OfficeCreate(OfficeBase):
    pass


class OfficeUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    subscription_status: Optional[SubscriptionStatus] = None
    payment_provider_customer_id: Optional[str] = None
    payment_provider_subscription_id: Optional[str] = None
    current_plan_id: Optional[int] = None
    billing_cycle_anchor_date: Optional[datetime.datetime] = None

    @validator("payment_provider_customer_id")
    def validate_customer_id(cls, v):
        """Validate Stripe customer ID format."""
        if v and not PaymentReferenceSecurity.validate_stripe_customer_id(v):
            raise ValueError(
                "Invalid Stripe customer ID format. Must match pattern: cus_[24 alphanumeric chars]"
            )
        return v

    @validator("payment_provider_subscription_id")
    def validate_subscription_id(cls, v):
        """Validate Stripe subscription ID format."""
        if v and not PaymentReferenceSecurity.validate_stripe_subscription_id(v):
            raise ValueError(
                "Invalid Stripe subscription ID format. Must match pattern: sub_[24 alphanumeric chars]"
            )
        return v


class OfficeInDBBase(OfficeBase):
    office_id: int
    company_id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True


class Office(OfficeInDBBase):
    pass  # Add related fields like users if needed in responses


class OfficeInDB(OfficeInDBBase):
    pass


class AssignManagerRequest(BaseModel):
    manager_user_id: int
