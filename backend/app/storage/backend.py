"""File storage behind an interface (HANDOFF §2): local disk now, S3-compatible later."""

import hashlib
import os
from pathlib import Path
from typing import BinaryIO, Protocol


class StorageBackend(Protocol):
    def save(self, key: str, data: bytes) -> None: ...
    def save_stream(self, key: str, src: BinaryIO, max_bytes: int) -> tuple[int, str]: ...
    def path(self, key: str) -> Path: ...
    def delete(self, key: str) -> None: ...
    def usage_bytes(self) -> int: ...


class LocalStorage:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    def _resolve(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root not in p.parents:
            raise ValueError("storage key escapes the media root")
        return p

    def save(self, key: str, data: bytes) -> None:
        p = self._resolve(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(p)

    def save_stream(self, key: str, src: BinaryIO, max_bytes: int) -> tuple[int, str]:
        """Copy in chunks (large videos never sit in memory). Returns (size, sha256).
        Raises ValueError("too_large") past max_bytes, leaving nothing behind."""
        p = self._resolve(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        digest, size = hashlib.sha256(), 0
        try:
            with tmp.open("wb") as out:
                while chunk := src.read(1 << 20):
                    size += len(chunk)
                    if size > max_bytes:
                        raise ValueError("too_large")
                    digest.update(chunk)
                    out.write(chunk)
            tmp.replace(p)
        finally:
            tmp.unlink(missing_ok=True)
        return size, digest.hexdigest()

    def path(self, key: str) -> Path:
        return self._resolve(key)

    def delete(self, key: str) -> None:
        self._resolve(key).unlink(missing_ok=True)

    def usage_bytes(self) -> int:
        return sum(f.stat().st_size for f in self.root.rglob("*") if f.is_file())


_storage: StorageBackend | None = None


def get_storage() -> StorageBackend:
    global _storage
    if _storage is None:
        _storage = LocalStorage(os.environ.get("MEDIA_ROOT", "/data/media"))
    return _storage


def set_storage(storage: StorageBackend | None) -> None:
    """Test hook."""
    global _storage
    _storage = storage
