# api/core/s3_client.py
import io
from minio import Minio
from minio.error import S3Error
from datetime import timedelta
import logging
from typing import Optional
from fastapi import HTTPException

from api.core.config import settings

logger = logging.getLogger(__name__) # Use FastAPI's logger or a custom one

_minio_client = None

def get_s3_client():
    """Initializes and returns the MinIO client instance."""
    global _minio_client
    if _minio_client is None:
        try:
            _minio_client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_USE_SSL
            )
            logger.info(f"MinIO client initialized for endpoint: {settings.MINIO_ENDPOINT}")
            # Check if bucket exists and create if not
            found = _minio_client.bucket_exists(settings.MINIO_BUCKET)
            if not found:
                _minio_client.make_bucket(settings.MINIO_BUCKET)
                logger.info(f"Created MinIO bucket: {settings.MINIO_BUCKET}")
            else:
                logger.info(f"Using existing MinIO bucket: {settings.MINIO_BUCKET}")
        except S3Error as e:
            logger.error(f"Error initializing MinIO client or checking bucket: {e}")
            _minio_client = None # Ensure client is None if init fails
            raise HTTPException(status_code=500, detail="Could not initialize S3/MinIO connection")
        except Exception as e:
            logger.error(f"Unexpected error initializing MinIO client: {e}")
            _minio_client = None
            raise HTTPException(status_code=500, detail="Unexpected error initializing S3/MinIO connection")

    return _minio_client

def upload_file_to_s3(
    file_stream: io.BytesIO,
    object_name: str,
    content_type: str,
    bucket_name: str = settings.MINIO_BUCKET
) -> Optional[str]:
    """Uploads a file stream to the specified S3/MinIO bucket."""
    client = get_s3_client()
    if not client:
        return None # Initialization failed
    try:
        # Need the size of the stream
        file_stream.seek(0, io.SEEK_END)
        file_size = file_stream.tell()
        file_stream.seek(0) # Reset stream position

        result = client.put_object(
            bucket_name,
            object_name,
            file_stream,
            length=file_size,
            content_type=content_type
        )
        logger.info(f"Successfully uploaded {object_name} to bucket {bucket_name}, etag: {result.etag}")
        # Return the object name, the URL can be constructed or presigned later
        return object_name
    except S3Error as e:
        logger.error(f"Error uploading {object_name} to S3: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error uploading {object_name} to S3: {e}")
        return None

def get_presigned_url_for_s3_object(
    object_name: str,
    bucket_name: str = settings.MINIO_BUCKET,
    expiry_hours: int = 24 # Default URL expiry: 24 hours
) -> Optional[str]:
    """Generates a pre-signed URL for accessing an object."""
    client = get_s3_client()
    if not client:
        return None
    try:
        url = client.presigned_get_object(
            bucket_name,
            object_name,
            expires=timedelta(hours=expiry_hours)
        )
        return url
    except S3Error as e:
        logger.error(f"Error generating presigned URL for {object_name}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error generating presigned URL for {object_name}: {e}")
        return None

# Optional: Add function for deleting objects if needed later
# def delete_object_from_s3(object_name: str, bucket_name: str = settings.MINIO_BUCKET):
#     ... 