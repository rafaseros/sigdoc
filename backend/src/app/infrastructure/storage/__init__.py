from functools import lru_cache

from app.domain.ports.storage_service import StorageService
from app.infrastructure.storage.minio_storage import MinioStorageService


@lru_cache
def get_storage_service() -> StorageService:
    return MinioStorageService()
