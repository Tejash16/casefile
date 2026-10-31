"""Stub for casefile.audit.log (a3): plain hash-chained JSON lines, no RFC 8785, no Merkle tree."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ZERO = "0" * 64


class AuditLog:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("", encoding="utf-8")
        self.session_id = str(uuid.uuid4())
        self._seq = 0
        self._prev = ZERO
        self._types: dict[str, str] = {}

    def _append(self, record: dict[str, Any]) -> str:
        record |= {
            "seq": self._seq,
            "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "agent_id": "casefile@stub",
            "session_id": self.session_id,
            "prev_hash": self._prev,
        }
        body = json.dumps(record, sort_keys=True, default=str)
        record["record_hash"] = hashlib.sha256(body.encode()).hexdigest()
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
        self._seq += 1
        self._prev = record["record_hash"]
        return record["record_id"]

    def pre(self, action_type: str, detail: dict[str, Any]) -> str:
        rid = str(uuid.uuid4())
        self._types[rid] = str(action_type)
        return self._append(
            {
                "record_id": rid,
                "action_type": str(action_type),
                "action_detail": detail,
                "outcome": None,
                "record_phase": "pre_execution",
                "parent_record_id": None,
            }
        )

    def post(self, parent_record_id: str, outcome: dict[str, Any]) -> str:
        return self._append(
            {
                "record_id": str(uuid.uuid4()),
                "action_type": self._types.get(parent_record_id, "tool_call"),
                "action_detail": {},
                "outcome": outcome,
                "record_phase": "post_execution",
                "parent_record_id": parent_record_id,
            }
        )

    @property
    def seq(self) -> int:
        return self._seq

    def merkle_root(self) -> str:
        return self._prev

    def seal(self) -> str:
        self.path.with_name("root.txt").write_text(f"{self._prev} {self._seq}\n", encoding="utf-8")
        return self._prev

    def close(self) -> None:
        pass
