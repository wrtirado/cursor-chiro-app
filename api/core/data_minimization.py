"""
Data minimization utilities for payment processing and invoice generation.

This module implements strict data minimization practices to ensure NO ePHI
is transmitted to external payment processors like Stripe. It provides utilities
for sanitizing, filtering, and anonymizing billing data while maintaining
internal tracking capabilities for compliance and audit purposes.
"""

import os
import logging
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from datetime import datetime
import hashlib
import secrets
from enum import Enum

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger("audit")


class DataClassification(str, Enum):
    """Data classification levels for billing information."""

    SAFE_FOR_EXTERNAL = "safe_for_external"  # Can be sent to Stripe
    INTERNAL_ONLY = "internal_only"  # Internal tracking only
    EPHI = "ephi"  # Contains ePHI - NEVER external
    AGGREGATE_ONLY = "aggregate_only"  # Only aggregate data allowed


@dataclass
class SanitizationResult:
    """Result of data sanitization process."""

    sanitized_data: Dict[str, Any]
    removed_fields: List[str]
    classification: DataClassification
    audit_reference: str
    warnings: List[str]


class ePHIDetector:
    """
    Detects potential ePHI in billing data structures.

    This class identifies fields and data that may contain ePHI and should
    never be transmitted to external payment processors.
    """

    # Fields that definitely contain ePHI
    EPHI_FIELDS = {
        "patient_id",
        "patient_name",
        "patient_email",
        "patient_phone",
        "patient_address",
        "patient_dob",
        "patient_ssn",
        "medical_record_number",
        "diagnosis_code",
        "treatment_code",
        "medical_notes",
        "clinical_data",
        "user_id",
        "user_name",
        "user_email",
        "user_phone",  # User fields that might be patients
        "first_name",
        "last_name",
        "full_name",
        "email",
        "phone",
        "address",
        "birth_date",
        "date_of_birth",
        "ssn",
        "social_security_number",
    }

    # Fields that might contain ePHI depending on context
    POTENTIALLY_EPHI_FIELDS = {
        "name",
        "description",
        "notes",
        "comments",
        "reference",
        "identifier",
        "external_id",
        "user_reference",
    }

    # Fields that are safe for external transmission
    SAFE_EXTERNAL_FIELDS = {
        "office_id",
        "company_id",
        "invoice_id",
        "amount",
        "quantity",
        "unit_price",
        "total_price",
        "billing_period_start",
        "billing_period_end",
        "invoice_date",
        "due_date",
        "status",
        "created_at",
        "updated_at",
        "payment_provider_customer_id",
        "payment_provider_subscription_id",
        "line_item_type",
        "billing_cycle",
        "office_name",
        "company_name",
    }

    @classmethod
    def classify_field(cls, field_name: str, field_value: Any) -> DataClassification:
        """
        Classify a field based on its name and potentially its value.

        Args:
            field_name: The name of the field
            field_value: The value of the field

        Returns:
            DataClassification: The classification of the field
        """
        field_lower = field_name.lower()

        # Check for definite ePHI
        if any(ephi_field in field_lower for ephi_field in cls.EPHI_FIELDS):
            return DataClassification.EPHI

        # Check for safe external fields
        if field_lower in cls.SAFE_EXTERNAL_FIELDS:
            return DataClassification.SAFE_FOR_EXTERNAL

        # Check for potentially dangerous fields
        if any(pot_field in field_lower for pot_field in cls.POTENTIALLY_EPHI_FIELDS):
            # Additional checks based on value
            if isinstance(field_value, str):
                if cls._contains_personal_info(field_value):
                    return DataClassification.EPHI
            return DataClassification.INTERNAL_ONLY

        # Default to internal only for unknown fields
        return DataClassification.INTERNAL_ONLY

    @classmethod
    def _contains_personal_info(cls, value: str) -> bool:
        """
        Check if a string value might contain personal information.

        Args:
            value: String value to check

        Returns:
            bool: True if might contain personal info
        """
        if not value or len(value) < 3:
            return False

        value_lower = value.lower()

        # Check for email patterns
        if "@" in value and "." in value:
            return True

        # Check for phone number patterns
        if any(char.isdigit() for char in value) and len(value) >= 10:
            digit_count = sum(1 for char in value if char.isdigit())
            if digit_count >= 10:  # Likely phone number
                return True

        # Check for common personal identifiers
        personal_indicators = [
            "patient",
            "user",
            "client",
            "person",
            "individual",
            "name",
            "email",
            "phone",
            "address",
        ]

        return any(indicator in value_lower for indicator in personal_indicators)


class BillingDataSanitizer:
    """
    Sanitizes billing data to ensure no ePHI is transmitted to external systems.

    This class provides methods to clean and filter billing data structures,
    ensuring compliance with the no-BAA Stripe integration approach.
    """

    def __init__(self):
        self.detector = ePHIDetector()
        self._audit_counter = 0

    def sanitize_invoice_data(self, invoice_data: Dict[str, Any]) -> SanitizationResult:
        """
        Sanitize invoice data for external payment processing.

        Args:
            invoice_data: Raw invoice data structure

        Returns:
            SanitizationResult: Sanitized data and audit information
        """
        audit_ref = self._generate_audit_reference("invoice")
        sanitized = {}
        removed_fields = []
        warnings = []

        # Process each field in the invoice data
        for field, value in invoice_data.items():
            classification = self.detector.classify_field(field, value)

            if classification == DataClassification.SAFE_FOR_EXTERNAL:
                sanitized[field] = value
            elif classification == DataClassification.AGGREGATE_ONLY:
                # Handle aggregate data specially
                sanitized[field] = self._anonymize_aggregate_data(value)
            else:
                removed_fields.append(field)
                if classification == DataClassification.EPHI:
                    warnings.append(f"Removed ePHI field: {field}")

        # Add required anonymous identifiers
        sanitized["anonymous_invoice_ref"] = self._generate_anonymous_reference(
            invoice_data.get("invoice_id", "unknown")
        )

        # Log sanitization activity
        audit_logger.info(
            f"Invoice data sanitized - Audit ref: {audit_ref}, "
            f"Removed fields: {len(removed_fields)}, "
            f"ePHI warnings: {len(warnings)}"
        )

        return SanitizationResult(
            sanitized_data=sanitized,
            removed_fields=removed_fields,
            classification=DataClassification.SAFE_FOR_EXTERNAL,
            audit_reference=audit_ref,
            warnings=warnings,
        )

    def sanitize_line_items(
        self, line_items: List[Dict[str, Any]]
    ) -> SanitizationResult:
        """
        Sanitize invoice line items for external processing.

        Args:
            line_items: List of line item data structures

        Returns:
            SanitizationResult: Sanitized line items and audit information
        """
        audit_ref = self._generate_audit_reference("line_items")
        sanitized_items = []
        all_removed_fields = []
        warnings = []

        for item in line_items:
            # Convert individual patient line items to aggregate
            if self._is_patient_specific_item(item):
                # Aggregate similar items
                sanitized_item = self._aggregate_patient_line_item(item)
                warnings.append("Converted patient-specific item to aggregate")
            else:
                # Sanitize office-level items
                sanitized_item = {}
                for field, value in item.items():
                    classification = self.detector.classify_field(field, value)

                    if classification == DataClassification.SAFE_FOR_EXTERNAL:
                        sanitized_item[field] = value
                    else:
                        all_removed_fields.append(f"{field}")
                        if classification == DataClassification.EPHI:
                            warnings.append(
                                f"Removed ePHI field from line item: {field}"
                            )

            # Add anonymous reference for tracking
            sanitized_item["anonymous_line_ref"] = self._generate_anonymous_reference(
                f"line_{item.get('line_item_id', secrets.token_hex(4))}"
            )

            sanitized_items.append(sanitized_item)

        audit_logger.info(
            f"Line items sanitized - Audit ref: {audit_ref}, "
            f"Items processed: {len(line_items)}, "
            f"ePHI warnings: {len(warnings)}"
        )

        return SanitizationResult(
            sanitized_data={"line_items": sanitized_items},
            removed_fields=all_removed_fields,
            classification=DataClassification.SAFE_FOR_EXTERNAL,
            audit_reference=audit_ref,
            warnings=warnings,
        )

    def create_aggregate_billing_summary(
        self,
        office_data: Dict[str, Any],
        patient_count: int,
        billing_period: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Create an aggregate billing summary with no patient identifiers.

        Args:
            office_data: Office information (already sanitized)
            patient_count: Number of active patients
            billing_period: Billing period information

        Returns:
            Dict[str, Any]: Aggregate billing summary safe for external transmission
        """
        summary = {
            "billing_summary": {
                "office_reference": self._generate_anonymous_reference(
                    str(office_data.get("office_id", "unknown"))
                ),
                "office_name": office_data.get("name", "Medical Office"),
                "billing_period_start": billing_period.get("start"),
                "billing_period_end": billing_period.get("end"),
                "active_patient_count": patient_count,
                "line_item_summary": f"Patient Activations: {patient_count} @ $5.00 each",
                "subtotal": patient_count * 5.00,  # Example rate
                "total_amount": patient_count * 5.00,
                "currency": "USD",
                "billing_type": "monthly_usage",
                "data_classification": "aggregated_anonymized",
            }
        }

        audit_logger.info(
            f"Created aggregate billing summary - Office: {office_data.get('office_id')}, "
            f"Patient count: {patient_count}, Amount: ${patient_count * 5.00}"
        )

        return summary

    def _is_patient_specific_item(self, item: Dict[str, Any]) -> bool:
        """Check if a line item contains patient-specific information."""
        patient_indicators = ["patient_id", "user_id", "patient_name", "user_name"]
        return any(field in item for field in patient_indicators)

    def _aggregate_patient_line_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Convert patient-specific line item to aggregate representation."""
        return {
            "description": "Patient Activation",
            "quantity": 1,
            "unit_price": item.get("unit_price", 5.00),
            "total_price": item.get("total_price", 5.00),
            "item_type": "patient_activation",
            "data_type": "aggregated",
        }

    def _anonymize_aggregate_data(self, value: Any) -> Any:
        """Anonymize aggregate data while preserving business logic."""
        if isinstance(value, dict):
            # Remove any identifiers from aggregate data
            anonymized = {}
            for k, v in value.items():
                if not any(
                    identifier in k.lower()
                    for identifier in ["id", "name", "email", "phone"]
                ):
                    anonymized[k] = v
            return anonymized
        return value

    def _generate_anonymous_reference(self, source_id: str) -> str:
        """Generate an anonymous reference that cannot be traced back to source."""
        # Use HMAC-like approach with application secret
        secret = os.getenv(
            "ANONYMOUS_REF_SECRET", "default_secret_change_in_production"
        )
        hash_source = f"{secret}_{source_id}_{datetime.now().strftime('%Y%m')}"
        return f"anon_{hashlib.sha256(hash_source.encode()).hexdigest()[:12]}"

    def _generate_audit_reference(self, operation_type: str) -> str:
        """Generate unique audit reference for tracking sanitization operations."""
        self._audit_counter += 1
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"sanitize_{operation_type}_{timestamp}_{self._audit_counter:04d}"


class ExternalDataValidator:
    """
    Validates that data structures are safe for external transmission.

    This validator performs final checks before data is sent to payment processors
    to ensure no ePHI has leaked through the sanitization process.
    """

    def __init__(self):
        self.detector = ePHIDetector()

    def validate_for_stripe(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate that data is safe for Stripe transmission.

        Args:
            data: Data structure to validate

        Returns:
            Dict[str, Any]: Validation result with pass/fail and details

        Raises:
            ValueError: If ePHI is detected in the data
        """
        validation_result = {
            "passed": True,
            "errors": [],
            "warnings": [],
            "audit_reference": self._generate_validation_reference(),
        }

        # Recursively check all fields in the data structure
        ephi_fields = self._scan_for_ephi(data, [])

        if ephi_fields:
            validation_result["passed"] = False
            validation_result["errors"] = [
                f"ePHI detected in field: {field}" for field in ephi_fields
            ]

            # Log critical security violation
            logger.error(
                f"SECURITY VIOLATION: ePHI detected in data for external transmission. "
                f"Fields: {ephi_fields}. Audit ref: {validation_result['audit_reference']}"
            )

            raise ValueError(
                f"Data validation failed: ePHI detected in fields {ephi_fields}. "
                "Data cannot be transmitted to external payment processor."
            )

        # Log successful validation
        audit_logger.info(
            f"External data validation passed - "
            f"Audit ref: {validation_result['audit_reference']}"
        )

        return validation_result

    def _scan_for_ephi(self, data: Any, path: List[str]) -> List[str]:
        """
        Recursively scan data structure for ePHI.

        Args:
            data: Data to scan
            path: Current path in the data structure

        Returns:
            List[str]: List of field paths containing ePHI
        """
        ephi_fields = []

        if isinstance(data, dict):
            for key, value in data.items():
                current_path = path + [key]

                # Check if this field contains ePHI
                classification = self.detector.classify_field(key, value)
                if classification == DataClassification.EPHI:
                    ephi_fields.append(".".join(current_path))

                # Recursively check nested structures
                ephi_fields.extend(self._scan_for_ephi(value, current_path))

        elif isinstance(data, list):
            for i, item in enumerate(data):
                current_path = path + [f"[{i}]"]
                ephi_fields.extend(self._scan_for_ephi(item, current_path))

        return ephi_fields

    def _generate_validation_reference(self) -> str:
        """Generate unique reference for validation operations."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"validate_{timestamp}_{secrets.token_hex(4)}"


# Global instances for use throughout the application
billing_sanitizer = BillingDataSanitizer()
external_validator = ExternalDataValidator()


def sanitize_for_stripe(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to sanitize and validate data for Stripe transmission.

    Args:
        data: Raw billing data

    Returns:
        Dict[str, Any]: Sanitized and validated data safe for Stripe

    Raises:
        ValueError: If data cannot be safely sanitized
    """
    # Determine data type and sanitize accordingly
    if "invoice_id" in data or "billing_period" in data:
        result = billing_sanitizer.sanitize_invoice_data(data)
    elif "line_items" in data or isinstance(data.get("items"), list):
        result = billing_sanitizer.sanitize_line_items(data.get("line_items", []))
    else:
        # Generic sanitization
        result = billing_sanitizer.sanitize_invoice_data(data)

    # Validate the sanitized data
    external_validator.validate_for_stripe(result.sanitized_data)

    return result.sanitized_data
