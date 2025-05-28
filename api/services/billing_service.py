"""
Billing Service for Patient Activation Logic

This service handles the business logic for billing patient activations,
ensuring strict ePHI isolation and proper audit trails for HIPAA compliance.
"""

from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import uuid
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

from api.models.base import User, Invoice, Office
from api.schemas.invoice import InvoiceCreate, InvoiceType, InvoiceStatus
from api.schemas.invoice_line_item import LineItemType
from api.crud.crud_invoice import crud_invoice
from api.crud.crud_invoice_line_item import crud_invoice_line_item
from api.crud.crud_user import update_last_billed_cycle
from api.core.audit_logger import log_billing_event


class PatientActivationBillingService:
    """
    Service for handling patient activation billing with strict ePHI isolation.

    This service implements a two-tier data architecture:
    1. Internal tracking with full ePHI data for audit and operational purposes
    2. External billing with sanitized aggregate data for Stripe integration
    """

    # Billing configuration (should eventually come from settings/config)
    PATIENT_ACTIVATION_FEE_CENTS = 200  # $2.00 per patient activation
    MONTHLY_BILLING_DAY = 1  # First day of month for billing cycle start

    def __init__(self):
        self.ephi_isolation_enabled = True

    def activate_patient_for_billing(
        self,
        db: Session,
        patient_id: int,
        admin_user_id: int,
        office_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Activate a patient for billing and automatically create billing line item.

        Returns comprehensive result with internal tracking and external billing info.
        """
        # Get the patient
        patient = db.query(User).filter(User.user_id == patient_id).first()
        if not patient:
            raise ValueError(f"Patient {patient_id} not found")

        # Use patient's office or provided office_id
        target_office_id = office_id or patient.office_id
        if not target_office_id:
            raise ValueError(f"Patient {patient_id} has no associated office")

        # Check if patient is already active for billing
        if patient.is_active_for_billing:
            return self._handle_patient_reactivation(
                db, patient, admin_user_id, target_office_id
            )

        # Activate the patient (update user record)
        activation_time = datetime.utcnow()
        patient.is_active_for_billing = True
        patient.activated_at = activation_time
        patient.deactivated_at = None  # Clear any previous deactivation

        # Get or create current billing period invoice
        current_period_start = self._get_current_billing_period_start()
        current_period_end = self._get_current_billing_period_end(current_period_start)

        invoice = self._get_or_create_monthly_invoice(
            db,
            target_office_id,
            current_period_start,
            current_period_end,
            admin_user_id,
        )

        # Create internal tracking record for audit (with ePHI)
        internal_tracking = self._create_internal_activation_record(
            patient_id=patient_id,
            office_id=target_office_id,
            invoice_id=invoice.id,
            activation_time=activation_time,
            admin_user_id=admin_user_id,
        )

        # Create sanitized billing line item (no ePHI)
        line_item = self._create_patient_activation_line_item(
            db,
            invoice_id=invoice.id,
            patient_count=1,  # Single activation
            admin_user_id=admin_user_id,
            internal_reference=internal_tracking["reference_id"],
        )

        # Log the activation for audit
        log_billing_event(
            action="user_activated_for_billing",
            office_id=target_office_id,
            user_id=admin_user_id,
            patient_id=patient_id,
            invoice_id=invoice.id,
            line_item_id=line_item.id,
            details={
                "activation_time": activation_time.isoformat(),
                "billing_period_start": current_period_start.isoformat(),
                "patient_name": patient.name,  # ePHI for internal audit only
                "fee_cents": self.PATIENT_ACTIVATION_FEE_CENTS,
                "internal_tracking_id": internal_tracking["reference_id"],
            },
        )

        db.commit()

        return {
            "success": True,
            "patient_id": patient_id,
            "office_id": target_office_id,
            "activation_time": activation_time,
            "invoice_id": invoice.id,
            "line_item_id": line_item.id,
            "fee_cents": self.PATIENT_ACTIVATION_FEE_CENTS,
            "internal_tracking": internal_tracking,
            "billing_period": {
                "start": current_period_start,
                "end": current_period_end,
            },
        }

    def deactivate_patient_for_billing(
        self,
        db: Session,
        patient_id: int,
        admin_user_id: int,
        reason: str = "manual_deactivation",
    ) -> Dict[str, Any]:
        """
        Deactivate a patient for billing (no line item created for deactivation).
        """
        patient = db.query(User).filter(User.user_id == patient_id).first()
        if not patient:
            raise ValueError(f"Patient {patient_id} not found")

        if not patient.is_active_for_billing:
            raise ValueError(f"Patient {patient_id} is already inactive for billing")

        # Deactivate the patient
        deactivation_time = datetime.utcnow()
        patient.is_active_for_billing = False
        patient.deactivated_at = deactivation_time

        # Log the deactivation for audit
        log_billing_event(
            action="user_deactivated_for_billing",
            office_id=patient.office_id,
            user_id=admin_user_id,
            patient_id=patient_id,
            details={
                "deactivation_time": deactivation_time.isoformat(),
                "reason": reason,
                "patient_name": patient.name,  # ePHI for internal audit only
                "was_active_since": (
                    patient.activated_at.isoformat() if patient.activated_at else None
                ),
            },
        )

        db.commit()

        return {
            "success": True,
            "patient_id": patient_id,
            "office_id": patient.office_id,
            "deactivation_time": deactivation_time,
            "reason": reason,
        }

    def get_current_billing_period_summary(
        self, db: Session, office_id: int
    ) -> Dict[str, Any]:
        """
        Get summary of current billing period activations for an office.
        Returns sanitized data suitable for external systems.
        """
        current_period_start = self._get_current_billing_period_start()
        current_period_end = self._get_current_billing_period_end(current_period_start)

        # Get the current period invoice
        invoices = crud_invoice.get_monthly_invoices_for_period(
            db, current_period_start, office_id
        )

        if not invoices:
            return {
                "office_id": office_id,
                "billing_period_start": current_period_start,
                "billing_period_end": current_period_end,
                "has_invoice": False,
                "patient_activations": 0,
                "total_activation_fees_cents": 0,
                "line_items": [],
            }

        invoice = invoices[0]  # Should only be one monthly invoice per period

        # Get patient activation line items
        line_items = crud_invoice_line_item.get_by_invoice(db, invoice_id=invoice.id)
        activation_line_items = [
            item
            for item in line_items
            if item.item_type == LineItemType.PATIENT_ACTIVATION.value
        ]

        total_activations = sum(item.quantity for item in activation_line_items)
        total_fees = sum(item.total_amount_cents for item in activation_line_items)

        return {
            "office_id": office_id,
            "billing_period_start": current_period_start,
            "billing_period_end": current_period_end,
            "has_invoice": True,
            "invoice_id": invoice.id,
            "patient_activations": total_activations,
            "total_activation_fees_cents": total_fees,
            "line_items": [
                {
                    "id": item.id,
                    "description": item.description,  # Already sanitized
                    "quantity": item.quantity,
                    "unit_price_cents": item.unit_price_cents,
                    "total_amount_cents": item.total_amount_cents,
                    "created_at": item.created_at,
                }
                for item in activation_line_items
            ],
        }

    def _handle_patient_reactivation(
        self,
        db: Session,
        patient: User,
        admin_user_id: int,
        office_id: int,
    ) -> Dict[str, Any]:
        """
        Handle reactivation of a patient who was previously active.

        For now, if they're already active, we'll just update the activation time
        and create a new line item (treating it as a fresh activation).
        """
        # Update activation time
        reactivation_time = datetime.utcnow()
        patient.activated_at = reactivation_time
        patient.deactivated_at = None

        # Get current billing period
        current_period_start = self._get_current_billing_period_start()
        current_period_end = self._get_current_billing_period_end(current_period_start)

        invoice = self._get_or_create_monthly_invoice(
            db, office_id, current_period_start, current_period_end, admin_user_id
        )

        # Create internal tracking record
        internal_tracking = self._create_internal_activation_record(
            patient_id=patient.user_id,
            office_id=office_id,
            invoice_id=invoice.id,
            activation_time=reactivation_time,
            admin_user_id=admin_user_id,
            is_reactivation=True,
        )

        # Create billing line item for reactivation
        line_item = self._create_patient_activation_line_item(
            db,
            invoice_id=invoice.id,
            patient_count=1,
            admin_user_id=admin_user_id,
            internal_reference=internal_tracking["reference_id"],
        )

        # Log the reactivation
        log_billing_event(
            action="user_reactivated_for_billing",
            office_id=office_id,
            user_id=admin_user_id,
            patient_id=patient.user_id,
            invoice_id=invoice.id,
            line_item_id=line_item.id,
            details={
                "reactivation_time": reactivation_time.isoformat(),
                "previous_activation": (
                    patient.activated_at.isoformat() if patient.activated_at else None
                ),
                "patient_name": patient.name,  # ePHI for internal audit only
                "fee_cents": self.PATIENT_ACTIVATION_FEE_CENTS,
                "internal_tracking_id": internal_tracking["reference_id"],
            },
        )

        return {
            "success": True,
            "patient_id": patient.user_id,
            "office_id": office_id,
            "reactivation_time": reactivation_time,
            "invoice_id": invoice.id,
            "line_item_id": line_item.id,
            "fee_cents": self.PATIENT_ACTIVATION_FEE_CENTS,
            "internal_tracking": internal_tracking,
            "is_reactivation": True,
        }

    def _get_current_billing_period_start(self) -> datetime:
        """Get the start of the current billing period (1st of current month)"""
        now = datetime.utcnow()
        return datetime(now.year, now.month, self.MONTHLY_BILLING_DAY)

    def _get_current_billing_period_end(self, period_start: datetime) -> datetime:
        """Get the end of the billing period (last day of the month)"""
        next_month = period_start + relativedelta(months=1)
        return next_month - timedelta(seconds=1)

    def _get_or_create_monthly_invoice(
        self,
        db: Session,
        office_id: int,
        billing_period_start: datetime,
        billing_period_end: datetime,
        admin_user_id: int,
    ) -> Invoice:
        """Get or create the monthly invoice for the given billing period"""
        # Try to find existing monthly invoice
        existing_invoices = crud_invoice.get_monthly_invoices_for_period(
            db, billing_period_start, office_id
        )

        if existing_invoices:
            return existing_invoices[0]

        # Create new monthly invoice
        invoice_data = InvoiceCreate(
            office_id=office_id,
            invoice_type=InvoiceType.MONTHLY,
            status=InvoiceStatus.PENDING,
            billing_period_start=billing_period_start,
            billing_period_end=billing_period_end,
            total_amount_cents=0,  # Will be updated as line items are added
            notes=f"Monthly billing for {billing_period_start.strftime('%B %Y')}",
        )

        return crud_invoice.create(db, obj_in=invoice_data, user_id=admin_user_id)

    def _create_internal_activation_record(
        self,
        patient_id: int,
        office_id: int,
        invoice_id: int,
        activation_time: datetime,
        admin_user_id: int,
        is_reactivation: bool = False,
    ) -> Dict[str, Any]:
        """
        Create internal tracking record for patient activation.

        This contains ePHI and is used for internal audit and operational purposes only.
        """
        reference_id = str(uuid.uuid4())

        return {
            "reference_id": reference_id,
            "patient_id": patient_id,
            "office_id": office_id,
            "invoice_id": invoice_id,
            "activation_time": activation_time,
            "admin_user_id": admin_user_id,
            "is_reactivation": is_reactivation,
            "fee_cents": self.PATIENT_ACTIVATION_FEE_CENTS,
            "ephi_stripped": False,  # This record contains ePHI
            "internal_use_only": True,
        }

    def _create_patient_activation_line_item(
        self,
        db: Session,
        invoice_id: int,
        patient_count: int,
        admin_user_id: int,
        internal_reference: str,
    ):
        """Create a sanitized patient activation line item for external billing"""
        return crud_invoice_line_item.create_patient_activation_line_item(
            db,
            invoice_id=invoice_id,
            patient_count=patient_count,
            unit_price_cents=self.PATIENT_ACTIVATION_FEE_CENTS,
            user_id=admin_user_id,
            patient_reference_ids=[internal_reference],  # Anonymous reference only
        )

    def validate_ephi_isolation(self, billing_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate that billing data is properly sanitized for external use.

        This ensures no ePHI is included in data sent to Stripe or other external systems.
        """
        validation_result = {
            "is_safe_for_external_use": True,
            "warnings": [],
            "errors": [],
            "sanitization_applied": True,
        }

        # Check for ePHI patterns in the data
        ephi_patterns = [
            "patient_id",
            "user_id",
            "email",
            "phone",
            "ssn",
            "medical_record",
            "patient_name",
            "full_name",
            "@",
        ]

        def check_value(value, path=""):
            if isinstance(value, str):
                value_lower = value.lower()
                for pattern in ephi_patterns:
                    if pattern in value_lower:
                        validation_result["errors"].append(
                            f"Potential ePHI found at {path}: {pattern}"
                        )
                        validation_result["is_safe_for_external_use"] = False

            elif isinstance(value, dict):
                for key, val in value.items():
                    key_lower = key.lower()
                    for pattern in ephi_patterns:
                        if pattern in key_lower:
                            validation_result["errors"].append(
                                f"Potential ePHI key found: {key}"
                            )
                            validation_result["is_safe_for_external_use"] = False
                    check_value(val, f"{path}.{key}" if path else key)

            elif isinstance(value, list):
                for i, val in enumerate(value):
                    check_value(val, f"{path}[{i}]" if path else f"[{i}]")

        check_value(billing_data)

        return validation_result

    def bulk_activate_patients_for_billing(
        self,
        db: Session,
        patient_ids: List[int],
        admin_user_id: int,
        office_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Bulk activate multiple patients for billing with aggregated line items.

        This creates a single line item with the total count instead of individual line items.
        """
        successful_activations = []
        failed_activations = []

        # Group patients by office for bulk processing
        office_patient_groups = {}

        for patient_id in patient_ids:
            patient = db.query(User).filter(User.user_id == patient_id).first()
            if not patient:
                failed_activations.append(
                    {"patient_id": patient_id, "error": "Patient not found"}
                )
                continue

            target_office_id = office_id or patient.office_id
            if not target_office_id:
                failed_activations.append(
                    {"patient_id": patient_id, "error": "No associated office"}
                )
                continue

            if target_office_id not in office_patient_groups:
                office_patient_groups[target_office_id] = []
            office_patient_groups[target_office_id].append(patient)

        # Process each office group
        total_activated = 0
        invoices_created = []

        for target_office_id, patients in office_patient_groups.items():
            try:
                # Get or create invoice for this office
                current_period_start = self._get_current_billing_period_start()
                current_period_end = self._get_current_billing_period_end(
                    current_period_start
                )

                invoice = self._get_or_create_monthly_invoice(
                    db,
                    target_office_id,
                    current_period_start,
                    current_period_end,
                    admin_user_id,
                )

                # Track internal references for this batch
                internal_references = []
                activation_time = datetime.utcnow()

                # Activate each patient in this office
                for patient in patients:
                    if not patient.is_active_for_billing:
                        # Activate the patient
                        patient.is_active_for_billing = True
                        patient.activated_at = activation_time
                        patient.deactivated_at = None

                        # Create internal tracking
                        internal_tracking = self._create_internal_activation_record(
                            patient_id=patient.user_id,
                            office_id=target_office_id,
                            invoice_id=invoice.id,
                            activation_time=activation_time,
                            admin_user_id=admin_user_id,
                        )

                        internal_references.append(internal_tracking["reference_id"])
                        successful_activations.append(
                            {
                                "patient_id": patient.user_id,
                                "office_id": target_office_id,
                                "internal_tracking_id": internal_tracking[
                                    "reference_id"
                                ],
                            }
                        )

                        total_activated += 1

                # Create a single aggregated line item for this office
                if len(internal_references) > 0:
                    line_item = (
                        crud_invoice_line_item.create_patient_activation_line_item(
                            db,
                            invoice_id=invoice.id,
                            patient_count=len(internal_references),
                            unit_price_cents=self.PATIENT_ACTIVATION_FEE_CENTS,
                            user_id=admin_user_id,
                            patient_reference_ids=internal_references,
                        )
                    )

                    invoices_created.append(
                        {
                            "office_id": target_office_id,
                            "invoice_id": invoice.id,
                            "line_item_id": line_item.id,
                            "patients_activated": len(internal_references),
                            "total_amount_cents": len(internal_references)
                            * self.PATIENT_ACTIVATION_FEE_CENTS,
                        }
                    )

                    # Log bulk activation
                    log_billing_event(
                        action="bulk_patients_activated_for_billing",
                        office_id=target_office_id,
                        user_id=admin_user_id,
                        invoice_id=invoice.id,
                        line_item_id=line_item.id,
                        details={
                            "patients_activated": len(internal_references),
                            "activation_time": activation_time.isoformat(),
                            "total_fee_cents": len(internal_references)
                            * self.PATIENT_ACTIVATION_FEE_CENTS,
                            "internal_tracking_ids": internal_references,
                        },
                    )

            except Exception as e:
                # Add all patients in this office to failed list
                for patient in patients:
                    failed_activations.append(
                        {
                            "patient_id": patient.user_id,
                            "office_id": target_office_id,
                            "error": str(e),
                        }
                    )

        db.commit()

        return {
            "success": len(failed_activations) == 0,
            "total_processed": len(patient_ids),
            "successful_activations": total_activated,
            "failed_activations": len(failed_activations),
            "successful_details": successful_activations,
            "failed_details": failed_activations,
            "invoices_affected": invoices_created,
        }

    def get_billing_period_activations_summary(
        self,
        db: Session,
        billing_period_start: datetime,
        office_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Get summary of patient activations for a specific billing period.
        Returns sanitized data suitable for external reporting.
        """
        billing_period_end = self._get_current_billing_period_end(billing_period_start)

        # Get invoices for the period
        invoices = crud_invoice.get_monthly_invoices_for_period(
            db, billing_period_start, office_id
        )

        summary = {
            "billing_period_start": billing_period_start,
            "billing_period_end": billing_period_end,
            "office_id": office_id,
            "total_offices": 0,
            "total_invoices": len(invoices),
            "total_patient_activations": 0,
            "total_activation_fees_cents": 0,
            "office_summaries": [],
        }

        office_summaries = {}

        for invoice in invoices:
            office_id_key = invoice.office_id

            if office_id_key not in office_summaries:
                office_summaries[office_id_key] = {
                    "office_id": office_id_key,
                    "invoices": [],
                    "total_activations": 0,
                    "total_fees_cents": 0,
                }

            # Get patient activation line items for this invoice
            line_items = crud_invoice_line_item.get_by_invoice(
                db, invoice_id=invoice.id
            )
            activation_line_items = [
                item
                for item in line_items
                if item.item_type == LineItemType.PATIENT_ACTIVATION.value
            ]

            invoice_activations = sum(item.quantity for item in activation_line_items)
            invoice_fees = sum(
                item.total_amount_cents for item in activation_line_items
            )

            office_summaries[office_id_key]["invoices"].append(
                {
                    "invoice_id": invoice.id,
                    "activations": invoice_activations,
                    "fees_cents": invoice_fees,
                }
            )

            office_summaries[office_id_key]["total_activations"] += invoice_activations
            office_summaries[office_id_key]["total_fees_cents"] += invoice_fees

            summary["total_patient_activations"] += invoice_activations
            summary["total_activation_fees_cents"] += invoice_fees

        summary["total_offices"] = len(office_summaries)
        summary["office_summaries"] = list(office_summaries.values())

        return summary

    def update_billing_cycle_for_activated_patients(
        self,
        db: Session,
        billing_cycle_date: datetime,
        office_id: Optional[int] = None,
        admin_user_id: int = 1,  # Default system user
    ) -> Dict[str, Any]:
        """
        Update the last_billed_cycle for all active patients.
        This is typically called at the end of a billing period.
        """
        from api.crud.crud_user import (
            get_active_patients_for_billing,
            update_last_billed_cycle,
        )

        # Get all active patients for billing
        active_patients = get_active_patients_for_billing(db, office_id=office_id)

        updated_count = 0
        for patient in active_patients:
            try:
                update_last_billed_cycle(
                    db, user_id=patient.id, last_billed_cycle=billing_cycle_date
                )
                updated_count += 1
            except Exception as e:
                logger.error(
                    f"Failed to update billing cycle for patient {patient.id}: {e}"
                )

        result = {
            "billing_cycle_date": billing_cycle_date,
            "office_id": office_id,
            "patients_updated": updated_count,
            "total_patients_found": len(active_patients),
        }

        # Log the billing cycle update
        log_billing_event(
            action="billing_cycle_updated_for_office",
            office_id=office_id,
            user_id=admin_user_id,
            details={
                "billing_cycle_date": billing_cycle_date.isoformat(),
                "patients_updated": updated_count,
                "total_patients_found": len(active_patients),
            },
        )

        return result

    # ============================================================================
    # ONE-OFF INVOICE/CHARGE LOGIC
    # ============================================================================

    def create_one_off_invoice_for_office(
        self,
        db: Session,
        office_id: int,
        charge_description: str,
        amount_cents: int,
        admin_user_id: int = 1,
        charge_type: str = "setup_fee",
        metadata: Optional[Dict[str, Any]] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Create a one-off invoice for an office (e.g., setup fee).

        This handles charges outside the regular billing cycle such as:
        - Setup/onboarding fees
        - Special service charges
        - One-time consulting fees
        - Custom implementation charges

        Args:
            db: Database session
            office_id: Office to charge
            charge_description: Human-readable description of the charge
            amount_cents: Amount in cents (e.g., 5000 for $50.00)
            admin_user_id: User creating the charge
            charge_type: Type of charge (setup_fee, consulting, custom, etc.)
            metadata: Additional metadata for the charge
            dry_run: If True, simulate without creating data

        Returns:
            Dict with invoice details and results
        """
        from api.crud.crud_invoice import crud_invoice
        from api.crud.crud_invoice_line_item import crud_invoice_line_item

        try:
            if dry_run:
                logger.info(
                    f"[DRY RUN] Creating one-off invoice for office {office_id}"
                )
                return {
                    "success": True,
                    "dry_run": True,
                    "office_id": office_id,
                    "charge_type": charge_type,
                    "amount_cents": amount_cents,
                    "description": charge_description,
                    "message": "Dry run completed successfully",
                }

            # Validate ePHI isolation for the metadata
            if metadata:
                validation_result = self.validate_ephi_isolation(metadata)
                if not validation_result["is_safe_for_external_use"]:
                    raise ValueError(
                        f"ePHI detected in one-off charge metadata: {validation_result['errors']}"
                    )

            # Create or find current one-off invoice for the office
            current_date = datetime.now()

            # For one-off charges, we create a separate invoice immediately
            # rather than adding to monthly recurring invoices
            invoice_data = {
                "office_id": office_id,
                "billing_period_start": current_date,
                "billing_period_end": current_date,  # Same day for one-off charges
                "total_amount_cents": amount_cents,
                "status": "pending",
                "invoice_type": "one_off",  # Mark as one-off vs monthly
            }

            invoice = crud_invoice.create_one_off_invoice(
                db, obj_in=invoice_data, user_id=admin_user_id
            )

            # Create line item for the one-off charge
            line_item_data = {
                "invoice_id": invoice.id,
                "item_type": charge_type,
                "description": charge_description,
                "quantity": 1,
                "unit_price_cents": amount_cents,
                "total_amount_cents": amount_cents,
                "metadata_json": metadata or {},
            }

            line_item = crud_invoice_line_item.create_one_off_charge_line_item(
                db, obj_in=line_item_data, user_id=admin_user_id
            )

            # Log the one-off charge creation
            log_billing_event(
                action="one_off_charge_created",
                office_id=office_id,
                user_id=admin_user_id,
                details={
                    "invoice_id": invoice.id,
                    "line_item_id": line_item.id,
                    "charge_type": charge_type,
                    "amount_cents": amount_cents,
                    "description": charge_description,
                },
            )

            return {
                "success": True,
                "office_id": office_id,
                "invoice": {
                    "id": invoice.id,
                    "total_amount_cents": invoice.total_amount_cents,
                    "status": invoice.status,
                    "created_at": invoice.created_at,
                },
                "line_item": {
                    "id": line_item.id,
                    "charge_type": charge_type,
                    "description": charge_description,
                    "amount_cents": amount_cents,
                },
                "message": f"One-off {charge_type} invoice created successfully",
            }

        except Exception as e:
            logger.error(
                f"Failed to create one-off invoice for office {office_id}: {e}"
            )

            # Log the failure
            log_billing_event(
                action="one_off_charge_failed",
                office_id=office_id,
                user_id=admin_user_id,
                details={
                    "error": str(e),
                    "charge_type": charge_type,
                    "amount_cents": amount_cents,
                },
            )

            return {
                "success": False,
                "office_id": office_id,
                "error": str(e),
                "message": f"Failed to create one-off {charge_type} invoice",
            }

    def create_setup_fee_invoice(
        self,
        db: Session,
        office_id: int,
        setup_fee_cents: int = 5000,  # Default $50.00 setup fee
        admin_user_id: int = 1,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Create a setup fee invoice for an office.

        This is a convenience method for the common setup fee scenario.
        """
        return self.create_one_off_invoice_for_office(
            db=db,
            office_id=office_id,
            charge_description=f"Onboarding and setup service",
            amount_cents=setup_fee_cents,
            admin_user_id=admin_user_id,
            charge_type="setup_fee",
            metadata={
                "service_type": "onboarding",
                "includes": ["account_setup", "configuration", "training"],
            },
            dry_run=dry_run,
        )

    def bulk_create_setup_fees(
        self,
        db: Session,
        office_ids: List[int],
        setup_fee_cents: int = 5000,
        admin_user_id: int = 1,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Create setup fee invoices for multiple offices in bulk.

        Useful for processing multiple new office onboardings.
        """
        results = []
        successful_count = 0
        failed_count = 0

        for office_id in office_ids:
            result = self.create_setup_fee_invoice(
                db=db,
                office_id=office_id,
                setup_fee_cents=setup_fee_cents,
                admin_user_id=admin_user_id,
                dry_run=dry_run,
            )

            results.append(result)
            if result["success"]:
                successful_count += 1
            else:
                failed_count += 1

        # Log bulk operation
        log_billing_event(
            action="bulk_setup_fees_created",
            user_id=admin_user_id,
            details={
                "total_offices": len(office_ids),
                "successful_count": successful_count,
                "failed_count": failed_count,
                "setup_fee_cents": setup_fee_cents,
                "dry_run": dry_run,
            },
        )

        return {
            "success": failed_count == 0,
            "total_offices": len(office_ids),
            "successful_count": successful_count,
            "failed_count": failed_count,
            "setup_fee_cents": setup_fee_cents,
            "office_results": results,
            "message": f"Bulk setup fees: {successful_count} successful, {failed_count} failed",
        }

    def get_one_off_charges_summary(
        self,
        db: Session,
        office_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        charge_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get summary of one-off charges for reporting.

        Args:
            db: Database session
            office_id: Filter by specific office
            start_date: Filter charges from this date
            end_date: Filter charges until this date
            charge_type: Filter by charge type (setup_fee, consulting, etc.)

        Returns:
            Summary with aggregated data and individual charge details
        """
        from api.crud.crud_invoice import crud_invoice
        from api.crud.crud_invoice_line_item import crud_invoice_line_item

        try:
            # Get one-off invoices with filters
            invoices = crud_invoice.get_invoices_by_type(
                db,
                invoice_type="one_off",
                office_id=office_id,
                start_date=start_date,
                end_date=end_date,
            )

            # Get line items for these invoices
            invoice_ids = [inv.id for inv in invoices]
            line_items = crud_invoice_line_item.get_line_items_by_invoices(
                db, invoice_ids=invoice_ids, item_type=charge_type
            )

            # Calculate summary statistics
            total_charges = len(line_items)
            total_amount_cents = sum(item.total_amount_cents for item in line_items)
            unique_offices = len(set(inv.office_id for inv in invoices))

            # Group by charge type
            charges_by_type = {}
            for item in line_items:
                charge_type_key = item.item_type
                if charge_type_key not in charges_by_type:
                    charges_by_type[charge_type_key] = {
                        "count": 0,
                        "total_amount_cents": 0,
                        "charges": [],
                    }

                charges_by_type[charge_type_key]["count"] += 1
                charges_by_type[charge_type_key][
                    "total_amount_cents"
                ] += item.total_amount_cents
                charges_by_type[charge_type_key]["charges"].append(
                    {
                        "id": item.id,
                        "invoice_id": item.invoice_id,
                        "office_id": next(
                            inv.office_id
                            for inv in invoices
                            if inv.id == item.invoice_id
                        ),
                        "description": item.description,
                        "amount_cents": item.total_amount_cents,
                        "created_at": item.created_at,
                    }
                )

            return {
                "success": True,
                "summary": {
                    "total_charges": total_charges,
                    "total_amount_cents": total_amount_cents,
                    "unique_offices": unique_offices,
                    "date_range": {
                        "start_date": start_date.isoformat() if start_date else None,
                        "end_date": end_date.isoformat() if end_date else None,
                    },
                    "filter_criteria": {
                        "office_id": office_id,
                        "charge_type": charge_type,
                    },
                },
                "charges_by_type": charges_by_type,
                "invoices": [
                    {
                        "id": inv.id,
                        "office_id": inv.office_id,
                        "total_amount_cents": inv.total_amount_cents,
                        "status": inv.status,
                        "created_at": inv.created_at,
                    }
                    for inv in invoices
                ],
            }

        except Exception as e:
            logger.error(f"Failed to get one-off charges summary: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to retrieve one-off charges summary",
            }


# Create a global service instance
billing_service = PatientActivationBillingService()
