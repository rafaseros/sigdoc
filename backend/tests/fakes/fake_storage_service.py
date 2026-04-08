from app.domain.ports.storage_service import StorageService


class FakeStorageService(StorageService):
    """In-memory implementation of StorageService for testing.

    Files are stored as a dict keyed by (bucket, path) → bytes.
    """

    def __init__(self) -> None:
        self.files: dict[tuple[str, str], bytes] = {}

    async def upload_file(
        self, bucket: str, path: str, data: bytes, content_type: str
    ) -> str:
        self.files[(bucket, path)] = data
        return path

    async def download_file(self, bucket: str, path: str) -> bytes:
        key = (bucket, path)
        if key not in self.files:
            raise FileNotFoundError(f"No file at bucket={bucket!r}, path={path!r}")
        return self.files[key]

    async def get_presigned_url(
        self, bucket: str, path: str, expires_hours: int = 1
    ) -> str:
        return f"http://fake/{bucket}/{path}"

    async def delete_file(self, bucket: str, path: str) -> None:
        self.files.pop((bucket, path), None)
