"""
MinIO storage adapter implementing the StorageService port.

NOTE: minio-py is a synchronous client. For the MVP with small files (<50MB),
calling sync methods inside async functions is acceptable and won't block the
event loop significantly. If true async is needed later (large files, high
concurrency), wrap calls with `asyncio.to_thread()`.
"""

import io
from datetime import timedelta

from minio import Minio

from app.config import get_settings
from app.domain.ports.storage_service import StorageService


class MinioStorageService(StorageService):
    def __init__(self) -> None:
        settings = get_settings()
        self._client = Minio(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        # For presigned URLs: replace internal hostname with external one
        self._internal_endpoint = settings.minio_endpoint
        self._external_endpoint = settings.minio_external_endpoint

    async def upload_file(
        self, bucket: str, path: str, data: bytes, content_type: str
    ) -> str:
        """Upload file to MinIO. Returns the object path."""
        # Sync call — acceptable for MVP; see module docstring.
        self._client.put_object(
            bucket_name=bucket,
            object_name=path,
            data=io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        return path

    async def download_file(self, bucket: str, path: str) -> bytes:
        """Download file from MinIO. Returns raw bytes."""
        # Sync call — acceptable for MVP; see module docstring.
        response = self._client.get_object(bucket_name=bucket, object_name=path)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    async def get_presigned_url(
        self, bucket: str, path: str, expires_hours: int = 1
    ) -> str:
        """Generate a presigned GET URL for downloading a file."""
        # Sync call — acceptable for MVP; see module docstring.
        return self._client.presigned_get_object(
            bucket_name=bucket,
            object_name=path,
            expires=timedelta(hours=expires_hours),
        )

    async def delete_file(self, bucket: str, path: str) -> None:
        """Delete a file from MinIO."""
        # Sync call — acceptable for MVP; see module docstring.
        self._client.remove_object(bucket_name=bucket, object_name=path)
