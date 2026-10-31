from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from casefile.agents import _audit, client
from casefile.audit.log import AuditLog


def text_block(text: str, citations: list[dict] | None = None) -> SimpleNamespace:
    cits = [SimpleNamespace(**c) for c in citations] if citations else None
    return SimpleNamespace(type="text", text=text, citations=cits)


def message(
    content: Any, stop_reason: str = "end_turn", cache_read: int = 0, model: str = "fake-model"
) -> SimpleNamespace:
    if isinstance(content, (dict, list)) and not (
        isinstance(content, list) and content and isinstance(content[0], SimpleNamespace)
    ):
        content = [text_block(json.dumps(content))]
    elif isinstance(content, str):
        content = [text_block(content)]
    return SimpleNamespace(
        id="msg_fake",
        model=model,
        content=content,
        stop_reason=stop_reason,
        stop_details=None,
        usage=SimpleNamespace(
            input_tokens=100,
            output_tokens=20,
            cache_read_input_tokens=cache_read,
            cache_creation_input_tokens=0,
        ),
    )


class _Endpoint:
    def __init__(self, parent: FakeClient) -> None:
        self.parent = parent

    def create(self, **kwargs: Any) -> Any:
        self.parent.calls.append(kwargs)
        if not self.parent.responses:
            raise AssertionError("FakeClient ran out of canned responses")
        resp = self.parent.responses.pop(0)
        if callable(resp):
            resp = resp(kwargs)
        if isinstance(resp, Exception):
            raise resp
        return resp


class FakeClient:
    def __init__(self, responses: list[Any] | None = None) -> None:
        self.responses = list(responses or [])
        self.calls: list[dict[str, Any]] = []
        self.messages = _Endpoint(self)
        self.beta = SimpleNamespace(messages=_Endpoint(self))


@pytest.fixture
def audit_log(tmp_path):
    log = AuditLog(tmp_path / "log.jsonl")
    _audit.set_audit(log)
    yield log
    _audit.set_audit(None)
    log.close()


@pytest.fixture
def fake(audit_log):
    fc = FakeClient()
    client.set_client(fc)
    client.reset_usage_totals()
    yield fc
    client.set_client(None)


def read_log(log: AuditLog) -> list[dict]:
    return [json.loads(line) for line in log.path.read_text(encoding="utf-8").splitlines()]
