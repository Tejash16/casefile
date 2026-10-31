"""Where agent audit records go.

Every model call and gate decision writes pre/post records to the run's `AuditLog`. The pipeline
either calls `set_audit(log)` once per run or passes `audit=log` to each agent function. With
neither, records go to a standalone log at `out/_agents_log.jsonl` (ad-hoc runs and smoke tests).
"""

from __future__ import annotations

import threading
from typing import Any, Protocol


class AuditSink(Protocol):
    def pre(self, action_type: str, detail: dict[str, Any]) -> str: ...

    def post(self, parent_record_id: str, outcome: dict[str, Any]) -> str: ...


_audit: AuditSink | None = None
_lock = threading.Lock()


def set_audit(audit: AuditSink | None) -> None:
    """Route agent audit records to `audit` (the run's AuditLog). None resets to the default."""
    global _audit
    with _lock:
        _audit = audit


def get_audit(audit: AuditSink | None = None) -> AuditSink:
    """`audit` if given, else the run's log set by `set_audit`, else a standalone default log."""
    global _audit
    if audit is not None:
        return audit
    with _lock:
        if _audit is None:
            from casefile.audit.log import AuditLog

            _audit = AuditLog("out/_agents_log.jsonl")
        return _audit
