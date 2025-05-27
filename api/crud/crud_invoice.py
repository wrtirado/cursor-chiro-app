from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc
from datetime import datetime

from api.models.base import Invoice
from api.schemas.invoice import (
    InvoiceCreate,
    InvoiceUpdate,
    InvoiceFilters,
    InvoiceStatus,
    InvoiceType,
)
from api.core.audit_logger import log_billing_event


class CRUDInvoice:
    """CRUD operations for Invoice model"""

    def create(self, db: Session, *, obj_in: InvoiceCreate, user_id: int) -> Invoice:
        """Create a new invoice with audit logging"""
        db_obj = Invoice(**obj_in.dict())
        db.add(db_obj)
        db.flush()  # Get the ID without committing

        # Log invoice creation
        log_billing_event(
            action="invoice_created",
            invoice_id=db_obj.id,
            office_id=db_obj.office_id,
            user_id=user_id,
            details={
                "invoice_type": db_obj.invoice_type,
                "total_amount_cents": db_obj.total_amount_cents,
                "billing_period_start": (
                    db_obj.billing_period_start.isoformat()
                    if db_obj.billing_period_start
                    else None
                ),
                "billing_period_end": (
                    db_obj.billing_period_end.isoformat()
                    if db_obj.billing_period_end
                    else None
                ),
            },
        )

        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get(self, db: Session, id: int) -> Optional[Invoice]:
        """Get invoice by ID"""
        return db.query(Invoice).filter(Invoice.id == id).first()

    def get_by_office(
        self, db: Session, office_id: int, skip: int = 0, limit: int = 100
    ) -> List[Invoice]:
        """Get invoices for a specific office"""
        return (
            db.query(Invoice)
            .filter(Invoice.office_id == office_id)
            .order_by(desc(Invoice.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_stripe_id(
        self, db: Session, stripe_invoice_id: str
    ) -> Optional[Invoice]:
        """Get invoice by Stripe invoice ID"""
        return (
            db.query(Invoice)
            .filter(Invoice.stripe_invoice_id == stripe_invoice_id)
            .first()
        )

    def get_multi_filtered(
        self,
        db: Session,
        *,
        filters: InvoiceFilters,
        skip: int = 0,
        limit: int = 100,
        order_by: str = "created_at",
        order_desc: bool = True,
    ) -> List[Invoice]:
        """Get invoices with advanced filtering"""
        query = db.query(Invoice)

        # Apply filters
        if filters.office_id is not None:
            query = query.filter(Invoice.office_id == filters.office_id)

        if filters.status is not None:
            query = query.filter(Invoice.status == filters.status)

        if filters.invoice_type is not None:
            query = query.filter(Invoice.invoice_type == filters.invoice_type)

        if filters.billing_period_start_after is not None:
            query = query.filter(
                Invoice.billing_period_start >= filters.billing_period_start_after
            )

        if filters.billing_period_start_before is not None:
            query = query.filter(
                Invoice.billing_period_start <= filters.billing_period_start_before
            )

        if filters.stripe_invoice_id is not None:
            query = query.filter(Invoice.stripe_invoice_id == filters.stripe_invoice_id)

        # Apply ordering
        order_column = getattr(Invoice, order_by, Invoice.created_at)
        if order_desc:
            query = query.order_by(desc(order_column))
        else:
            query = query.order_by(asc(order_column))

        return query.offset(skip).limit(limit).all()

    def count_filtered(self, db: Session, *, filters: InvoiceFilters) -> int:
        """Count invoices matching filters"""
        query = db.query(Invoice)

        # Apply same filters as get_multi_filtered
        if filters.office_id is not None:
            query = query.filter(Invoice.office_id == filters.office_id)

        if filters.status is not None:
            query = query.filter(Invoice.status == filters.status)

        if filters.invoice_type is not None:
            query = query.filter(Invoice.invoice_type == filters.invoice_type)

        if filters.billing_period_start_after is not None:
            query = query.filter(
                Invoice.billing_period_start >= filters.billing_period_start_after
            )

        if filters.billing_period_start_before is not None:
            query = query.filter(
                Invoice.billing_period_start <= filters.billing_period_start_before
            )

        if filters.stripe_invoice_id is not None:
            query = query.filter(Invoice.stripe_invoice_id == filters.stripe_invoice_id)

        return query.count()

    def update(
        self, db: Session, *, db_obj: Invoice, obj_in: InvoiceUpdate, user_id: int
    ) -> Invoice:
        """Update invoice with audit logging"""
        # Track changes for audit log
        changes = {}
        update_data = obj_in.dict(exclude_unset=True)

        for field, value in update_data.items():
            old_value = getattr(db_obj, field)
            if old_value != value:
                changes[field] = {"old": old_value, "new": value}
                setattr(db_obj, field, value)

        if changes:
            # Update timestamp
            db_obj.updated_at = datetime.utcnow()

            # Log the update
            log_billing_event(
                action="invoice_updated",
                invoice_id=db_obj.id,
                office_id=db_obj.office_id,
                user_id=user_id,
                details={"changes": changes},
            )

            db.commit()
            db.refresh(db_obj)

        return db_obj

    def update_status(
        self, db: Session, *, db_obj: Invoice, status: InvoiceStatus, user_id: int
    ) -> Invoice:
        """Update invoice status with specific audit logging"""
        old_status = db_obj.status
        db_obj.status = status
        db_obj.updated_at = datetime.utcnow()

        # Log status change
        log_billing_event(
            action="invoice_status_changed",
            invoice_id=db_obj.id,
            office_id=db_obj.office_id,
            user_id=user_id,
            details={
                "old_status": old_status,
                "new_status": status,
                "total_amount_cents": db_obj.total_amount_cents,
            },
        )

        db.commit()
        db.refresh(db_obj)
        return db_obj

    def cancel(self, db: Session, *, db_obj: Invoice, user_id: int) -> Invoice:
        """Cancel invoice (soft delete) with audit logging"""
        return self.update_status(
            db=db, db_obj=db_obj, status=InvoiceStatus.CANCELLED, user_id=user_id
        )

    def get_pending_invoices(
        self, db: Session, office_id: Optional[int] = None
    ) -> List[Invoice]:
        """Get all pending invoices, optionally filtered by office"""
        query = db.query(Invoice).filter(Invoice.status == InvoiceStatus.PENDING)

        if office_id is not None:
            query = query.filter(Invoice.office_id == office_id)

        return query.order_by(desc(Invoice.created_at)).all()

    def get_monthly_invoices_for_period(
        self,
        db: Session,
        billing_period_start: datetime,
        office_id: Optional[int] = None,
    ) -> List[Invoice]:
        """Get monthly invoices for a specific billing period"""
        query = db.query(Invoice).filter(
            and_(
                Invoice.invoice_type == InvoiceType.MONTHLY,
                Invoice.billing_period_start == billing_period_start,
            )
        )

        if office_id is not None:
            query = query.filter(Invoice.office_id == office_id)

        return query.all()

    def search(
        self,
        db: Session,
        *,
        query: str,
        office_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Invoice]:
        """Search invoices by notes or Stripe invoice ID"""
        search_filter = or_(
            Invoice.notes.ilike(f"%{query}%"),
            Invoice.stripe_invoice_id.ilike(f"%{query}%"),
        )

        db_query = db.query(Invoice).filter(search_filter)

        if office_id is not None:
            db_query = db_query.filter(Invoice.office_id == office_id)

        return (
            db_query.order_by(desc(Invoice.created_at)).offset(skip).limit(limit).all()
        )

    def get_invoice_statistics(self, db: Session, office_id: int) -> Dict[str, Any]:
        """Get invoice statistics for an office"""
        from sqlalchemy import func

        stats = (
            db.query(
                func.count(Invoice.id).label("total_invoices"),
                func.sum(Invoice.total_amount_cents).label("total_amount_cents"),
                func.count(
                    Invoice.id.filter(Invoice.status == InvoiceStatus.PAID)
                ).label("paid_invoices"),
                func.count(
                    Invoice.id.filter(Invoice.status == InvoiceStatus.PENDING)
                ).label("pending_invoices"),
                func.count(
                    Invoice.id.filter(Invoice.status == InvoiceStatus.FAILED)
                ).label("failed_invoices"),
            )
            .filter(Invoice.office_id == office_id)
            .first()
        )

        return {
            "total_invoices": stats.total_invoices or 0,
            "total_amount_cents": stats.total_amount_cents or 0,
            "paid_invoices": stats.paid_invoices or 0,
            "pending_invoices": stats.pending_invoices or 0,
            "failed_invoices": stats.failed_invoices or 0,
        }


# Create the CRUD instance
crud_invoice = CRUDInvoice()
