"""In-package log verifier: `verify(path) -> VerifyReport`.

The repo-root `verify.py` is an independent, standard-library-only implementation of the same
checks for judges; tests/audit asserts that the two agree on every tamper case.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from casefile.audit.log import ACTION_TYPES, PHASES, ZERO_HASH, merkle_root, record_hash

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


@dataclass
class Failure:
    check: str  # json | fields | record_hash | chain | seq | pairing | root
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


def read_root_file(path: Path) -> tuple[str, int | None]:
    parts = path.read_text(encoding="utf-8").split()
    return parts[0].lower(), (int(parts[1]) if len(parts) > 1 else None)


def verify(
    path: str | Path,
    expected_root: str | None = None,
    expected_size: int | None = None,
    check_case_file: bool = True,
) -> VerifyReport:
    """Recompute every record_hash, the prev_hash chain, seq, pre/post pairing and the root.

    Without `expected_root`, reads `root.txt` next to the log if present. If `case_file.md`
    sits next to the log, the root it prints is checked against the matching prefix.
    """
    path = Path(path)
    rep = VerifyReport(path=str(path))
    if not path.is_file():
        rep.failures.append(Failure("json", None, f"{path} not found"))
        return rep
    root_txt = path.with_name("root.txt")
    if expected_root is None and root_txt.is_file():
        expected_root, expected_size = read_root_file(root_txt)
    rep.expected_root = expected_root

    hashes: list[str | None] = []
    open_pre: dict[str, str] = {}
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
        hashes.append(stored)
        try:
            recomputed = record_hash(rec)
        except (TypeError, ValueError) as exc:
            recomputed = f"<{exc}>"
        if recomputed != stored:
            rep.failures.append(
                Failure(
                    "record_hash",
                    seq,
                    f"seq {seq}: record_hash mismatch, stored {str(stored)[:12]}... "
                    f"recomputed {recomputed[:12]}... (record content altered)",
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
        prev = stored

        phase, rid = rec.get("record_phase"), rec.get("record_id")
        if rec.get("action_type") not in ACTION_TYPES:
            rep.warnings.append(f"seq {seq}: unknown action_type {rec.get('action_type')!r}")
        if phase not in PHASES:
            rep.failures.append(
                Failure("pairing", seq, f"seq {seq}: record_phase {phase!r} is not one of {PHASES}")
            )
        elif phase == "pre_execution":
            open_pre[rid] = rec.get("action_type")
        else:
            parent = rec.get("parent_record_id")
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
    elif expected_root is None:
        rep.warnings.append(
            "no root.txt or --root given: chain verified, tail truncation not checked"
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
