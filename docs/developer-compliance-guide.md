# Developer Compliance Guide (HIPAA)

This document outlines key security and compliance features implemented in the API codebase to help meet HIPAA requirements. Developers should adhere to these guidelines when adding or modifying features, especially those handling potential ePHI (Electronic Protected Health Information).

**Reference:** Always refer to the main `docs/healthcare-compliance.md` for detailed HIPAA requirements.

## 1. Security Configuration (`api/core/config.py`)

- **Environment:** The `ENVIRONMENT` setting (e.g., "development", "production") may influence certain security behaviors.
- **Token Expiration:** JWT `ACCESS_TOKEN_EXPIRE_MINUTES` defaults to 30 minutes but is configurable via environment variable. Ensure this remains reasonably short for production environments.
- **Encryption Key:** `ENCRYPTION_KEY` is crucial for data-at-rest encryption. It **MUST** be set in the environment (`.env` locally) and must be a valid Fernet key. **For Production:** Use a secure key management system (KMS, Vault) and never commit keys.
- **Secure Headers:** Middleware (`api/core/middleware.py`) adds security headers (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`).
  - **Content-Security-Policy (CSP):** Currently configured to allow `/docs` resources. **Needs careful tuning** based on the actual frontend application's requirements (scripts, styles, connections).
  - **Strict-Transport-Security (HSTS):** Currently commented out. Should be enabled in production once HTTPS is enforced.
- **TLS/SSL:** Configuration settings (`TLS_CERT_PATH`, `TLS_KEY_PATH`) exist but enforcement is deferred to deployment environments (staging/production). Local development uses HTTP.

## 2. Audit Logging (`api/core/logging_config.py`, `api/core/audit_logger.py`)

- **Purpose:** To track significant events, especially those involving access or modification of potential ePHI.
- **Implementation:**
  - A dedicated `audit` logger is configured in `logging_config.py`.
  - Logs are written in **JSON format** to the file specified by `settings.AUDIT_LOG_FILE` (`logs/audit.log` by default).
  - Logs are automatically rotated.
  - The helper function `log_audit_event()` in `audit_logger.py` should be used to ensure consistent, structured logs.
- **Developer Responsibility:**
  - **Integrate `log_audit_event()`:** Calls _must_ be added to relevant endpoints/service functions performing auditable actions (CRUD on users, plans, progress, media access, auth events, etc.).
  - **Use `AuditEvent` enum:** Use the predefined event types from `AuditEvent` class where possible for consistency.
  - **Include Context:** Pass relevant `user`, `request`, `resource_type`, `resource_id`, `outcome`, and `details` to `log_audit_event()`.
- **Log Content:** Logs include timestamp, level, message, logger name, event type, outcome, user info (ID/email), request info (IP, path, method), resource info, and custom details.
- **Retention:** Log rotation is configured, but long-term (6-year) retention needs to be managed by external log aggregation/archiving systems in production.

## 3. Encryption at Rest (`api/core/encryption.py`, `api/models/base.py`)

- **Purpose:** Protect sensitive data stored in the database.
- **Implementation:**
  - Uses Fernet symmetric encryption via the `cryptography` library.
  - A SQLAlchemy `TypeDecorator` (`EncryptedType`) automatically encrypts specified model fields before saving and decrypts them upon loading.
  - Relies on the `ENCRYPTION_KEY` from `settings`.
- **Encrypted Fields (Current):**
  - `User`: `name`, `email`
  - `TherapyPlan`: `title`, `description`
  - `PlanExercise`: `title`, `instructions`
  - `Progress`: `notes`
  - _(Review and add others as necessary)_
- **Developer Responsibility:**
  - **Identify Sensitive Fields:** When adding new models/fields containing potential ePHI, consider if they require encryption and apply the `EncryptedType` in `api/models/base.py`.
  - **Database Migrations:** Adding/removing `EncryptedType` requires a corresponding database migration using the custom migration tool for libSQL. Handle existing data carefully during migrations.
  - **Key Management:** Understand that changing the `ENCRYPTION_KEY` will make previously encrypted data unreadable unless the old key is available for decryption (requires more complex key rotation logic not yet implemented).

## 4. Secure Data Handling (`api/core/exceptions.py`, Pydantic Schemas)

- **Input Validation:** Use Pydantic schemas with specific types (`EmailStr`, etc.) and `Field` constraints (`max_length`, etc.) for robust validation.
- **Error Handling:**
  - Custom exception handlers are registered in `api/main.py`.
  - `generic_exception_handler` catches unexpected `Exception`s, logs the full error internally (`app.log`), but returns a generic 500 message to the client (prevents stack trace leaks).
  - `http_exception_handler` logs `HTTPException` details internally. Ensure `detail` messages in custom `HTTPException`s do not contain PHI.
- **Minimum Necessary Principle:** Filter API responses to only include data necessary for the specific request context and user role (implementation primarily within specific endpoint logic and response models).

## 5. General Guidelines

- **Assume HTTPS in Production:** Code handling data transmission should assume it will occur over HTTPS in production, even if HTTP is used locally.
- **Dependency Updates:** Keep libraries (FastAPI, Pydantic, SQLAlchemy, Cryptography, etc.) updated to patch security vulnerabilities.
- **Secrets Management:** Never commit sensitive information (API keys, passwords, encryption keys) directly into the codebase. Use environment variables and secure management systems for production.
- **Think Compliance:** When implementing new features, consider the potential impact on HIPAA compliance regarding data access, storage, logging, and transmission.
