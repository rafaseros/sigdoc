from abc import ABC, abstractmethod


class StorageService(ABC):
    @abstractmethod
    async def upload_file(
        self, bucket: str, path: str, data: bytes, content_type: str
    ) -> str:
        ...

    @abstractmethod
    async def download_file(self, bucket: str, path: str) -> bytes:
        ...

    @abstractmethod
    async def get_presigned_url(
        self, bucket: str, path: str, expires_hours: int = 1
    ) -> str:
        ...

    @abstractmethod
    async def delete_file(self, bucket: str, path: str) -> None:
        ...
