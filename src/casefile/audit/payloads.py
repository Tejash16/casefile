"""Content-addressed store for the source payloads that evidence quotes come from.

Whoever builds an EvidenceObject registers the exact bytes its `quote` was taken from and
uses the returned hash as `EvidenceObject.sha256`:

    from casefile.audit.payloads import put
    ev = EvidenceObject(..., quote=quote, sha256=put(payload_text), ...)

`report.check.check_citations` looks the payload up by that hash, recomputes the SHA-256 and
requires the quote to appear in it literally. `put` is in-memory (no I/O, safe inside rules);
the pipeline calls `default_store.dump(out_dir / "payloads")` so a later check can reload them.
"""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from casefile.audit.log import canonical, jsonable


def to_bytes(payload: bytes | str | Any) -> bytes:
    """bytes as is, str as UTF-8, anything else as RFC 8785 canonical JSON."""
    if isinstance(payload, bytes):
        return payload
    if isinstance(payload, str):
        return payload.encode("utf-8")
    return canonical(jsonable(payload))


class PayloadStore(Mapping[str, bytes]):
    """sha256 hex -> payload bytes."""

    def __init__(self) -> None:
        self._data: dict[str, bytes] = {}
        self._lock = threading.Lock()

    def put(self, payload: bytes | str | Any) -> str:
        data = to_bytes(payload)
        sha = hashlib.sha256(data).hexdigest()
        with self._lock:
            self._data[sha] = data
        return sha

    def __getitem__(self, sha: str) -> bytes:
        return self._data[sha]

    def __iter__(self) -> Iterator[str]:
        return iter(list(self._data))

    def __len__(self) -> int:
        return len(self._data)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def dump(self, directory: str | Path) -> Path:
        d = Path(directory)
        d.mkdir(parents=True, exist_ok=True)
        for sha, data in list(self._data.items()):
            (d / sha).write_bytes(data)
        return d

    @classmethod
    def load(cls, directory: str | Path) -> PayloadStore:
        store = cls()
        for f in Path(directory).iterdir():
            if f.is_file():
                store.put(f.read_bytes())
        return store


default_store = PayloadStore()


def put(payload: bytes | str | Any) -> str:
    """Register a payload in the process-wide store; returns its sha256 hex."""
    return default_store.put(payload)
