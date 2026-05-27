"""Supabase Storage adapter — implements the Storage Protocol.

Re-added per user request; overrides §11/§13 deferral; OPTIONAL.
The adapter is only instantiated when SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY
are present in settings — the app boots fine without them.
"""

from __future__ import annotations

from supabase import acreate_client
from supabase._async.client import AsyncClient
from storage3._async.file_api import AsyncBucketProxy

from app.infrastructure.storage.types import StoredObject


class SupabaseStorage:
    """Async adapter for Supabase Storage (storage3 under the hood)."""

    def __init__(self, url: str, service_role_key: str) -> None:
        self._url = url
        self._key = service_role_key
        # client is created lazily on first use so the constructor stays sync
        self._client: AsyncClient | None = None

    async def _bucket(self, bucket: str) -> AsyncBucketProxy:
        if self._client is None:
            self._client = await acreate_client(self._url, self._key)
        return self._client.storage.from_(bucket)

    async def put(
        self,
        *,
        key: str,
        data: bytes,
        content_type: str,
    ) -> StoredObject:
        bucket_name, path = _split_key(key)
        bucket = await self._bucket(bucket_name)
        await bucket.upload(
            path=path,
            file=data,
            file_options={"content-type": content_type, "upsert": "true"},
        )
        return StoredObject(key=key, size_bytes=len(data), content_type=content_type)

    async def signed_url(self, *, key: str, expires_in: int = 3600) -> str:
        bucket_name, path = _split_key(key)
        bucket = await self._bucket(bucket_name)
        result = await bucket.create_signed_url(path=path, expires_in=expires_in)
        # storage3 returns a dict with signedURL or signedUrl depending on version
        url: str | None = result.get("signedURL") or result.get("signedUrl")
        if not url:
            raise ValueError(f"Supabase did not return a signed URL for key={key!r}")
        return url

    async def delete(self, *, key: str) -> None:
        bucket_name, path = _split_key(key)
        bucket = await self._bucket(bucket_name)
        await bucket.remove(paths=[path])


def _split_key(key: str) -> tuple[str, str]:
    """Split ``bucket/path/to/file`` → ``(bucket, path/to/file)``."""
    parts = key.split("/", 1)
    if len(parts) != 2 or not parts[1]:
        raise ValueError(f"Storage key must be 'bucket/path', got {key!r}")
    return parts[0], parts[1]
