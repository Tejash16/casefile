"""Audit log: chain, Merkle root, and the three tampers the demo shows."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import random
import subprocess
import sys
import threading
from decimal import Decimal
from pathlib import Path

import pytest
import rfc8785

from casefile.audit.log import ZERO_HASH, AuditLog, merkle_root
from casefile.audit.verify import verify

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("standalone_verify", ROOT / "verify.py")
standalone = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(standalone)


def build_log(out: Path, pairs: int = 10) -> Path:
    """`pairs` pre/post pairs = 2*pairs records; odd seqs are posts carrying an outcome."""
    path = out / "log.jsonl"
    with AuditLog(path, agent_id="casefile@test", session_id="s1") as log:
        for i in range(pairs):
            rid = log.pre("tool_call", {"name": f"company/identify#{i}", "args_sha256": "ab" * 32})
            log.post(rid, {"status": "ok", "credits_used": i * 2, "request_id": f"req-{i}"})
        log.seal()
    return path


def lines_of(path: Path) -> list[bytes]:
    return path.read_bytes().splitlines(keepends=True)


def run_cli(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "verify.py"), str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def fail_lines(stdout: str) -> list[str]:
    return [ln for ln in stdout.splitlines() if ln.startswith("FAIL")]


# --- clean log ---------------------------------------------------------------------------


def test_twenty_records_verify(tmp_path: Path) -> None:
    path = build_log(tmp_path)
    recs = [json.loads(ln) for ln in lines_of(path)]
    assert len(recs) == 20
    assert recs[0]["prev_hash"] == ZERO_HASH
    assert [r["seq"] for r in recs] == list(range(20))
    assert all(recs[i]["prev_hash"] == recs[i - 1]["record_hash"] for i in range(1, 20))
    assert recs[1]["parent_record_id"] == recs[0]["record_id"]
    assert recs[1]["action_detail"] == recs[0]["action_detail"]

    rep = verify(path)
    assert rep.ok, rep.lines()
    assert rep.root == (tmp_path / "root.txt").read_text().split()[0]
    assert (tmp_path / "root.txt").read_text().split()[1] == "20"

    proc = run_cli(path)
    assert proc.returncode == 0, proc.stdout
    assert "VERIFY OK: 20 records" in proc.stdout


def test_lines_are_canonical_json(tmp_path: Path) -> None:
    path = build_log(tmp_path, pairs=2)
    for ln in lines_of(path):
        assert ln.rstrip(b"\n") == rfc8785.dumps(json.loads(ln))


# --- the three tampers -------------------------------------------------------------------


def test_flip_one_byte_in_outcome_names_seq_7(tmp_path: Path) -> None:
    path = build_log(tmp_path)
    lines = lines_of(path)
    assert b'"status":"ok"' in lines[7]
    lines[7] = lines[7].replace(b'"status":"ok"', b'"status":"oK"', 1)
    path.write_bytes(b"".join(lines))

    rep = verify(path)
    assert not rep.ok
    assert [(f.check, f.seq) for f in rep.failures] == [("record_hash", 7)]

    proc = run_cli(path)
    assert proc.returncode == 1
    (line,) = fail_lines(proc.stdout)
    assert line.startswith("FAIL record_hash: seq 7:")


def test_delete_last_record_fails_on_root(tmp_path: Path) -> None:
    path = build_log(tmp_path)
    path.write_bytes(b"".join(lines_of(path)[:-1]))

    rep = verify(path)
    assert [f.check for f in rep.failures] == ["root"]
    assert "log truncated" in rep.failures[0].message

    proc = run_cli(path)
    assert proc.returncode == 1
    (line,) = fail_lines(proc.stdout)
    assert line.startswith("FAIL root: Merkle root of 19 records")


def test_reorder_two_records_fails_on_chain(tmp_path: Path) -> None:
    path = build_log(tmp_path)
    lines = lines_of(path)
    lines[4], lines[5] = lines[5], lines[4]
    path.write_bytes(b"".join(lines))

    rep = verify(path)
    assert not rep.ok
    assert rep.failures[0].check == "chain"

    proc = run_cli(path)
    assert proc.returncode == 1
    first = fail_lines(proc.stdout)[0]
    assert first.startswith("FAIL chain: seq 5 (line 5)")


def test_both_verifiers_agree(tmp_path: Path) -> None:
    clean = build_log(tmp_path)
    variants = {"clean": lines_of(clean)}
    flipped = list(variants["clean"])
    flipped[7] = flipped[7].replace(b'"status":"ok"', b'"status":"oK"')
    variants["flip"] = flipped
    variants["truncate"] = variants["clean"][:-1]
    swapped = list(variants["clean"])
    swapped[4], swapped[5] = swapped[5], swapped[4]
    variants["swap"] = swapped
    variants["drop_middle"] = variants["clean"][:10] + variants["clean"][11:]
    variants["bad_json"] = variants["clean"][:3] + [b"{not json\n"] + variants["clean"][4:]
    root, size = standalone.read_root_file(tmp_path / "root.txt")
    for name, content in variants.items():
        clean.write_bytes(b"".join(content))
        pkg = verify(clean)
        fails, _, info = standalone.verify(clean, root, size)
        assert [(f.check, f.seq) for f in pkg.failures] == [(c, s) for c, s, _ in fails], name
        assert [f.message for f in pkg.failures] == [m for _, _, m in fails], name
        assert pkg.root == info["root"], name


# --- crash safety, pairing, resume, threads ----------------------------------------------


def test_crash_leaves_verifiable_prefix(tmp_path: Path) -> None:
    path = tmp_path / "log.jsonl"
    log = AuditLog(path)
    rid = log.pre("model_call", {"name": "propose"})
    log.post(rid, {"status": "ok"})
    log.pre("tool_call", {"name": "company/enrich"})  # process dies here
    log.close()
    rep = verify(path)
    assert rep.ok
    assert any("no post_execution" in w for w in rep.warnings)
    assert standalone.verify(path)[0] == []


def test_step_records_errors(tmp_path: Path) -> None:
    path = tmp_path / "log.jsonl"
    with AuditLog(path) as log:
        with log.step("rule_test", {"name": "T05"}) as outcome:
            outcome["evidence_ids"] = ["E1"]
        with pytest.raises(RuntimeError), log.step("rule_test", {"name": "T06"}):
            raise RuntimeError("boom")
    recs = [json.loads(ln) for ln in lines_of(path)]
    assert recs[1]["outcome"] == {"status": "ok", "evidence_ids": ["E1"]}
    assert recs[3]["outcome"]["status"] == "error"
    assert "boom" in recs[3]["outcome"]["error"]
    assert verify(path).ok


def test_post_requires_open_pre(tmp_path: Path) -> None:
    with AuditLog(tmp_path / "log.jsonl") as log:
        rid = log.pre("gate", {"name": "H1"})
        log.post(rid, {"status": "ok"})
        with pytest.raises(ValueError):
            log.post(rid, {"status": "ok"})
        with pytest.raises(ValueError):
            log.pre("email", {})


def test_resume_continues_chain(tmp_path: Path) -> None:
    path = tmp_path / "log.jsonl"
    with AuditLog(path) as log:
        rid = log.pre("file_read", {"name": "ledger.csv"})
    with AuditLog(path) as log:
        log.post(rid, {"status": "ok", "amount": Decimal("498000.00")})
        assert log.seq == 2
    rep = verify(path)
    assert rep.ok, rep.lines()
    assert json.loads(lines_of(path)[1])["outcome"]["amount"] == "498000.00"


def test_concurrent_writers_keep_chain(tmp_path: Path) -> None:
    path = tmp_path / "log.jsonl"
    with AuditLog(path) as log:

        def work(n: int) -> None:
            for i in range(25):
                with log.step("tool_call", {"name": f"w{n}-{i}"}):
                    pass

        threads = [threading.Thread(target=work, args=(n,)) for n in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        log.seal()
    rep = verify(path)
    assert rep.ok and rep.records == 200, rep.lines()


# --- Merkle and JCS ----------------------------------------------------------------------


def _mth(leaves: list[bytes]) -> bytes:
    """RFC 6962 section 2.1, recursive definition."""
    n = len(leaves)
    if n == 0:
        return hashlib.sha256(b"").digest()
    if n == 1:
        return hashlib.sha256(b"\x00" + leaves[0]).digest()
    k = 1
    while k * 2 < n:
        k *= 2
    return hashlib.sha256(b"\x01" + _mth(leaves[:k]) + _mth(leaves[k:])).digest()


@pytest.mark.parametrize("n", list(range(0, 34)))
def test_merkle_matches_rfc6962(n: int) -> None:
    hashes = [hashlib.sha256(str(i).encode()).hexdigest() for i in range(n)]
    expected = _mth([bytes.fromhex(h) for h in hashes]).hex()
    assert merkle_root(hashes) == expected
    assert standalone.merkle_root(hashes) == expected


JCS_SAMPLES = [
    None,
    True,
    False,
    0,
    -0.0,
    1,
    -17,
    2**53 - 1,
    0.1,
    1.5,
    -2.75,
    123.0,
    1e21,
    1e20,
    1e-7,
    1e-6,
    5e-324,
    1.7976931348623157e308,
    0.000123456,
    123456789.123,
    "",
    "plain",
    'q"uote\\back',
    "ctl\x00\x01\x1f\x7f\b\f\n\r\t",
    "unicode é ₹ 日本 😀",
    {"b": 1, "a": 2, "é": 3, "€": 4, "😀": 5, "דּ": 6},
    [1, [2, [3, {"z": None}]]],
    {"nested": {"list": [0.5, "x", {"k": [True, None]}]}},
]


@pytest.mark.parametrize("value", JCS_SAMPLES, ids=range(len(JCS_SAMPLES)))
def test_vendored_jcs_matches_rfc8785(value: object) -> None:
    assert standalone.canonical(value) == rfc8785.dumps(value)


def test_vendored_jcs_matches_random_floats() -> None:
    rng = random.Random(42)
    for _ in range(5000):
        x = rng.uniform(-1, 1) * 10 ** rng.randint(-30, 30)
        assert standalone.canonical(x) == rfc8785.dumps(x), x


# --- review fixes ------------------------------------------------------------------------


def both(path: Path) -> list[tuple[str, int | None]]:
    """(check, seq) failures, asserting both verifiers agree."""
    pkg = [(f.check, f.seq) for f in verify(path).failures]
    alone = [(c, s) for c, s, _ in standalone.verify(path)[0]]
    assert pkg == alone
    return pkg


def test_duplicate_key_fails_canonical(tmp_path: Path) -> None:
    path = build_log(tmp_path)
    lines = lines_of(path)
    lines[7] = lines[7].replace(b"{", b'{"outcome":{"verdict":"Substantiated"},', 1)
    path.write_bytes(b"".join(lines))
    assert both(path) == [("canonical", 7)]


def test_respaced_line_fails_canonical(tmp_path: Path) -> None:
    path = build_log(tmp_path)
    lines = lines_of(path)
    lines[3] = json.dumps(json.loads(lines[3])).encode() + b"\n"
    path.write_bytes(b"".join(lines))
    assert both(path) == [("canonical", 3)]


def test_crlf_checkout_still_verifies(tmp_path: Path) -> None:
    path = build_log(tmp_path)
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    assert both(path) == []


@pytest.mark.parametrize(
    "value",
    [1e16, -2.5e300, float("nan"), float("inf"), 2**60, "lone \ud800 surrogate", {"\ud83d": 1}],
)
def test_awkward_values_round_trip(tmp_path: Path, value: object) -> None:
    path = tmp_path / "log.jsonl"
    with AuditLog(path) as log:
        rid = log.pre("rule_test", {"name": "T08", "stat": value})
        log.post(rid, {"status": "ok", "value": value})
        log.seal()
    assert both(path) == []


def test_resume_refuses_torn_line(tmp_path: Path) -> None:
    path = build_log(tmp_path, pairs=2)
    path.write_bytes(path.read_bytes() + b'{"record_id":"x"')
    with pytest.raises(ValueError, match="partial record"):
        AuditLog(path)


@pytest.mark.parametrize(
    ("field", "value", "check"),
    [
        ("record_hash", "not-hex", "record_hash"),
        ("record_hash", 12345, "record_hash"),
        ("record_id", ["a", "b"], "record_hash"),
    ],
)
def test_malformed_fields_fail_without_crashing(
    tmp_path: Path, field: str, value: object, check: str
) -> None:
    path = build_log(tmp_path)
    lines = lines_of(path)
    rec = json.loads(lines[4])
    rec[field] = value
    lines[4] = rfc8785.dumps(rec) + b"\n"
    path.write_bytes(b"".join(lines))
    fails = both(path)
    assert fails and fails[0] == (check, 4)
    proc = run_cli(path)
    assert proc.returncode == 1 and "Traceback" not in proc.stderr


def test_unhashable_record_id_with_valid_hash(tmp_path: Path) -> None:
    """A record whose hash was recomputed after making record_id a list: pairing, no crash."""
    path = tmp_path / "log.jsonl"
    with AuditLog(path) as log:
        log.pre("gate", {"name": "H1"})
    rec = json.loads(lines_of(path)[0])
    rec["record_id"] = ["x"]
    from casefile.audit.log import record_hash

    rec["record_hash"] = record_hash(rec)
    path.write_bytes(rfc8785.dumps(rec) + b"\n")
    assert both(path) == [("pairing", 0)]


def test_empty_root_txt_fails(tmp_path: Path) -> None:
    path = build_log(tmp_path)
    (tmp_path / "root.txt").write_text("", encoding="utf-8")
    assert both(path) == [("root", None)]
    assert run_cli(path).returncode == 1
