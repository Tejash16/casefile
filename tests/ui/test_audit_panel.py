"""ui/audit.py helpers: log table, metrics, verify and the tamper demo (no Streamlit needed)."""

from __future__ import annotations

from pathlib import Path

from casefile.audit.log import AuditLog
from casefile.ui import audit


def make_run(out: Path) -> Path:
    with AuditLog(out / "log.jsonl") as log:
        rid = log.pre("tool_call", {"name": "company/identify", "cache_hit": False})
        log.post(rid, {"status": "ok", "credits_used": 2.5, "request_id": "r1"})
        rid = log.pre("model_call", {"name": "propose", "model": "m"})
        log.post(rid, {"status": "ok", "tokens_in": 100, "tokens_out": 40})
        for i in range(6):
            with log.step("rule_test", {"name": f"T0{i}"}):
                pass
        log.seal()
    return out


def test_empty_dir(tmp_path: Path) -> None:
    assert audit.read_log(tmp_path) == []
    assert audit.merkle_root(tmp_path) is None
    assert audit.make_tampered(tmp_path) is None


def test_rows_and_metrics(tmp_path: Path) -> None:
    recs = audit.read_log(make_run(tmp_path))
    rows = audit.log_rows(recs)
    assert len(rows) == 16
    assert rows[0] == {
        "seq": 0,
        "time": rows[0]["time"],
        "action_type": "tool_call",
        "phase": "pre",
        "name": "company/identify",
        "status": "",
        "cache_hit": False,
        "credits": None,
    }
    assert rows[1]["credits"] == 2.5 and rows[1]["phase"] == "post"
    m = audit.metrics(recs)
    assert (m["crustdata_calls"], m["credits"], m["model_calls"], m["tokens"]) == (1, 2.5, 1, 140)
    assert m["records"] == 16
    root = audit.merkle_root(tmp_path)
    assert root is not None and len(root[0]) == 64 and root[1] == 16


def test_partial_last_line_is_skipped(tmp_path: Path) -> None:
    make_run(tmp_path)
    with open(tmp_path / "log.jsonl", "ab") as fh:
        fh.write(b'{"seq": 16, "record_id"')
    assert len(audit.read_log(tmp_path)) == 16


def test_verify_and_tamper_demo(tmp_path: Path) -> None:
    make_run(tmp_path)
    ok, lines = audit.run_verify(tmp_path / "log.jsonl")
    assert ok and lines[-1].startswith("VERIFY OK: 16 records")

    before = (tmp_path / "log.jsonl").read_bytes()
    path, seq, what = audit.make_tampered(tmp_path)
    assert path.name == "log_tampered.jsonl" and seq == 8 and "timestamp digit" in what
    assert (tmp_path / "log.jsonl").read_bytes() == before  # original untouched
    ok, lines = audit.run_verify(path)
    assert not ok
    fails = [ln for ln in lines if ln.startswith("FAIL")]
    assert fails == [fails[0]] and fails[0].startswith("FAIL record_hash: seq 8:")
    assert audit.run_verify(tmp_path / "log.jsonl")[0]  # the real log still verifies
