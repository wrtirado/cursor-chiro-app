from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum
import json


class LineItemType(str, Enum):
    """Line item type enumeration"""

    PATIENT_ACTIVATION = "patient_activation"
    SETUP_FEE = "setup_fee"
    MONTHLY_RECURRING = "monthly_recurring"
    ONE_OFF = "one_off"
    ADJUSTMENT = "adjustment"
    DISCOUNT = "discount"


class InvoiceLineItemBase(BaseModel):
    """Base InvoiceLineItem schema with common fields"""

    invoice_id: int = Field(..., description="Invoice ID this line item belongs to")
    item_type: LineItemType = Field(..., description="Type of line item")
    description: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="ePHI-sanitized description (e.g., 'Patient Activations: 3 @ $5.00 each')",
    )
    quantity: int = Field(1, ge=0, description="Quantity of items")
    unit_price_cents: int = Field(0, ge=0, description="Unit price in cents")
    total_amount_cents: int = Field(
        0, description="Total amount in cents (quantity * unit_price)"
    )
    metadata_json: Optional[str] = Field(
        None, description="JSON metadata for aggregate billing data (NO ePHI allowed)"
    )

    @validator("total_amount_cents", always=True)
    def validate_total_amount(cls, v, values):
        """Ensure total_amount_cents matches quantity * unit_price_cents"""
        if "quantity" in values and "unit_price_cents" in values:
            expected_total = values["quantity"] * values["unit_price_cents"]
            if v != expected_total:
                return expected_total
        return v

    @validator("metadata_json")
    def validate_metadata_json(cls, v):
        """Validate that metadata_json is valid JSON if provided"""
        if v is not None:
            try:
                json.loads(v)
            except json.JSONDecodeError:
                raise ValueError("metadata_json must be valid JSON")
        return v

    @validator("description")
    def validate_no_ephi_in_description(cls, v):
        """Basic validation to ensure description doesn't contain obvious ePHI markers"""
        # Check for common ePHI patterns (this is basic validation, real implementation would be more sophisticated)
        forbidden_patterns = [
            "@",  # Email addresses
            "ssn",
            "social security",
            "patient id",
            "patient_id",
            "medical record",
            "mrn",
            "dob",
            "date of birth",
        ]

        description_lower = v.lower()
        for pattern in forbidden_patterns:
            if pattern in description_lower:
                raise ValueError(
                    f"Description contains potential ePHI pattern: {pattern}"
                )

        return v


class InvoiceLineItemCreate(InvoiceLineItemBase):
    """Schema for creating a new invoice line item"""

    pass


class InvoiceLineItemUpdate(BaseModel):
    """Schema for updating an existing invoice line item"""

    item_type: Optional[LineItemType] = None
    description: Optional[str] = Field(None, min_length=1, max_length=500)
    quantity: Optional[int] = Field(None, ge=0)
    unit_price_cents: Optional[int] = Field(None, ge=0)
    total_amount_cents: Optional[int] = None
    metadata_json: Optional[str] = None

    @validator("metadata_json")
    def validate_metadata_json(cls, v):
        """Validate that metadata_json is valid JSON if provided"""
        if v is not None:
            try:
                json.loads(v)
            except json.JSONDecodeError:
                raise ValueError("metadata_json must be valid JSON")
        return v

    @validator("description")
    def validate_no_ephi_in_description(cls, v):
        """Basic validation to ensure description doesn't contain obvious ePHI markers"""
        if v is not None:
            forbidden_patterns = [
                "@",
                "ssn",
                "social security",
                "patient id",
                "patient_id",
                "medical record",
                "mrn",
                "dob",
                "date of birth",
            ]

            description_lower = v.lower()
            for pattern in forbidden_patterns:
                if pattern in description_lower:
                    raise ValueError(
                        f"Description contains potential ePHI pattern: {pattern}"
                    )

        return v


class InvoiceLineItemResponse(InvoiceLineItemBase):
    """Schema for invoice line item API responses"""

    id: int = Field(..., description="Line item ID")
    created_at: datetime = Field(..., description="Creation timestamp")

    class Config:
        from_attributes = True


class InvoiceLineItemFilters(BaseModel):
    """Schema for filtering invoice line items"""

    invoice_id: Optional[int] = None
    item_type: Optional[LineItemType] = None
    min_amount_cents: Optional[int] = Field(None, ge=0)
    max_amount_cents: Optional[int] = Field(None, ge=0)
    description_contains: Optional[str] = None


class LineItemSummary(BaseModel):
    """Schema for line item summary (for invoice totals, etc.)"""

    item_type: LineItemType
    total_quantity: int = Field(..., ge=0)
    total_amount_cents: int = Field(..., ge=0)
    line_item_count: int = Field(..., ge=0)


class InvoiceLineItemListResponse(BaseModel):
    """Schema for paginated invoice line item list responses"""

    line_items: list[InvoiceLineItemResponse]
    total: int = Field(..., description="Total number of line items")
    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Items per page")
    has_next: bool = Field(..., description="Whether there are more pages")
    has_prev: bool = Field(..., description="Whether there are previous pages")


class ePHISanitizationHelper:
    """Helper class for ePHI sanitization functions"""

    @staticmethod
    def create_patient_activation_description(count: int, unit_price_cents: int) -> str:
        """Create sanitized description for patient activations"""
        unit_price_dollars = unit_price_cents / 100
        return f"Patient Activations: {count} @ ${unit_price_dollars:.2f} each"

    @staticmethod
    def create_setup_fee_description(office_name: str) -> str:
        """Create sanitized description for setup fees"""
        return f"Initial Setup Fee - {office_name}"

    @staticmethod
    def create_monthly_recurring_description(
        billing_period_start: datetime, billing_period_end: datetime
    ) -> str:
        """Create sanitized description for monthly recurring charges"""
        start_str = billing_period_start.strftime("%Y-%m-%d")
        end_str = billing_period_end.strftime("%Y-%m-%d")
        return f"Monthly Subscription ({start_str} to {end_str})"

    @staticmethod
    def create_aggregate_metadata(
        *,
        internal_reference_ids: list[str] = None,
        billing_period: str = None,
        office_id: int = None,
        **additional_sanitized_data,
    ) -> str:
        """Create aggregate metadata JSON without ePHI"""
        metadata = {
            "aggregate_data": True,
            "ephi_stripped": True,
            "created_at": datetime.utcnow().isoformat(),
        }

        if internal_reference_ids:
            # Store only count, not actual IDs
            metadata["internal_reference_count"] = len(internal_reference_ids)

        if billing_period:
            metadata["billing_period"] = billing_period

        if office_id:
            metadata["office_id"] = office_id

        # Add any additional sanitized data
        metadata.update(additional_sanitized_data)

        return json.dumps(metadata, separators=(",", ":"))  # Compact JSON
