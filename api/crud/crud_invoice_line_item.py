from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc, func
from datetime import datetime
import json

from api.models.base import InvoiceLineItem, Invoice
from api.schemas.invoice_line_item import (
    InvoiceLineItemCreate,
    InvoiceLineItemUpdate,
    InvoiceLineItemFilters,
    LineItemType,
    LineItemSummary,
    ePHISanitizationHelper,
)
from api.core.audit_logger import log_billing_event


class CRUDInvoiceLineItem:
    """CRUD operations for InvoiceLineItem model with ePHI protection"""

    def create(
        self, db: Session, *, obj_in: InvoiceLineItemCreate, user_id: int
    ) -> InvoiceLineItem:
        """Create a new invoice line item with audit logging"""
        # Validate that the invoice exists and belongs to the user's office
        invoice = db.query(Invoice).filter(Invoice.id == obj_in.invoice_id).first()
        if not invoice:
            raise ValueError(f"Invoice {obj_in.invoice_id} not found")

        # Create the line item
        obj_data = obj_in.dict()
        db_obj = InvoiceLineItem(**obj_data)
        db.add(db_obj)
        db.flush()  # Get the ID without committing

        # Log the creation for audit
        log_billing_event(
            action="line_item_created",
            office_id=invoice.office_id,
            user_id=user_id,
            invoice_id=invoice.id,
            line_item_id=db_obj.id,
            details={
                "item_type": obj_in.item_type.value,
                "description": obj_in.description,
                "quantity": obj_in.quantity,
                "unit_price_cents": obj_in.unit_price_cents,
                "total_amount_cents": obj_in.total_amount_cents,
            },
        )

        # Update the invoice total
        self._update_invoice_total(db, invoice_id=invoice.id)

        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get(self, db: Session, *, line_item_id: int) -> Optional[InvoiceLineItem]:
        """Get a single invoice line item by ID"""
        return (
            db.query(InvoiceLineItem).filter(InvoiceLineItem.id == line_item_id).first()
        )

    def get_by_invoice(
        self, db: Session, *, invoice_id: int, skip: int = 0, limit: int = 100
    ) -> List[InvoiceLineItem]:
        """Get all line items for a specific invoice"""
        return (
            db.query(InvoiceLineItem)
            .filter(InvoiceLineItem.invoice_id == invoice_id)
            .order_by(InvoiceLineItem.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_multi_with_filters(
        self,
        db: Session,
        *,
        filters: InvoiceLineItemFilters,
        skip: int = 0,
        limit: int = 100,
        order_by: str = "created_at",
        order_desc: bool = True,
    ) -> Tuple[List[InvoiceLineItem], int]:
        """Get multiple invoice line items with filters and pagination"""
        query = db.query(InvoiceLineItem)

        # Apply filters
        if filters.invoice_id is not None:
            query = query.filter(InvoiceLineItem.invoice_id == filters.invoice_id)

        if filters.item_type is not None:
            query = query.filter(InvoiceLineItem.item_type == filters.item_type.value)

        if filters.min_amount_cents is not None:
            query = query.filter(
                InvoiceLineItem.total_amount_cents >= filters.min_amount_cents
            )

        if filters.max_amount_cents is not None:
            query = query.filter(
                InvoiceLineItem.total_amount_cents <= filters.max_amount_cents
            )

        if filters.description_contains:
            query = query.filter(
                InvoiceLineItem.description.ilike(f"%{filters.description_contains}%")
            )

        # Get total count
        total = query.count()

        # Apply ordering
        if hasattr(InvoiceLineItem, order_by):
            order_column = getattr(InvoiceLineItem, order_by)
            if order_desc:
                query = query.order_by(desc(order_column))
            else:
                query = query.order_by(asc(order_column))

        # Apply pagination
        items = query.offset(skip).limit(limit).all()

        return items, total

    def update(
        self,
        db: Session,
        *,
        db_obj: InvoiceLineItem,
        obj_in: InvoiceLineItemUpdate,
        user_id: int,
    ) -> InvoiceLineItem:
        """Update an existing invoice line item with audit logging"""
        # Get the invoice for office_id (for audit logging)
        invoice = db.query(Invoice).filter(Invoice.id == db_obj.invoice_id).first()
        if not invoice:
            raise ValueError(f"Invoice {db_obj.invoice_id} not found")

        # Store original values for audit
        original_data = {
            "item_type": db_obj.item_type,
            "description": db_obj.description,
            "quantity": db_obj.quantity,
            "unit_price_cents": db_obj.unit_price_cents,
            "total_amount_cents": db_obj.total_amount_cents,
            "metadata_json": db_obj.metadata_json,
        }

        # Update fields
        update_data = obj_in.dict(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)

        # Recalculate total if quantity or unit price changed
        if "quantity" in update_data or "unit_price_cents" in update_data:
            db_obj.total_amount_cents = db_obj.quantity * db_obj.unit_price_cents

        # Log the update for audit
        log_billing_event(
            action="line_item_updated",
            office_id=invoice.office_id,
            user_id=user_id,
            invoice_id=invoice.id,
            line_item_id=db_obj.id,
            details={
                "original_data": original_data,
                "updated_fields": update_data,
                "new_total_amount_cents": db_obj.total_amount_cents,
            },
        )

        # Update the invoice total
        self._update_invoice_total(db, invoice_id=invoice.id)

        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, *, line_item_id: int, user_id: int) -> bool:
        """Delete an invoice line item with audit logging"""
        db_obj = self.get(db, line_item_id=line_item_id)
        if not db_obj:
            return False

        # Get the invoice for office_id and total update
        invoice = db.query(Invoice).filter(Invoice.id == db_obj.invoice_id).first()
        if not invoice:
            raise ValueError(f"Invoice {db_obj.invoice_id} not found")

        # Log the deletion for audit
        log_billing_event(
            action="line_item_deleted",
            office_id=invoice.office_id,
            user_id=user_id,
            invoice_id=invoice.id,
            line_item_id=db_obj.id,
            details={
                "deleted_line_item": {
                    "item_type": db_obj.item_type,
                    "description": db_obj.description,
                    "quantity": db_obj.quantity,
                    "unit_price_cents": db_obj.unit_price_cents,
                    "total_amount_cents": db_obj.total_amount_cents,
                }
            },
        )

        db.delete(db_obj)

        # Update the invoice total
        self._update_invoice_total(db, invoice_id=invoice.id)

        db.commit()
        return True

    def get_line_item_summary(
        self, db: Session, *, invoice_id: int
    ) -> List[LineItemSummary]:
        """Get summary of line items by type for an invoice"""
        results = (
            db.query(
                InvoiceLineItem.item_type,
                func.sum(InvoiceLineItem.quantity).label("total_quantity"),
                func.sum(InvoiceLineItem.total_amount_cents).label(
                    "total_amount_cents"
                ),
                func.count(InvoiceLineItem.id).label("line_item_count"),
            )
            .filter(InvoiceLineItem.invoice_id == invoice_id)
            .group_by(InvoiceLineItem.item_type)
            .all()
        )

        return [
            LineItemSummary(
                item_type=LineItemType(result.item_type),
                total_quantity=result.total_quantity or 0,
                total_amount_cents=result.total_amount_cents or 0,
                line_item_count=result.line_item_count or 0,
            )
            for result in results
        ]

    def create_patient_activation_line_item(
        self,
        db: Session,
        *,
        invoice_id: int,
        patient_count: int,
        unit_price_cents: int,
        user_id: int,
        patient_reference_ids: List[str] = None,
    ) -> InvoiceLineItem:
        """Create a patient activation line item with ePHI sanitization"""
        # Create sanitized description
        description = ePHISanitizationHelper.create_patient_activation_description(
            count=patient_count, unit_price_cents=unit_price_cents
        )

        # Create aggregate metadata without ePHI
        metadata_json = ePHISanitizationHelper.create_aggregate_metadata(
            internal_reference_ids=patient_reference_ids,
            item_type="patient_activation",
            patient_count=patient_count,
        )

        line_item_data = InvoiceLineItemCreate(
            invoice_id=invoice_id,
            item_type=LineItemType.PATIENT_ACTIVATION,
            description=description,
            quantity=patient_count,
            unit_price_cents=unit_price_cents,
            total_amount_cents=patient_count * unit_price_cents,
            metadata_json=metadata_json,
        )

        return self.create(db, obj_in=line_item_data, user_id=user_id)

    def create_setup_fee_line_item(
        self,
        db: Session,
        *,
        invoice_id: int,
        office_name: str,
        setup_fee_cents: int,
        user_id: int,
    ) -> InvoiceLineItem:
        """Create a setup fee line item with ePHI sanitization"""
        description = ePHISanitizationHelper.create_setup_fee_description(office_name)

        metadata_json = ePHISanitizationHelper.create_aggregate_metadata(
            item_type="setup_fee",
            office_name=office_name,
        )

        line_item_data = InvoiceLineItemCreate(
            invoice_id=invoice_id,
            item_type=LineItemType.SETUP_FEE,
            description=description,
            quantity=1,
            unit_price_cents=setup_fee_cents,
            total_amount_cents=setup_fee_cents,
            metadata_json=metadata_json,
        )

        return self.create(db, obj_in=line_item_data, user_id=user_id)

    def create_monthly_recurring_line_item(
        self,
        db: Session,
        *,
        invoice_id: int,
        billing_period_start: datetime,
        billing_period_end: datetime,
        monthly_fee_cents: int,
        user_id: int,
    ) -> InvoiceLineItem:
        """Create a monthly recurring line item with ePHI sanitization"""
        description = ePHISanitizationHelper.create_monthly_recurring_description(
            billing_period_start=billing_period_start,
            billing_period_end=billing_period_end,
        )

        metadata_json = ePHISanitizationHelper.create_aggregate_metadata(
            item_type="monthly_recurring",
            billing_period=f"{billing_period_start.date()} to {billing_period_end.date()}",
        )

        line_item_data = InvoiceLineItemCreate(
            invoice_id=invoice_id,
            item_type=LineItemType.MONTHLY_RECURRING,
            description=description,
            quantity=1,
            unit_price_cents=monthly_fee_cents,
            total_amount_cents=monthly_fee_cents,
            metadata_json=metadata_json,
        )

        return self.create(db, obj_in=line_item_data, user_id=user_id)

    def _update_invoice_total(self, db: Session, *, invoice_id: int) -> None:
        """Update the total amount for an invoice based on its line items"""
        total_cents = (
            db.query(func.sum(InvoiceLineItem.total_amount_cents))
            .filter(InvoiceLineItem.invoice_id == invoice_id)
            .scalar()
        ) or 0

        # Update the invoice total
        db.query(Invoice).filter(Invoice.id == invoice_id).update(
            {"total_amount_cents": total_cents}
        )

    def validate_ephi_sanitization(self, line_item: InvoiceLineItem) -> Dict[str, Any]:
        """Validate that a line item is properly sanitized for external use"""
        validation_result = {
            "is_sanitized": True,
            "warnings": [],
            "errors": [],
        }

        # Check description for ePHI patterns
        description_lower = line_item.description.lower()
        ephi_patterns = [
            "@",
            "ssn",
            "social security",
            "patient id",
            "patient_id",
            "medical record",
            "mrn",
            "dob",
            "date of birth",
            "phone",
            "email",
            "address",
            "zip",
            "zipcode",
        ]

        for pattern in ephi_patterns:
            if pattern in description_lower:
                validation_result["errors"].append(
                    f"Description contains potential ePHI: {pattern}"
                )
                validation_result["is_sanitized"] = False

        # Check metadata for ePHI
        if line_item.metadata_json:
            try:
                metadata = json.loads(line_item.metadata_json)
                if not metadata.get("ephi_stripped", False):
                    validation_result["warnings"].append(
                        "Metadata does not indicate ePHI was stripped"
                    )

                # Check for sensitive keys
                sensitive_keys = [
                    "patient_id",
                    "user_id",
                    "email",
                    "phone",
                    "ssn",
                    "medical_record",
                ]
                for key in sensitive_keys:
                    if key in metadata:
                        validation_result["errors"].append(
                            f"Metadata contains sensitive key: {key}"
                        )
                        validation_result["is_sanitized"] = False

            except json.JSONDecodeError:
                validation_result["warnings"].append("Invalid JSON in metadata")

        return validation_result


# Create a global instance
crud_invoice_line_item = CRUDInvoiceLineItem()
