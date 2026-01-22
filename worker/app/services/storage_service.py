from minio import Minio
from minio.error import S3Error
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class StorageService:
    """MinIO storage service for worker (download receipts)."""

    def __init__(self):
        """Initialize MinIO client."""
        endpoint = settings.MINIO_ENDPOINT.replace('http://', '').replace('https://', '')

        self.client = Minio(
            endpoint,
            access_key=settings.S3_ACCESS_KEY,
            secret_key=settings.S3_SECRET_KEY,
            secure=settings.S3_SECURE
        )
        self.bucket = settings.S3_BUCKET_RECEIPTS_RAW

    def download(self, key: str) -> bytes:
        """
        Download file from MinIO.

        Args:
            key: Object key

        Returns:
            File content as bytes
        """
        try:
            response = self.client.get_object(self.bucket, key)
            data = response.read()
            response.close()
            response.release_conn()

            logger.info(f"Downloaded from MinIO: {key} ({len(data)} bytes)")
            return data

        except S3Error as e:
            logger.error(f"Error downloading from MinIO: {e}")
            raise
