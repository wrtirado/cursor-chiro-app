from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, validator
from enum import Enum


class InvoiceStatus(str, Enum):
    """Invoice status enumeration"""

    PENDING = "pending"
    SENT = "sent"
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"


class InvoiceType(str, Enum):
    """Invoice type enumeration"""

    MONTHLY = "monthly"
    ONE_OFF = "one_off"
    SETUP_FEE = "setup_fee"


class InvoiceBase(BaseModel):
    """Base Invoice schema with common fields"""

    office_id: int = Field(..., description="Office ID this invoice belongs to")
    billing_period_start: Optional[datetime] = Field(
        None, description="Start of billing period"
    )
    billing_period_end: Optional[datetime] = Field(
        None, description="End of billing period"
    )
    total_amount_cents: int = Field(0, ge=0, description="Total amount in cents")
    status: InvoiceStatus = Field(InvoiceStatus.PENDING, description="Invoice status")
    stripe_invoice_id: Optional[str] = Field(None, description="Stripe invoice ID")
    invoice_type: InvoiceType = Field(
        InvoiceType.MONTHLY, description="Type of invoice"
    )
    notes: Optional[str] = Field(None, description="Additional notes")

    @validator("billing_period_end")
    def validate_billing_period(cls, v, values):
        """Ensure billing period end is after start if both are provided"""
        if v and "billing_period_start" in values and values["billing_period_start"]:
            if v <= values["billing_period_start"]:
                raise ValueError(
                    "billing_period_end must be after billing_period_start"
                )
        return v


class InvoiceCreate(InvoiceBase):
    """Schema for creating a new invoice"""

    pass


class InvoiceUpdate(BaseModel):
    """Schema for updating an existing invoice"""

    billing_period_start: Optional[datetime] = None
    billing_period_end: Optional[datetime] = None
    total_amount_cents: Optional[int] = Field(None, ge=0)
    status: Optional[InvoiceStatus] = None
    stripe_invoice_id: Optional[str] = None
    invoice_type: Optional[InvoiceType] = None
    notes: Optional[str] = None

    @validator("billing_period_end")
    def validate_billing_period(cls, v, values):
        """Ensure billing period end is after start if both are provided"""
        if v and "billing_period_start" in values and values["billing_period_start"]:
            if v <= values["billing_period_start"]:
                raise ValueError(
                    "billing_period_end must be after billing_period_start"
                )
        return v


class InvoiceResponse(InvoiceBase):
    """Schema for invoice API responses"""

    id: int = Field(..., description="Invoice ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        from_attributes = True


class InvoiceListResponse(BaseModel):
    """Schema for paginated invoice list responses"""

    invoices: list[InvoiceResponse]
    total: int = Field(..., description="Total number of invoices")
    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Items per page")
    has_next: bool = Field(..., description="Whether there are more pages")
    has_prev: bool = Field(..., description="Whether there are previous pages")


class InvoiceFilters(BaseModel):
    """Schema for filtering invoices"""

    office_id: Optional[int] = None
    status: Optional[InvoiceStatus] = None
    invoice_type: Optional[InvoiceType] = None
    billing_period_start_after: Optional[datetime] = None
    billing_period_start_before: Optional[datetime] = None
    stripe_invoice_id: Optional[str] = None
