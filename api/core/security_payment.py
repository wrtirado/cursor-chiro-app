"""
Security utilities for payment provider references and billing data.

This module implements secure handling of payment provider references like
customer IDs and subscription IDs, ensuring they are protected both at rest
and in transit while maintaining compliance with HIPAA requirements.
"""

import os
import logging
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet
from pydantic import validator
import re

logger = logging.getLogger(__name__)


class PaymentReferenceSecurityError(Exception):
    """Custom exception for payment reference security issues."""

    pass


class PaymentReferenceSecurity:
    """
    Handles secure encryption/decryption and validation of payment provider references.

    This class provides methods to securely handle customer IDs, subscription IDs,
    and other payment provider references that need protection.
    """

    def __init__(self):
        self._encryption_key = self._get_or_generate_key()
        self._cipher = Fernet(self._encryption_key)

    @staticmethod
    def _get_or_generate_key() -> bytes:
        """
        Get encryption key from environment or generate a new one.

        Returns:
            bytes: The encryption key for Fernet

        Raises:
            PaymentReferenceSecurityError: If key cannot be obtained
        """
        key_str = os.getenv("PAYMENT_ENCRYPTION_KEY")

        if key_str:
            try:
                return key_str.encode()
            except Exception as e:
                logger.error(f"Invalid payment encryption key format: {e}")
                raise PaymentReferenceSecurityError("Invalid encryption key format")

        # Generate new key if none exists (for development)
        if os.getenv("ENVIRONMENT", "development") == "development":
            key = Fernet.generate_key()
            logger.warning(
                "Generated new payment encryption key for development. "
                "Set PAYMENT_ENCRYPTION_KEY environment variable for production."
            )
            return key
        else:
            raise PaymentReferenceSecurityError(
                "PAYMENT_ENCRYPTION_KEY environment variable must be set in production"
            )

    def encrypt_reference(self, reference: str) -> str:
        """
        Encrypt a payment provider reference.

        Args:
            reference: The payment provider reference to encrypt

        Returns:
            str: Base64 encoded encrypted reference

        Raises:
            PaymentReferenceSecurityError: If encryption fails
        """
        if not reference:
            return ""

        try:
            encrypted_bytes = self._cipher.encrypt(reference.encode())
            return encrypted_bytes.decode()
        except Exception as e:
            logger.error(f"Failed to encrypt payment reference: {e}")
            raise PaymentReferenceSecurityError("Encryption failed")

    def decrypt_reference(self, encrypted_reference: str) -> str:
        """
        Decrypt a payment provider reference.

        Args:
            encrypted_reference: The encrypted reference to decrypt

        Returns:
            str: The decrypted reference

        Raises:
            PaymentReferenceSecurityError: If decryption fails
        """
        if not encrypted_reference:
            return ""

        try:
            decrypted_bytes = self._cipher.decrypt(encrypted_reference.encode())
            return decrypted_bytes.decode()
        except Exception as e:
            logger.error(f"Failed to decrypt payment reference: {e}")
            raise PaymentReferenceSecurityError("Decryption failed")

    @staticmethod
    def validate_stripe_customer_id(customer_id: str) -> bool:
        """
        Validate Stripe customer ID format.

        Args:
            customer_id: The customer ID to validate

        Returns:
            bool: True if valid format, False otherwise
        """
        if not customer_id:
            return True  # Allow empty values

        # Stripe customer IDs start with 'cus_' followed by alphanumeric characters
        pattern = r"^cus_[a-zA-Z0-9]{24}$"
        return bool(re.match(pattern, customer_id))

    @staticmethod
    def validate_stripe_subscription_id(subscription_id: str) -> bool:
        """
        Validate Stripe subscription ID format.

        Args:
            subscription_id: The subscription ID to validate

        Returns:
            bool: True if valid format, False otherwise
        """
        if not subscription_id:
            return True  # Allow empty values

        # Stripe subscription IDs start with 'sub_' followed by alphanumeric characters
        pattern = r"^sub_[a-zA-Z0-9]{24}$"
        return bool(re.match(pattern, subscription_id))

    @staticmethod
    def sanitize_for_logging(reference: str) -> str:
        """
        Sanitize payment reference for safe logging.

        Args:
            reference: The reference to sanitize

        Returns:
            str: Sanitized reference showing only prefix and suffix
        """
        if not reference or len(reference) < 8:
            return "***"

        # Show first 4 and last 4 characters, mask the rest
        return f"{reference[:4]}{'*' * (len(reference) - 8)}{reference[-4:]}"


class TLSValidator:
    """
    Validates TLS/SSL configuration for secure data transmission.
    """

    @staticmethod
    def validate_tls_config() -> Dict[str, bool]:
        """
        Validate TLS configuration settings.

        Returns:
            Dict[str, bool]: Validation results for different TLS aspects
        """
        results = {
            "tls_cert_configured": bool(os.getenv("TLS_CERT_PATH")),
            "tls_key_configured": bool(os.getenv("TLS_KEY_PATH")),
            "minio_ssl_enabled": os.getenv("MINIO_USE_SSL", "false").lower() == "true",
            "environment_ready": os.getenv("ENVIRONMENT") in ["staging", "production"],
        }

        return results

    @staticmethod
    def get_tls_recommendations() -> Dict[str, str]:
        """
        Get TLS configuration recommendations.

        Returns:
            Dict[str, str]: Recommendations for TLS setup
        """
        return {
            "production": "Configure reverse proxy (nginx/CloudFlare) with TLS 1.2+ termination",
            "api_server": "Set TLS_CERT_PATH and TLS_KEY_PATH for direct TLS if needed",
            "internal_services": "Enable MINIO_USE_SSL=true for production MinIO connections",
            "headers": "Ensure HSTS header is enabled in production middleware",
        }


# Global instances for use throughout the application
payment_security = PaymentReferenceSecurity()
tls_validator = TLSValidator()


def secure_payment_reference_field(value: str, field_type: str) -> str:
    """
    Utility function to securely handle payment reference fields.

    Args:
        value: The payment reference value
        field_type: The type of field ('customer_id' or 'subscription_id')

    Returns:
        str: Validated and encrypted reference

    Raises:
        ValueError: If validation fails
    """
    if not value:
        return ""

    # Validate format based on field type
    if (
        field_type == "customer_id"
        and not PaymentReferenceSecurity.validate_stripe_customer_id(value)
    ):
        raise ValueError("Invalid Stripe customer ID format")
    elif (
        field_type == "subscription_id"
        and not PaymentReferenceSecurity.validate_stripe_subscription_id(value)
    ):
        raise ValueError("Invalid Stripe subscription ID format")

    # Encrypt the reference
    return payment_security.encrypt_reference(value)


def get_decrypted_payment_reference(encrypted_value: str) -> str:
    """
    Utility function to decrypt payment reference fields.

    Args:
        encrypted_value: The encrypted payment reference

    Returns:
        str: Decrypted reference
    """
    if not encrypted_value:
        return ""

    return payment_security.decrypt_reference(encrypted_value)
