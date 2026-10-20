"""File storage behind an interface (HANDOFF §2): local disk now, S3-compatible later."""

import os
from pathlib import Path
from typing import Protocol


class StorageBackend(Protocol):
    def save(self, key: str, data: bytes) -> None: ...
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
