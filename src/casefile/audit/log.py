"""Append-only, hash-chained audit log (docs/contract.md section 4).

Each line of `log.jsonl` is one LogRecord in RFC 8785 canonical JSON. `record_hash` is the
SHA-256 of the record's canonical JSON without `record_hash`; `prev_hash` chains each record
to the one before (64 zeros for the first). The Merkle root over all `record_hash` values
(RFC 6962) is written to `root.txt` by `seal()` and printed in the case file.

    log = AuditLog("out/case/log.jsonl")
    rid = log.pre("tool_call", {"name": "company/identify", "args_sha256": h})
    ...
    log.post(rid, {"status": "ok", "credits_used": 0, "request_id": req})

or, with the context manager, which records `status: error` if the body raises:

    with log.step("rule_test", {"name": "T05"}) as outcome:
        outcome["evidence_ids"] = ["E3", "E4"]
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import decimal
import hashlib
import json
import os
import subprocess
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import rfc8785

ZERO_HASH = "0" * 64
ACTION_TYPES = ("file_read", "tool_call", "model_call", "rule_test", "gate", "render")
PHASES = ("pre_execution", "post_execution")


def canonical(obj: Any) -> bytes:
    """RFC 8785 (JCS) canonical JSON bytes."""
    return rfc8785.dumps(obj)


def sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def hash_json(obj: Any) -> str:
    """SHA-256 of the canonical JSON of `obj` (use for `args_sha256`, `result_sha256`)."""
    return sha256_hex(canonical(jsonable(obj)))


def record_hash(record: dict[str, Any]) -> str:
    body = {k: v for k, v in record.items() if k != "record_hash"}
    return sha256_hex(canonical(body))


def merkle_root(record_hashes: list[str]) -> str:
    """RFC 6962 Merkle tree hash: leaf = H(0x00||h), node = H(0x01||L||R), odd node promoted."""
    if not record_hashes:
        return hashlib.sha256(b"").hexdigest()
    level = [hashlib.sha256(b"\x00" + bytes.fromhex(h)).digest() for h in record_hashes]
    while len(level) > 1:
        nxt = [
            hashlib.sha256(b"\x01" + level[i] + level[i + 1]).digest()
            for i in range(0, len(level) - 1, 2)
        ]
        if len(level) % 2:
            nxt.append(level[-1])
        level = nxt
    return level[0].hex()


def jsonable(obj: Any) -> Any:
    """Coerce Decimals, dates, Paths, Pydantic models and tuples into plain JSON values."""
    if obj is None or isinstance(obj, (bool, int, str)):
        return obj
    if isinstance(obj, float):
        return obj
    if isinstance(obj, decimal.Decimal):
        return str(obj)
    if isinstance(obj, (dt.datetime, dt.date, dt.time)):
        return obj.isoformat()
    if isinstance(obj, Path):
        return obj.as_posix()
    if isinstance(obj, dict):
        return {str(k): jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [jsonable(v) for v in obj]
    if isinstance(obj, (set, frozenset)):
        return sorted(jsonable(v) for v in obj)
    if hasattr(obj, "model_dump"):
        return jsonable(obj.model_dump(mode="json"))
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return jsonable(dataclasses.asdict(obj))
    return str(obj)


def _now() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=Path(__file__).resolve().parent,
        )
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


class AuditLog:
    """Append-only JSONL log. Thread-safe; fsyncs after every line."""

    def __init__(
        self,
        path: str | os.PathLike[str],
        agent_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.agent_id = agent_id or f"casefile@{_git_sha()}"
        self.session_id = session_id or uuid.uuid4().hex
        self._lock = threading.Lock()
        self._hashes: list[str] = []
        self._open_pre: dict[str, tuple[str, dict[str, Any]]] = {}
        if self.path.exists():
            self._resume()
        self._fh = open(self.path, "ab")  # noqa: SIM115 - held open for the run

    def _resume(self) -> None:
        with open(self.path, "rb") as fh:
            for line in fh:
                if not line.strip():
                    continue
                rec = json.loads(line)
                self._hashes.append(rec["record_hash"])
                if rec["record_phase"] == "pre_execution":
                    self._open_pre[rec["record_id"]] = (rec["action_type"], rec["action_detail"])
                else:
                    self._open_pre.pop(rec.get("parent_record_id"), None)

    @property
    def seq(self) -> int:
        """Number of records written so far (the next record's seq)."""
        return len(self._hashes)

    @property
    def record_hashes(self) -> list[str]:
        return list(self._hashes)

    def _append(
        self,
        action_type: str,
        detail: dict[str, Any],
        outcome: dict[str, Any] | None,
        phase: str,
        parent: str | None,
    ) -> str:
        if action_type not in ACTION_TYPES:
            raise ValueError(f"action_type must be one of {ACTION_TYPES}, got {action_type!r}")
        with self._lock:
            rec: dict[str, Any] = {
                "record_id": str(uuid.uuid4()),
                "seq": len(self._hashes),
                "timestamp": _now(),
                "agent_id": self.agent_id,
                "session_id": self.session_id,
                "action_type": action_type,
                "action_detail": jsonable(detail),
                "outcome": jsonable(outcome),
                "record_phase": phase,
                "parent_record_id": parent,
                "prev_hash": self._hashes[-1] if self._hashes else ZERO_HASH,
            }
            rec["record_hash"] = record_hash(rec)
            self._fh.write(canonical(rec) + b"\n")
            self._fh.flush()
            os.fsync(self._fh.fileno())
            self._hashes.append(rec["record_hash"])
            return rec["record_id"]

    def pre(self, action_type: str, detail: dict[str, Any]) -> str:
        """Record intent before an action; returns the record id to pass to `post`."""
        rid = self._append(action_type, detail, None, "pre_execution", None)
        self._open_pre[rid] = (action_type, jsonable(detail))
        return rid

    def post(self, parent_record_id: str, outcome: dict[str, Any]) -> str:
        """Record the outcome of the action opened by `pre`."""
        try:
            action_type, detail = self._open_pre.pop(parent_record_id)
        except KeyError:
            raise ValueError(f"no open pre_execution record {parent_record_id!r}") from None
        return self._append(action_type, detail, outcome, "post_execution", parent_record_id)

    @contextmanager
    def step(self, action_type: str, detail: dict[str, Any]) -> Iterator[dict[str, Any]]:
        """pre/post around a block; the yielded dict becomes the outcome (status defaults ok)."""
        rid = self.pre(action_type, detail)
        outcome: dict[str, Any] = {}
        try:
            yield outcome
        except BaseException as exc:
            outcome.setdefault("status", "error")
            outcome["error"] = f"{type(exc).__name__}: {exc}"
            self.post(rid, outcome)
            raise
        outcome.setdefault("status", "ok")
        self.post(rid, outcome)

    def merkle_root(self) -> str:
        with self._lock:
            return merkle_root(self._hashes)

    def seal(self, root_path: str | os.PathLike[str] | None = None) -> str:
        """Write `<root> <record count>` to root.txt (next to the log by default). Call last."""
        with self._lock:
            root, size = merkle_root(self._hashes), len(self._hashes)
        target = Path(root_path) if root_path else self.path.with_name("root.txt")
        target.write_text(f"{root} {size}\n", encoding="utf-8")
        return root

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.close()

    def __enter__(self) -> AuditLog:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
