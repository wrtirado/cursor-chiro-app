import base64
from sqlalchemy import TypeDecorator, Text  # Store encrypted data as TEXT
from cryptography.fernet import Fernet, InvalidToken
from cryptography.exceptions import InvalidSignature

from api.core.config import settings
from api.core.logging_config import app_log  # For logging encryption errors

# Initialize Fernet cipher suite
# Ensure the key is bytes
key = settings.ENCRYPTION_KEY.encode()
try:
    # Validate the key format early
    if not key or len(base64.urlsafe_b64decode(key)) != 32:
        raise ValueError(
            "Invalid ENCRYPTION_KEY length or format. Must be 32 url-safe base64-encoded bytes."
        )
    fernet = Fernet(key)
except (ValueError, TypeError) as e:
    app_log.error(
        f"FATAL: Invalid ENCRYPTION_KEY configured. Application cannot start securely. Error: {e}"
    )
    # In a real app, you might want to exit here or prevent startup
    # For now, we log error and let it potentially fail later if fernet is used.
    fernet = None  # Indicate failure


class EncryptedType(TypeDecorator):
    """SQLAlchemy TypeDecorator for symmetric encryption using Fernet."""

    impl = Text  # Store encrypted data as TEXT in the database.
    # Use LargeBinary if you prefer storing bytes directly.
    cache_ok = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if fernet is None:
            raise RuntimeError(
                "Encryption key is not configured correctly. Cannot use EncryptedType."
            )
        self._fernet = fernet

    def process_bind_param(self, value, dialect):
        """Encrypt data when writing to the database."""
        if value is None:
            return None
        # Ensure the value is string before encrypting
        str_value = str(value)
        try:
            encrypted_value = self._fernet.encrypt(str_value.encode())
            # Return as string for TEXT column
            return encrypted_value.decode()
        except Exception as e:
            app_log.error(f"Encryption failed: {e}", exc_info=True)
            # Handle encryption failure appropriately - raise error?
            raise ValueError("Encryption failed during database write.") from e

    def process_result_value(self, value, dialect):
        """Decrypt data when reading from the database."""
        if value is None:
            return None
        try:
            # Ensure the value from DB is bytes before decrypting
            encrypted_value = value.encode()
            decrypted_value = self._fernet.decrypt(encrypted_value)
            return decrypted_value.decode()  # Return as string
        except InvalidToken:
            app_log.error(
                f"Decryption failed: Invalid token/data format for value starting with: {value[:10]}...",
                exc_info=False,
            )  # Avoid logging potentially sensitive data
            # Handle decryption failure: return None, raise error, return placeholder?
            # Returning None might hide issues, raising error might break application flow.
            # Choose based on application needs.
            # For now, let's return None to avoid breaking reads, but log error.
            return None
        except InvalidSignature:
            app_log.error(
                f"Decryption failed: Invalid signature for value starting with: {value[:10]}...",
                exc_info=False,
            )
            return None
        except Exception as e:
            app_log.error(f"Decryption failed: {e}", exc_info=True)
            raise ValueError("Decryption failed during database read.") from e
