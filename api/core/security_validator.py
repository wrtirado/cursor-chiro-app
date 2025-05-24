"""
Security configuration validator for payment processing and data transmission.

This module provides utilities to validate and report on security configurations
to ensure compliance with HIPAA requirements and secure handling of payment data.
"""

import os
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from api.core.security_payment import tls_validator, PaymentReferenceSecurity

logger = logging.getLogger(__name__)


@dataclass
class SecurityCheckResult:
    """Result of a security configuration check."""

    check_name: str
    passed: bool
    message: str
    severity: str  # 'critical', 'warning', 'info'
    recommendation: Optional[str] = None


class PaymentSecurityValidator:
    """
    Validates security configurations for payment processing.
    """

    def __init__(self):
        self.results: List[SecurityCheckResult] = []

    def validate_all(self) -> List[SecurityCheckResult]:
        """
        Run all security validation checks.

        Returns:
            List[SecurityCheckResult]: Results of all validation checks
        """
        self.results.clear()

        # Validate encryption configuration
        self._check_payment_encryption_key()

        # Validate TLS configuration
        self._check_tls_configuration()

        # Validate environment settings
        self._check_environment_security()

        # Validate database security
        self._check_database_security()

        # Validate MinIO/S3 security
        self._check_storage_security()

        return self.results

    def _check_payment_encryption_key(self):
        """Check if payment encryption key is properly configured."""
        environment = os.getenv("ENVIRONMENT", "development")
        payment_key = os.getenv("PAYMENT_ENCRYPTION_KEY")

        if environment == "production" and not payment_key:
            self.results.append(
                SecurityCheckResult(
                    check_name="Payment Encryption Key",
                    passed=False,
                    message="PAYMENT_ENCRYPTION_KEY not set in production environment",
                    severity="critical",
                    recommendation="Set PAYMENT_ENCRYPTION_KEY environment variable with a secure Fernet key",
                )
            )
        elif environment == "development" and not payment_key:
            self.results.append(
                SecurityCheckResult(
                    check_name="Payment Encryption Key",
                    passed=True,
                    message="Payment encryption key will be auto-generated for development",
                    severity="info",
                    recommendation="Set PAYMENT_ENCRYPTION_KEY for consistent encryption in development",
                )
            )
        else:
            # Try to validate the key format
            try:
                PaymentReferenceSecurity()
                self.results.append(
                    SecurityCheckResult(
                        check_name="Payment Encryption Key",
                        passed=True,
                        message="Payment encryption key is properly configured",
                        severity="info",
                    )
                )
            except Exception as e:
                self.results.append(
                    SecurityCheckResult(
                        check_name="Payment Encryption Key",
                        passed=False,
                        message=f"Invalid payment encryption key: {str(e)}",
                        severity="critical",
                        recommendation="Generate a new Fernet key using cryptography.fernet.Fernet.generate_key()",
                    )
                )

    def _check_tls_configuration(self):
        """Check TLS/SSL configuration."""
        tls_config = tls_validator.validate_tls_config()
        environment = os.getenv("ENVIRONMENT", "development")

        if environment == "production":
            if (
                not tls_config["tls_cert_configured"]
                and not tls_config["tls_key_configured"]
            ):
                self.results.append(
                    SecurityCheckResult(
                        check_name="TLS Configuration",
                        passed=False,
                        message="TLS certificates not configured for production",
                        severity="warning",
                        recommendation="Configure TLS_CERT_PATH and TLS_KEY_PATH or use reverse proxy with TLS termination",
                    )
                )
            else:
                self.results.append(
                    SecurityCheckResult(
                        check_name="TLS Configuration",
                        passed=True,
                        message="TLS configuration is set for production",
                        severity="info",
                    )
                )
        else:
            self.results.append(
                SecurityCheckResult(
                    check_name="TLS Configuration",
                    passed=True,
                    message="TLS configuration not required for development environment",
                    severity="info",
                    recommendation="Ensure TLS is configured in staging/production environments",
                )
            )

    def _check_environment_security(self):
        """Check general environment security settings."""
        environment = os.getenv("ENVIRONMENT", "development")
        secret_key = os.getenv("SECRET_KEY", "")

        # Check if using default secret key
        if "a_very_secret_key_that_should_be_changed" in secret_key:
            self.results.append(
                SecurityCheckResult(
                    check_name="Secret Key Security",
                    passed=False,
                    message="Using default SECRET_KEY value",
                    severity="critical" if environment == "production" else "warning",
                    recommendation="Generate a secure random secret key for JWT signing",
                )
            )
        elif len(secret_key) < 32:
            self.results.append(
                SecurityCheckResult(
                    check_name="Secret Key Security",
                    passed=False,
                    message="SECRET_KEY is too short (minimum 32 characters recommended)",
                    severity="warning",
                    recommendation="Use a longer, more secure secret key",
                )
            )
        else:
            self.results.append(
                SecurityCheckResult(
                    check_name="Secret Key Security",
                    passed=True,
                    message="SECRET_KEY appears to be properly configured",
                    severity="info",
                )
            )

    def _check_database_security(self):
        """Check database security configuration."""
        db_url = os.getenv("DATABASE_URL", "")

        if "sqlite+libsql://" in db_url:
            # Check for secure libSQL configuration
            if (
                db_url.startswith("sqlite+libsql://")
                and "localhost" not in db_url
                and "127.0.0.1" not in db_url
            ):
                if not db_url.startswith("sqlite+libsql://https://"):
                    self.results.append(
                        SecurityCheckResult(
                            check_name="Database Connection Security",
                            passed=False,
                            message="Remote libSQL connection not using HTTPS",
                            severity="critical",
                            recommendation="Use HTTPS for remote libSQL connections",
                        )
                    )
                else:
                    self.results.append(
                        SecurityCheckResult(
                            check_name="Database Connection Security",
                            passed=True,
                            message="Database connection appears secure",
                            severity="info",
                        )
                    )
            else:
                self.results.append(
                    SecurityCheckResult(
                        check_name="Database Connection Security",
                        passed=True,
                        message="Local database connection configured",
                        severity="info",
                        recommendation="Ensure production database uses encrypted connections",
                    )
                )
        else:
            self.results.append(
                SecurityCheckResult(
                    check_name="Database Connection Security",
                    passed=True,
                    message="Database connection configuration appears standard",
                    severity="info",
                )
            )

    def _check_storage_security(self):
        """Check MinIO/S3 storage security configuration."""
        minio_ssl = os.getenv("MINIO_USE_SSL", "false").lower() == "true"
        environment = os.getenv("ENVIRONMENT", "development")

        if environment == "production" and not minio_ssl:
            self.results.append(
                SecurityCheckResult(
                    check_name="Storage Security",
                    passed=False,
                    message="MinIO SSL not enabled in production",
                    severity="warning",
                    recommendation="Set MINIO_USE_SSL=true for production environments",
                )
            )
        elif minio_ssl:
            self.results.append(
                SecurityCheckResult(
                    check_name="Storage Security",
                    passed=True,
                    message="MinIO SSL is enabled",
                    severity="info",
                )
            )
        else:
            self.results.append(
                SecurityCheckResult(
                    check_name="Storage Security",
                    passed=True,
                    message="MinIO SSL configuration acceptable for development",
                    severity="info",
                    recommendation="Enable SSL for production environments",
                )
            )

    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of validation results.

        Returns:
            Dict[str, Any]: Summary of validation results
        """
        if not self.results:
            self.validate_all()

        critical_issues = [
            r for r in self.results if r.severity == "critical" and not r.passed
        ]
        warning_issues = [
            r for r in self.results if r.severity == "warning" and not r.passed
        ]
        passed_checks = [r for r in self.results if r.passed]

        return {
            "total_checks": len(self.results),
            "passed": len(passed_checks),
            "critical_issues": len(critical_issues),
            "warnings": len(warning_issues),
            "overall_status": (
                "SECURE" if len(critical_issues) == 0 else "NEEDS_ATTENTION"
            ),
            "critical_issues_list": [r.check_name for r in critical_issues],
            "warning_issues_list": [r.check_name for r in warning_issues],
        }

    def log_results(self):
        """Log all validation results."""
        if not self.results:
            self.validate_all()

        summary = self.get_summary()
        logger.info(f"Security validation summary: {summary}")

        for result in self.results:
            if result.severity == "critical" and not result.passed:
                logger.error(f"CRITICAL: {result.check_name} - {result.message}")
            elif result.severity == "warning" and not result.passed:
                logger.warning(f"WARNING: {result.check_name} - {result.message}")
            else:
                logger.info(f"INFO: {result.check_name} - {result.message}")


# Global validator instance
payment_security_validator = PaymentSecurityValidator()
