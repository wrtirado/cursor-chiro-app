"""
Tests for data minimization utilities.

This test suite ensures that the data minimization system properly prevents
ePHI from being transmitted to external payment processors like Stripe.
"""

import pytest
from unittest.mock import patch, MagicMock
from api.core.data_minimization import (
    ePHIDetector,
    BillingDataSanitizer,
    ExternalDataValidator,
    DataClassification,
    sanitize_for_stripe,
)


class TestePHIDetector:
    """Test ePHI detection capabilities."""

    def test_classify_definite_ephi_fields(self):
        """Test that definite ePHI fields are properly classified."""
        detector = ePHIDetector()

        ephi_fields = [
            ("patient_id", "12345"),
            ("patient_name", "John Doe"),
            ("patient_email", "john@example.com"),
            ("user_id", "67890"),
            ("first_name", "Jane"),
            ("ssn", "123-45-6789"),
        ]

        for field_name, field_value in ephi_fields:
            classification = detector.classify_field(field_name, field_value)
            assert (
                classification == DataClassification.EPHI
            ), f"Field {field_name} should be classified as ePHI"

    def test_classify_safe_external_fields(self):
        """Test that safe external fields are properly classified."""
        detector = ePHIDetector()

        safe_fields = [
            ("office_id", 123),
            ("invoice_id", "inv_12345"),
            ("amount", 150.00),
            ("quantity", 3),
            ("billing_period_start", "2024-01-01"),
            ("payment_provider_customer_id", "cus_123456789012345678901234"),
        ]

        for field_name, field_value in safe_fields:
            classification = detector.classify_field(field_name, field_value)
            assert (
                classification == DataClassification.SAFE_FOR_EXTERNAL
            ), f"Field {field_name} should be safe for external transmission"

    def test_classify_potentially_dangerous_fields(self):
        """Test that potentially dangerous fields are properly handled."""
        detector = ePHIDetector()

        # These should be classified as internal only or ePHI depending on content
        potentially_dangerous = [
            (
                "description",
                "Patient John Doe activation",
            ),  # Contains name - should be ePHI
            ("notes", "Regular billing item"),  # Generic - should be internal only
            ("reference", "REF123"),  # Generic - should be internal only
        ]

        name_field_classification = detector.classify_field(
            "description", "Patient John Doe activation"
        )
        assert name_field_classification == DataClassification.EPHI

        generic_field_classification = detector.classify_field(
            "notes", "Regular billing item"
        )
        assert generic_field_classification == DataClassification.INTERNAL_ONLY

    def test_contains_personal_info_detection(self):
        """Test personal information detection in string values."""
        detector = ePHIDetector()

        # Email patterns
        assert detector._contains_personal_info("john@example.com") == True
        assert detector._contains_personal_info("contact@medical-office.com") == True

        # Phone number patterns
        assert detector._contains_personal_info("555-123-4567") == True
        assert detector._contains_personal_info("(555) 123-4567") == True
        assert detector._contains_personal_info("5551234567") == True

        # Personal identifiers
        assert detector._contains_personal_info("Patient John Smith") == True
        assert detector._contains_personal_info("User profile data") == True

        # Safe content
        assert detector._contains_personal_info("Billing item") == False
        assert detector._contains_personal_info("Monthly charge") == False
        assert detector._contains_personal_info("INV123") == False


class TestBillingDataSanitizer:
    """Test billing data sanitization."""

    def test_sanitize_invoice_data_removes_ephi(self):
        """Test that invoice sanitization removes ePHI fields."""
        sanitizer = BillingDataSanitizer()

        invoice_data = {
            "invoice_id": "inv_123",
            "office_id": 456,
            "amount": 150.00,
            "patient_id": 789,  # ePHI - should be removed
            "patient_name": "John Doe",  # ePHI - should be removed
            "billing_period_start": "2024-01-01",
            "notes": "Patient care billing",  # Potentially sensitive - should be removed
        }

        result = sanitizer.sanitize_invoice_data(invoice_data)

        # Check that safe fields are retained
        assert "invoice_id" in result.sanitized_data
        assert "office_id" in result.sanitized_data
        assert "amount" in result.sanitized_data
        assert "billing_period_start" in result.sanitized_data

        # Check that ePHI fields are removed
        assert "patient_id" not in result.sanitized_data
        assert "patient_name" not in result.sanitized_data

        # Check that potentially sensitive fields are removed
        assert "notes" not in result.sanitized_data

        # Check that anonymous reference is added
        assert "anonymous_invoice_ref" in result.sanitized_data

        # Check audit information
        assert result.audit_reference is not None
        assert "patient_id" in result.removed_fields
        assert "patient_name" in result.removed_fields
        assert len(result.warnings) >= 2  # Should have warnings for ePHI removal

    def test_sanitize_line_items_aggregates_patient_data(self):
        """Test that line item sanitization properly aggregates patient-specific data."""
        sanitizer = BillingDataSanitizer()

        line_items = [
            {
                "line_item_id": 1,
                "patient_id": 123,  # ePHI - triggers aggregation
                "patient_name": "John Doe",  # ePHI
                "description": "Patient activation",
                "unit_price": 5.00,
                "total_price": 5.00,
            },
            {
                "line_item_id": 2,
                "description": "Setup fee",  # Office-level item
                "unit_price": 50.00,
                "total_price": 50.00,
            },
        ]

        result = sanitizer.sanitize_line_items(line_items)

        sanitized_items = result.sanitized_data["line_items"]

        # Should have 2 items
        assert len(sanitized_items) == 2

        # First item should be aggregated (no patient-specific data)
        first_item = sanitized_items[0]
        assert "patient_id" not in first_item
        assert "patient_name" not in first_item
        assert first_item["description"] == "Patient Activation"
        assert first_item["data_type"] == "aggregated"
        assert "anonymous_line_ref" in first_item

        # Second item should be sanitized but not aggregated
        second_item = sanitized_items[1]
        assert "description" in second_item
        assert "anonymous_line_ref" in second_item

        # Check warnings for aggregation
        assert any("aggregate" in warning.lower() for warning in result.warnings)

    def test_create_aggregate_billing_summary(self):
        """Test creation of aggregate billing summary."""
        sanitizer = BillingDataSanitizer()

        office_data = {"office_id": 123, "name": "Test Medical Office"}

        billing_period = {"start": "2024-01-01", "end": "2024-01-31"}

        patient_count = 15

        summary = sanitizer.create_aggregate_billing_summary(
            office_data, patient_count, billing_period
        )

        billing_summary = summary["billing_summary"]

        # Check required fields
        assert "office_reference" in billing_summary
        assert "office_name" in billing_summary
        assert billing_summary["active_patient_count"] == 15
        assert billing_summary["total_amount"] == 75.00  # 15 * $5.00
        assert billing_summary["data_classification"] == "aggregated_anonymized"

        # Ensure no patient identifiers
        assert "patient_id" not in str(summary)
        assert "patient_name" not in str(summary)

    def test_anonymous_reference_generation(self):
        """Test that anonymous references cannot be traced back."""
        sanitizer = BillingDataSanitizer()

        # Generate references for the same source ID multiple times
        ref1 = sanitizer._generate_anonymous_reference("patient_123")
        ref2 = sanitizer._generate_anonymous_reference("patient_123")

        # References should be consistent within the same month
        assert ref1 == ref2

        # Reference should not contain the original ID
        assert "patient_123" not in ref1
        assert "123" not in ref1

        # Reference should start with "anon_"
        assert ref1.startswith("anon_")


class TestExternalDataValidator:
    """Test external data validation."""

    def test_validate_clean_data_passes(self):
        """Test that clean data passes validation."""
        validator = ExternalDataValidator()

        clean_data = {
            "invoice_id": "inv_123",
            "office_id": 456,
            "amount": 150.00,
            "billing_period_start": "2024-01-01",
            "line_items": [
                {
                    "description": "Patient Activation",
                    "quantity": 3,
                    "unit_price": 5.00,
                    "total_price": 15.00,
                }
            ],
        }

        result = validator.validate_for_stripe(clean_data)
        assert result["passed"] == True
        assert len(result["errors"]) == 0

    def test_validate_ephi_data_fails(self):
        """Test that data containing ePHI fails validation."""
        validator = ExternalDataValidator()

        ephi_data = {
            "invoice_id": "inv_123",
            "office_id": 456,
            "amount": 150.00,
            "patient_id": 789,  # ePHI - should cause failure
            "patient_name": "John Doe",  # ePHI - should cause failure
        }

        with pytest.raises(ValueError) as exc_info:
            validator.validate_for_stripe(ephi_data)

        assert "ePHI detected" in str(exc_info.value)
        assert "patient_id" in str(exc_info.value)
        assert "patient_name" in str(exc_info.value)

    def test_validate_nested_ephi_detection(self):
        """Test that ePHI in nested structures is detected."""
        validator = ExternalDataValidator()

        nested_ephi_data = {
            "invoice_id": "inv_123",
            "office_id": 456,
            "line_items": [
                {"description": "Service charge", "amount": 50.00},
                {
                    "description": "Patient activation",
                    "amount": 5.00,
                    "patient_id": 789,  # Nested ePHI - should be detected
                },
            ],
        }

        with pytest.raises(ValueError) as exc_info:
            validator.validate_for_stripe(nested_ephi_data)

        assert "ePHI detected" in str(exc_info.value)
        assert "line_items[1].patient_id" in str(exc_info.value)


class TestIntegrationSanitization:
    """Integration tests for the complete sanitization pipeline."""

    def test_sanitize_for_stripe_invoice_data(self):
        """Test the main sanitize_for_stripe function with invoice data."""
        invoice_data = {
            "invoice_id": "inv_123",
            "office_id": 456,
            "amount": 150.00,
            "patient_id": 789,  # ePHI - should be removed
            "billing_period_start": "2024-01-01",
        }

        sanitized = sanitize_for_stripe(invoice_data)

        # Should contain safe fields
        assert "invoice_id" in sanitized
        assert "office_id" in sanitized
        assert "amount" in sanitized

        # Should not contain ePHI
        assert "patient_id" not in sanitized

        # Should have anonymous reference
        assert "anonymous_invoice_ref" in sanitized

    def test_sanitize_for_stripe_line_items(self):
        """Test the main sanitize_for_stripe function with line items."""
        line_items_data = {
            "line_items": [
                {
                    "patient_id": 123,
                    "description": "Patient activation",
                    "unit_price": 5.00,
                }
            ]
        }

        sanitized = sanitize_for_stripe(line_items_data)

        # Should have line_items
        assert "line_items" in sanitized

        # Line items should be aggregated
        item = sanitized["line_items"][0]
        assert "patient_id" not in item
        assert item["description"] == "Patient Activation"
        assert "anonymous_line_ref" in item

    def test_end_to_end_ephi_isolation(self):
        """Test complete end-to-end ePHI isolation."""
        # Simulate a complex billing data structure with mixed content
        complex_billing_data = {
            "invoice_id": "inv_123",
            "office_id": 456,
            "office_name": "Test Medical Office",
            "amount": 175.00,
            "billing_period_start": "2024-01-01",
            "billing_period_end": "2024-01-31",
            "line_items": [
                {
                    "line_item_id": 1,
                    "patient_id": 789,
                    "patient_name": "John Doe",
                    "description": "Patient activation",
                    "unit_price": 5.00,
                    "total_price": 5.00,
                },
                {
                    "line_item_id": 2,
                    "patient_id": 790,
                    "patient_name": "Jane Smith",
                    "description": "Patient activation",
                    "unit_price": 5.00,
                    "total_price": 5.00,
                },
                {
                    "line_item_id": 3,
                    "description": "Setup fee",
                    "unit_price": 50.00,
                    "total_price": 50.00,
                },
            ],
            "customer_notes": "Patient John Doe requested special billing",  # Contains ePHI
            "internal_ref": "INT_789_PATIENT",  # Internal reference
        }

        # Sanitize for Stripe transmission
        sanitized = sanitize_for_stripe(complex_billing_data)

        # Verify safe office-level data is retained
        assert sanitized["invoice_id"] == "inv_123"
        assert sanitized["office_id"] == 456
        assert sanitized["office_name"] == "Test Medical Office"
        assert sanitized["amount"] == 175.00

        # Verify ePHI is completely removed
        sanitized_str = str(sanitized)
        assert "John Doe" not in sanitized_str
        assert "Jane Smith" not in sanitized_str
        assert "patient_id" not in sanitized_str
        assert "patient_name" not in sanitized_str

        # Verify line items are properly aggregated
        if "line_items" in sanitized:
            for item in sanitized["line_items"]:
                assert "patient_id" not in item
                assert "patient_name" not in item
                assert "anonymous_line_ref" in item

        # Verify anonymous references are present
        assert "anonymous_invoice_ref" in sanitized

    @patch("api.core.data_minimization.audit_logger")
    def test_audit_logging_during_sanitization(self, mock_audit_logger):
        """Test that proper audit logging occurs during sanitization."""
        invoice_data = {"invoice_id": "inv_123", "patient_id": 789, "amount": 50.00}

        sanitize_for_stripe(invoice_data)

        # Verify audit logging was called
        assert mock_audit_logger.info.called

        # Check that audit logs contain relevant information
        call_args = [call[0][0] for call in mock_audit_logger.info.call_args_list]
        audit_messages = " ".join(call_args)

        assert "sanitized" in audit_messages.lower()
        assert "audit ref" in audit_messages.lower()


if __name__ == "__main__":
    pytest.main([__file__])
