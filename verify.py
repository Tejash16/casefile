#!/usr/bin/env python3
"""Standalone verifier for a Casefile audit log. Standard library only; shares no code with
the writer, so it can be run from a fresh clone:

    python verify.py out/demo/log.jsonl            # reads out/demo/root.txt if present
    python verify.py out/demo/log.jsonl --root <64-hex>

Checks, per line: valid JSON; record_hash = SHA-256(RFC 8785 JSON without record_hash);
prev_hash = previous line's record_hash (64 zeros first); seq = line number; each post points
at an earlier, still-open pre of the same action type. Then the RFC 6962 Merkle root over all
record hashes against root.txt (catches truncation), and against the root printed in
case_file.md if one sits next to the log. Exit 0 if all pass, 1 otherwise.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

ZERO_HASH = "0" * 64
PHASES = ("pre_execution", "post_execution")
FIELDS = (
    "record_id",
    "seq",
    "timestamp",
    "agent_id",
    "session_id",
    "action_type",
    "action_detail",
    "outcome",
    "record_phase",
    "parent_record_id",
    "prev_hash",
    "record_hash",
)

# --- RFC 8785 JSON Canonicalization Scheme (vendored) -------------------------------------


def _jcs_number(x):
    if isinstance(x, bool):
        raise TypeError("bool is not a number")
    if isinstance(x, int):
        if abs(x) > 2**53 - 1:
            raise ValueError(f"integer {x} outside the IEEE 754 safe range")
        return str(x)
    if not math.isfinite(x):
        raise ValueError("NaN and Infinity are not valid JSON")
    if x == 0:
        return "0"
    # ECMAScript Number.prototype.toString, from the shortest round-trip digits
    sign = "-" if x < 0 else ""
    mantissa, _, exp = repr(abs(x)).partition("e")
    int_part, _, frac_part = mantissa.partition(".")
    all_digits = int_part + frac_part
    stripped = all_digits.lstrip("0")
    # value = 0.<digits> x 10^n
    n = len(int_part) + int(exp or 0) - (len(all_digits) - len(stripped))
    digits = stripped.rstrip("0")
    k = len(digits)
    if k <= n <= 21:
        out = digits + "0" * (n - k)
    elif 0 < n <= 21:
        out = digits[:n] + "." + digits[n:]
    elif -6 < n <= 0:
        out = "0." + "0" * (-n) + digits
    else:
        e = n - 1
        out = (
            digits[0]
            + ("." + digits[1:] if k > 1 else "")
            + "e"
            + ("+" if e >= 0 else "-")
            + str(abs(e))
        )
    return sign + out


def jcs(obj):
    """Canonical JSON string per RFC 8785."""
    if obj is None:
        return "null"
    if obj is True:
        return "true"
    if obj is False:
        return "false"
    if isinstance(obj, (int, float)):
        return _jcs_number(obj)
    if isinstance(obj, str):
        return json.dumps(obj, ensure_ascii=False)
    if isinstance(obj, (list, tuple)):
        return "[" + ",".join(jcs(v) for v in obj) + "]"
    if isinstance(obj, dict):
        keys = sorted(obj, key=lambda k: k.encode("utf-16-be"))
        return (
            "{"
            + ",".join(json.dumps(k, ensure_ascii=False) + ":" + jcs(obj[k]) for k in keys)
            + "}"
        )
    raise TypeError(f"cannot canonicalise {type(obj).__name__}")


def canonical(obj):
    return jcs(obj).encode("utf-8")


# --- Hashes -------------------------------------------------------------------------------


def record_hash(rec):
    return hashlib.sha256(
        canonical({k: v for k, v in rec.items() if k != "record_hash"})
    ).hexdigest()


def merkle_root(hashes):
    """RFC 6962: leaf = H(0x00||h), node = H(0x01||L||R), odd node promoted."""
    if not hashes:
        return hashlib.sha256(b"").hexdigest()
    level = [hashlib.sha256(b"\x00" + bytes.fromhex(h)).digest() for h in hashes]
    while len(level) > 1:
        nxt = [
            hashlib.sha256(b"\x01" + level[i] + level[i + 1]).digest()
            for i in range(0, len(level) - 1, 2)
        ]
        if len(level) % 2:
            nxt.append(level[-1])
        level = nxt
    return level[0].hex()


# --- Verification -------------------------------------------------------------------------


def read_root_file(path):
    """root.txt holds '<64-hex root> <record count>'; returns (root, size or None)."""
    parts = Path(path).read_text(encoding="utf-8").split()
    return parts[0].lower(), (int(parts[1]) if len(parts) > 1 else None)


def read_case_file_root(path):
    m = re.search(
        r"Merkle root[^0-9a-f]*([0-9a-f]{64})[^\n]*?(\d+) records",
        Path(path).read_text(encoding="utf-8"),
    )
    return (m.group(1), int(m.group(2))) if m else None


def verify(log_path, expected_root=None, expected_size=None, case_root=None):
    """Return (failures, warnings, info). Each failure is (check, seq_or_None, message)."""
    failures, warnings = [], []
    hashes, open_pre = [], {}
    prev = ZERO_HASH
    with open(log_path, "rb") as fh:
        lines = [ln for ln in fh.read().split(b"\n") if ln.strip()]
    for i, raw in enumerate(lines):
        try:
            rec = json.loads(raw)
            if not isinstance(rec, dict):
                raise ValueError("not an object")
        except ValueError as exc:
            failures.append(
                ("json", i, f"line {i + 1} is not a JSON record ({exc}); record altered")
            )
            hashes.append(None)
            prev = None
            continue
        seq = rec.get("seq", i)
        missing = [f for f in FIELDS if f not in rec]
        if missing:
            failures.append(("fields", seq, f"seq {seq}: missing fields {missing}"))
        stored = rec.get("record_hash")
        hashes.append(stored)
        try:
            recomputed = record_hash(rec)
        except (TypeError, ValueError) as exc:
            recomputed = f"<{exc}>"
        if recomputed != stored:
            failures.append(
                (
                    "record_hash",
                    seq,
                    f"seq {seq}: record_hash mismatch, stored {str(stored)[:12]}... "
                    f"recomputed {recomputed[:12]}... (record content altered)",
                )
            )
        elif prev is not None and rec.get("prev_hash") != prev:
            failures.append(
                (
                    "chain",
                    seq,
                    f"seq {seq} (line {i + 1}): prev_hash does not match the record_hash of the "
                    f"line before (records reordered, inserted or removed)",
                )
            )
        elif seq != i:
            failures.append(
                ("seq", seq, f"line {i + 1}: expected seq {i}, found {seq} (sequence gap)")
            )
        prev = stored
        phase, rid = rec.get("record_phase"), rec.get("record_id")
        if phase not in PHASES:
            failures.append(
                ("pairing", seq, f"seq {seq}: record_phase {phase!r} is not one of {PHASES}")
            )
        elif phase == "pre_execution":
            open_pre[rid] = rec.get("action_type")
        else:
            parent = rec.get("parent_record_id")
            if parent not in open_pre:
                failures.append(
                    (
                        "pairing",
                        seq,
                        f"seq {seq}: post_execution has no earlier open pre_execution {parent}",
                    )
                )
            elif open_pre.pop(parent) != rec.get("action_type"):
                failures.append(
                    ("pairing", seq, f"seq {seq}: action_type differs from its pre_execution")
                )
    for rid in open_pre:
        warnings.append(f"pre_execution {rid} has no post_execution (run interrupted?)")

    root = merkle_root([h for h in hashes if h]) if all(hashes) else None
    if root and expected_root:
        if root != expected_root:
            sealed = f" sealed at {expected_size} records" if expected_size is not None else ""
            hint = ""
            if expected_size is not None and expected_size != len(hashes):
                hint = (
                    "; log truncated"
                    if len(hashes) < expected_size
                    else "; records appended after seal"
                )
            failures.append(
                (
                    "root",
                    None,
                    f"Merkle root of {len(hashes)} records {root[:12]}... != expected "
                    f"{expected_root[:12]}...{sealed}{hint}",
                )
            )
    elif expected_root is None:
        warnings.append("no root.txt or --root given: chain verified, tail truncation not checked")
    if case_root and all(hashes):
        c_root, c_size = case_root
        if c_size > len(hashes):
            failures.append(
                ("root", None, f"case_file.md cites {c_size} records, log has {len(hashes)}")
            )
        elif merkle_root(hashes[:c_size]) != c_root:
            failures.append(
                (
                    "root",
                    None,
                    f"case_file.md Merkle root {c_root[:12]}... does not match records "
                    f"0..{c_size - 1}",
                )
            )
    return failures, warnings, {"records": len(hashes), "root": root}


def summarize(failures):
    """One line per failed check: the first failure of each kind, with a count of the rest."""
    lines, seen = [], {}
    for check, _, msg in failures:
        seen.setdefault(check, []).append(msg)
    for check, msgs in seen.items():
        more = f"  [+{len(msgs) - 1} more {check} failures]" if len(msgs) > 1 else ""
        lines.append(f"FAIL {check}: {msgs[0]}{more}")
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description="Verify a Casefile hash-chained audit log.")
    ap.add_argument("log", help="path to log.jsonl")
    ap.add_argument("--root", help="expected Merkle root (default: root.txt next to the log)")
    ap.add_argument("--verbose", "-v", action="store_true", help="list every failure")
    args = ap.parse_args(argv)
    log = Path(args.log)
    if not log.is_file():
        print(f"FAIL: {log} not found")
        return 1
    size = None
    root = args.root.lower() if args.root else None
    if root is None and (log.parent / "root.txt").is_file():
        root, size = read_root_file(log.parent / "root.txt")
    case_root = None
    if (log.parent / "case_file.md").is_file():
        case_root = read_case_file_root(log.parent / "case_file.md")
    failures, warnings, info = verify(log, root, size, case_root)
    for w in warnings:
        print(f"warn: {w}")
    if args.verbose:
        for check, _, msg in failures:
            print(f"FAIL {check}: {msg}")
    else:
        for line in summarize(failures):
            print(line)
    if failures:
        print(f"VERIFY FAILED: {len(failures)} problem(s) in {info['records']} records ({log})")
        return 1
    print(f"VERIFY OK: {info['records']} records, chain intact, Merkle root {info['root']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
