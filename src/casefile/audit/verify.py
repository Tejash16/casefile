"""In-package log verifier: `verify(path) -> VerifyReport`.

The repo-root `verify.py` is an independent, standard-library-only implementation of the same
checks for judges; tests/audit asserts that the two agree on every tamper case.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from casefile.audit.log import (
    ACTION_TYPES,
    PHASES,
    ZERO_HASH,
    canonical,
    merkle_root,
    record_hash,
)

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
CASE_ROOT_RE = re.compile(r"Merkle root[^0-9a-f]*([0-9a-f]{64})[^\n]*?(\d+) records")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


@dataclass
class Failure:
    check: str  # json | fields | record_hash | canonical | chain | seq | pairing | root | files
    seq: int | None
    message: str


@dataclass
class VerifyReport:
    path: str
    records: int = 0
    root: str | None = None
    expected_root: str | None = None
    failures: list[Failure] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures

    def lines(self, verbose: bool = False) -> list[str]:
        """One line per failed check (first occurrence, with a count), then a verdict line."""
        out = [f"warn: {w}" for w in self.warnings]
        if verbose:
            out += [f"FAIL {f.check}: {f.message}" for f in self.failures]
        else:
            by_check: dict[str, list[Failure]] = {}
            for f in self.failures:
                by_check.setdefault(f.check, []).append(f)
            for check, fs in by_check.items():
                more = f"  [+{len(fs) - 1} more {check} failures]" if len(fs) > 1 else ""
                out.append(f"FAIL {check}: {fs[0].message}{more}")
        if self.ok:
            out.append(f"VERIFY OK: {self.records} records, chain intact, Merkle root {self.root}")
        else:
            out.append(
                f"VERIFY FAILED: {len(self.failures)} problem(s) in {self.records} records "
                f"({self.path})"
            )
        return out

    def __str__(self) -> str:
        return "\n".join(self.lines())


def read_root_file(path: Path) -> tuple[str | None, int | None]:
    """root.txt holds '<64-hex root> <record count>'; (None, None) if malformed."""
    parts = path.read_text(encoding="utf-8").split()
    if not parts or not HEX64.match(parts[0].lower()):
        return None, None
    size = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
    return parts[0].lower(), size


def _rendered_files(rec: dict[str, Any]) -> dict[str, str]:
    """Files and hashes a `render` post_execution record vouches for."""
    out = rec.get("outcome")
    if not isinstance(out, dict):
        return {}
    files = {k: v for k, v in (out.get("files") or {}).items() if isinstance(v, str)}
    detail = rec.get("action_detail")
    name = detail.get("name") if isinstance(detail, dict) else None
    if isinstance(out.get("result_sha256"), str) and name == "case_file":
        files.setdefault("case_file.md", out["result_sha256"])
    return files


def verify(
    path: str | Path,
    expected_root: str | None = None,
    expected_size: int | None = None,
    check_case_file: bool = True,
) -> VerifyReport:
    """Recompute every record_hash, canonical form, the prev_hash chain, seq, pre/post pairing
    and the root.

    Without `expected_root`, reads `root.txt` next to the log if present. Files next to the log
    that a `render` record hashed (case_file.md, ...) must still match, and the root printed in
    case_file.md must match the prefix of the log it covers.
    """
    path = Path(path)
    rep = VerifyReport(path=str(path))
    if not path.is_file():
        rep.failures.append(Failure("json", None, f"{path} not found"))
        return rep
    root_txt = path.with_name("root.txt")
    if expected_root is None and root_txt.is_file():
        expected_root, expected_size = read_root_file(root_txt)
        if expected_root is None:
            rep.failures.append(Failure("root", None, "root.txt is empty or malformed"))
    rep.expected_root = expected_root

    hashes: list[str | None] = []
    open_pre: dict[str, Any] = {}
    rendered: dict[str, tuple[str, int]] = {}
    prev: str | None = ZERO_HASH
    lines = [ln for ln in path.read_bytes().split(b"\n") if ln.strip()]
    for i, raw in enumerate(lines):
        try:
            rec = json.loads(raw)
            if not isinstance(rec, dict):
                raise ValueError("not an object")
        except ValueError as exc:
            rep.failures.append(
                Failure("json", i, f"line {i + 1} is not a JSON record ({exc}); record altered")
            )
            hashes.append(None)
            prev = None
            continue
        seq = rec.get("seq", i)
        missing = [f for f in FIELDS if f not in rec]
        if missing:
            rep.failures.append(Failure("fields", seq, f"seq {seq}: missing fields {missing}"))
        stored = rec.get("record_hash")
        stored_ok = isinstance(stored, str) and bool(HEX64.match(stored))
        hashes.append(stored if stored_ok else None)
        try:
            recomputed = record_hash(rec)
            canonical_ok = canonical(rec) == raw.rstrip(b"\r")
        except (TypeError, ValueError) as exc:
            recomputed, canonical_ok = f"<{exc}>", False
        if recomputed != stored:
            rep.failures.append(
                Failure(
                    "record_hash",
                    seq,
                    f"seq {seq}: record_hash mismatch, stored {str(stored)[:12]}... "
                    f"recomputed {recomputed[:12]}... (record content altered)",
                )
            )
        elif not canonical_ok:
            rep.failures.append(
                Failure(
                    "canonical",
                    seq,
                    f"seq {seq}: line is not RFC 8785 canonical JSON (edited, or duplicate keys)",
                )
            )
        elif prev is not None and rec.get("prev_hash") != prev:
            rep.failures.append(
                Failure(
                    "chain",
                    seq,
                    f"seq {seq} (line {i + 1}): prev_hash does not match the record_hash of the "
                    f"line before (records reordered, inserted or removed)",
                )
            )
        elif seq != i:
            rep.failures.append(
                Failure("seq", seq, f"line {i + 1}: expected seq {i}, found {seq} (sequence gap)")
            )
        prev = stored if stored_ok else None

        phase, rid = rec.get("record_phase"), rec.get("record_id")
        parent = rec.get("parent_record_id")
        if rec.get("action_type") not in ACTION_TYPES:
            rep.warnings.append(f"seq {seq}: unknown action_type {rec.get('action_type')!r}")
        if phase not in PHASES:
            rep.failures.append(
                Failure("pairing", seq, f"seq {seq}: record_phase {phase!r} is not one of {PHASES}")
            )
        elif not isinstance(rid, str) or not (parent is None or isinstance(parent, str)):
            rep.failures.append(
                Failure("pairing", seq, f"seq {seq}: record_id/parent_record_id must be strings")
            )
        elif phase == "pre_execution":
            open_pre[rid] = rec.get("action_type")
        else:
            if parent not in open_pre:
                rep.failures.append(
                    Failure(
                        "pairing",
                        seq,
                        f"seq {seq}: post_execution has no earlier open pre_execution {parent}",
                    )
                )
            elif open_pre.pop(parent) != rec.get("action_type"):
                rep.failures.append(
                    Failure(
                        "pairing", seq, f"seq {seq}: action_type differs from its pre_execution"
                    )
                )
            if rec.get("action_type") == "render":
                for name, sha in _rendered_files(rec).items():
                    rendered[name] = (sha, seq)
    for rid in open_pre:
        rep.warnings.append(f"pre_execution {rid} has no post_execution (run interrupted?)")

    rep.records = len(hashes)
    complete = [h for h in hashes if h]
    rep.root = merkle_root(complete) if len(complete) == len(hashes) else None
    if rep.root and expected_root:
        if rep.root != expected_root:
            sealed = f" sealed at {expected_size} records" if expected_size is not None else ""
            hint = ""
            if expected_size is not None and expected_size != len(hashes):
                hint = (
                    "; log truncated"
                    if len(hashes) < expected_size
                    else "; records appended after seal"
                )
            rep.failures.append(
                Failure(
                    "root",
                    None,
                    f"Merkle root of {len(hashes)} records {rep.root[:12]}... != expected "
                    f"{expected_root[:12]}...{sealed}{hint}",
                )
            )
    elif expected_root is None and not root_txt.is_file():
        rep.warnings.append(
            "no root.txt or --root given: chain verified, tail truncation not checked"
        )

    for name, (sha, seq) in sorted(rendered.items()):
        target = path.with_name(name)
        if "/" in name or "\\" in name or not target.is_file():
            continue
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual != sha:
            rep.failures.append(
                Failure(
                    "files",
                    None,
                    f"{name} sha256 {actual[:12]}... != {sha[:12]}... logged by render record "
                    f"seq {seq} (file edited after it was rendered)",
                )
            )

    case_md = path.with_name("case_file.md")
    if check_case_file and rep.root and case_md.is_file():
        m = CASE_ROOT_RE.search(case_md.read_text(encoding="utf-8"))
        if m:
            c_root, c_size = m.group(1), int(m.group(2))
            if c_size > len(complete):
                rep.failures.append(
                    Failure(
                        "root",
                        None,
                        f"case_file.md cites {c_size} records, log has {len(complete)}",
                    )
                )
            elif merkle_root(complete[:c_size]) != c_root:
                rep.failures.append(
                    Failure(
                        "root",
                        None,
                        f"case_file.md Merkle root {c_root[:12]}... does not match records "
                        f"0..{c_size - 1}",
                    )
                )
    return rep


def main(argv: list[str] | None = None) -> int:
    """CLI entry: `casefile verify <log> [--root HEX] [-v]`; prints the report, returns 0 or 1."""
    import argparse

    ap = argparse.ArgumentParser(prog="casefile verify")
    ap.add_argument("log")
    ap.add_argument("--root")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args(argv)
    rep = verify(args.log, expected_root=args.root.lower() if args.root else None)
    print("\n".join(rep.lines(verbose=args.verbose)))
    return 0 if rep.ok else 1
