from minio import Minio
from minio.error import S3Error
from app.config import settings
from app.core.logging import get_logger
import uuid
from datetime import datetime
from io import BytesIO

logger = get_logger(__name__)


class StorageService:
    """
    MinIO object storage operations with safe key generation.

    Key format: {user_id}/{uuid}_{timestamp}.{ext}
    Example: 123/a7b3c2d1-e4f5-6789-abcd-ef0123456789_20260115123045.jpg
    """

    def __init__(self):
        """Initialize MinIO client."""
        # Parse endpoint to remove protocol
        endpoint = settings.MINIO_ENDPOINT.replace('http://', '').replace('https://', '')

        self.client = Minio(
            endpoint,
            access_key=settings.S3_ACCESS_KEY,
            secret_key=settings.S3_SECRET_KEY,
            secure=settings.S3_SECURE
        )
        self.bucket = settings.S3_BUCKET_RECEIPTS_RAW

        # Ensure bucket exists
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        """Create bucket if it doesn't exist."""
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info(f"Created bucket: {self.bucket}")
        except S3Error as e:
            logger.error(f"Error ensuring bucket exists: {e}")
            raise

    def generate_safe_key(self, user_id: int, original_filename: str) -> str:
        """
        Generate safe storage key with user partitioning.

        Args:
            user_id: User ID for folder segmentation
            original_filename: Original filename to extract extension

        Returns:
            Safe key like "123/uuid_timestamp.jpg"
        """
        # Extract extension safely
        ext = 'bin'  # Default extension
        if '.' in original_filename:
            ext = original_filename.rsplit('.', 1)[-1].lower()
            # Sanitize extension (max 10 chars, alphanumeric only)
            ext = ''.join(c for c in ext if c.isalnum())[:10]

        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        unique_id = str(uuid.uuid4())

        return f"{user_id}/{unique_id}_{timestamp}.{ext}"

    def upload(self, key: str, data: bytes, content_type: str) -> str:
        """
        Upload file to MinIO.

        Args:
            key: Object key (from generate_safe_key)
            data: File bytes
            content_type: MIME type

        Returns:
            Object key on success

        Raises:
            S3Error: On upload failure
        """
        try:
            self.client.put_object(
                bucket_name=self.bucket,
                object_name=key,
                data=BytesIO(data),
                length=len(data),
                content_type=content_type
            )

            logger.info(f"Uploaded to MinIO: {key} ({len(data)} bytes)")
            return key

        except S3Error as e:
            logger.error(f"Error uploading to MinIO: {e}")
            raise

    def download(self, key: str) -> bytes:
        """
        Download file from MinIO.

        Args:
            key: Object key

        Returns:
            File content as bytes

        Raises:
            S3Error: On download failure
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

    def delete(self, key: str) -> None:
        """
        Delete object from MinIO.

        Args:
            key: Object key

        Raises:
            S3Error: On deletion failure
        """
        try:
            self.client.remove_object(self.bucket, key)
            logger.info(f"Deleted from MinIO: {key}")
        except S3Error as e:
            logger.error(f"Error deleting from MinIO: {e}")
            raise

    def get_presigned_url(self, key: str, expires_seconds: int = 3600) -> str:
        """
        Generate presigned URL for temporary access.

        Args:
            key: Object key
            expires_seconds: URL expiration time (default 1 hour)

        Returns:
            Presigned URL string

        Raises:
            S3Error: On error generating URL
        """
        try:
            from datetime import timedelta
            url = self.client.presigned_get_object(
                self.bucket,
                key,
                expires=timedelta(seconds=expires_seconds)
            )
            return url
        except S3Error as e:
            logger.error(f"Error generating presigned URL: {e}")
            raise
