import os

# from pydantic import BaseSettings # Old import
from pydantic_settings import BaseSettings  # New import from pydantic-settings
from dotenv import load_dotenv
from enum import Enum
from typing import Optional, List

load_dotenv()  # Load environment variables from .env file


# Define roles using Enum for consistency
class RoleType(str, Enum):
    PATIENT = "patient"
    CHIROPRACTOR = "chiropractor"
    OFFICE_MANAGER = "office_manager"
    BILLING_ADMIN = "billing_admin"
    ADMIN = "admin"  # Added Admin role
    # Add other roles like ADMIN if needed


class Settings(BaseSettings):
    PROJECT_NAME: str = "Tirado Chiro API"
    API_V1_STR: str = "/api/v1"

    # Environment mode (e.g., 'development', 'production')
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+libsql://db:8080?mode=rw")

    # JWT settings
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY", "a_very_secret_key_that_should_be_changed"
    )  # openssl rand -hex 32
    ALGORITHM: str = "HS256"
    # Make token expiration configurable, default to 30 mins for HIPAA
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    )

    # Optional TLS Configuration (paths to cert/key files)
    # These would be used if running Uvicorn directly with TLS, not typically with Docker/reverse proxy
    TLS_CERT_PATH: Optional[str] = os.getenv("TLS_CERT_PATH", None)
    TLS_KEY_PATH: Optional[str] = os.getenv("TLS_KEY_PATH", None)

    # CORS Origins (Moved here for clarity)
    # Allow specific origins based on environment
    CORS_ORIGINS: List[str] = [
        os.getenv(
            "FRONTEND_URL", "http://localhost:3000"
        ),  # Primary frontend URL from env
        "http://localhost:5173",  # Vite default
        # Add other allowed origins if necessary
    ]
    # Allow all origins in development for ease of use? Use with caution.
    # CORS_ORIGINS: List[str] = ["*"] if os.getenv("ENVIRONMENT", "development") == "development" else [
    #     os.getenv("FRONTEND_URL", "http://localhost:3000"),
    # ]

    # MinIO/S3 settings
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "minio:9000")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    MINIO_BUCKET: str = os.getenv("MINIO_BUCKET", "therapy-media")
    MINIO_USE_SSL: bool = os.getenv("MINIO_USE_SSL", "false").lower() == "true"

    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    AUDIT_LOG_FILE: str = os.getenv("AUDIT_LOG_FILE", "logs/audit.log")
    APP_LOG_FILE: str = os.getenv(
        "APP_LOG_FILE", "logs/app.log"
    )  # Optional: Separate file for general app logs

    class Config:
        case_sensitive = True


settings = Settings()
