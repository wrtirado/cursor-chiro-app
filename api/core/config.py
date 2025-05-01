import os
# from pydantic import BaseSettings # Old import
from pydantic_settings import BaseSettings # New import from pydantic-settings
from dotenv import load_dotenv
from enum import Enum

load_dotenv() # Load environment variables from .env file

# Define roles using Enum for consistency
class RoleType(str, Enum):
    PATIENT = "patient"
    CHIROPRACTOR = "chiropractor"
    OFFICE_MANAGER = "office_manager"
    BILLING_ADMIN = "billing_admin"
    ADMIN = "admin" # Added Admin role
    # Add other roles like ADMIN if needed

class Settings(BaseSettings):
    PROJECT_NAME: str = "Tirado Chiro API"
    API_V1_STR: str = "/api/v1"

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:changethis@db:5432/app_db")

    # JWT settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "a_very_secret_key_that_should_be_changed") # openssl rand -hex 32
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 # 1 day

    # MinIO/S3 settings
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "minio:9000")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    MINIO_BUCKET: str = os.getenv("MINIO_BUCKET", "therapy-media")
    MINIO_USE_SSL: bool = os.getenv("MINIO_USE_SSL", "false").lower() == "true"

    class Config:
        case_sensitive = True

settings = Settings() 