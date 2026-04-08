"""
MinIO storage adapter implementing the StorageService port.

minio-py is a synchronous client. All blocking I/O calls are offloaded to a
thread pool via `asyncio.to_thread()` so the event loop is never blocked.
"""

import asyncio
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
        def _upload() -> None:
            self._client.put_object(
                bucket_name=bucket,
                object_name=path,
                data=io.BytesIO(data),
                length=len(data),
                content_type=content_type,
            )

        await asyncio.to_thread(_upload)
        return path

    async def download_file(self, bucket: str, path: str) -> bytes:
        """Download file from MinIO. Returns raw bytes."""
        def _download() -> bytes:
            response = self._client.get_object(bucket_name=bucket, object_name=path)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()

        return await asyncio.to_thread(_download)

    async def get_presigned_url(
        self, bucket: str, path: str, expires_hours: int = 1
    ) -> str:
        """Generate a presigned GET URL for downloading a file."""
        def _presign() -> str:
            return self._client.presigned_get_object(
                bucket_name=bucket,
                object_name=path,
                expires=timedelta(hours=expires_hours),
            )

        return await asyncio.to_thread(_presign)

    async def delete_file(self, bucket: str, path: str) -> None:
        """Delete a file from MinIO."""
        await asyncio.to_thread(
            self._client.remove_object, bucket, path
        )
