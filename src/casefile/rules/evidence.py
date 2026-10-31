"""Builders for EvidenceObjects: literal quotes, canonical payloads, sha256 (b3).

Every evidence object's payload is `quote + "\\n" + canonical JSON of the source records`, put in
`casefile.audit.payloads` so the citation check can recompute the hash and find the quote in it.
Tests leave `evidence_id` and `log_record_id` as placeholders; `run_tests` assigns both.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from decimal import Decimal
from typing import Any

from casefile.audit.log import canonical, jsonable
from casefile.audit.payloads import put
from casefile.schemas import Direction, EvidenceObject, LedgerRow, Source, SourceKind

PENDING = "pending"


def inr(amount: Decimal | float | int) -> str:
    """Indian digit grouping: 498000 -> 4,98,000; 12345678.5 -> 1,23,45,678.50."""
    q = Decimal(str(amount)).quantize(Decimal("0.01"))
    sign = "-" if q < 0 else ""
    whole, frac = f"{abs(q):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups: list[str] = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join([*groups, tail])
    return f"{sign}{whole}" + ("" if frac == "00" else f".{frac}")


def row_line(r: LedgerRow) -> str:
    """`L000042 2025-03-14 Orbital Fasteners Pvt Ltd 4,98,000 inv INV-102 approver S004`."""
    parts = [r.row_id, r.date.isoformat(), r.vendor_name_raw, inr(r.amount)]
    if r.invoice_no:
        parts.append(f"inv {r.invoice_no}")
    if r.approver_id:
        parts.append(f"approver {r.approver_id}")
    elif r.approver_name_raw:
        parts.append(f"approver {r.approver_name_raw}")
    if r.posted_at is not None:
        parts.append(f"posted {r.posted_at.isoformat(sep=' ', timespec='minutes')}")
    return " ".join(parts)


def rows_quote(rows: Sequence[LedgerRow], max_rows: int) -> str:
    lines = [row_line(r) for r in rows[:max_rows]]
    if len(rows) > max_rows:
        lines.append(f"(+{len(rows) - max_rows} more rows in the payload)")
    return "; ".join(lines)


def make(
    *,
    test_id: str,
    direction: Direction,
    strength: float,
    summary: str,
    quote: str,
    kind: SourceKind,
    refs: Iterable[str],
    records: Any,
    subject_ids: Iterable[str | None] = (),
    object_ids: Iterable[str | None] = (),
    as_of: str | None = None,
) -> EvidenceObject:
    payload = quote + "\n" + canonical(jsonable(records)).decode("utf-8")
    return EvidenceObject(
        evidence_id=PENDING,
        test_id=test_id,
        subject_ids=sorted({s for s in subject_ids if s}),
        object_ids=sorted({o for o in object_ids if o}),
        direction=direction,
        strength=round(min(max(strength, 0.0), 1.0), 3),
        summary=summary,
        quote=quote,
        source=Source(kind=kind, refs=list(dict.fromkeys(refs)), as_of=as_of),
        sha256=put(payload),
        log_record_id=PENDING,
    )


def from_rows(
    *,
    test_id: str,
    direction: Direction,
    strength: float,
    summary: str,
    rows: Sequence[LedgerRow],
    max_rows: int,
    prefix: str = "",
    subject_ids: Iterable[str | None] | None = None,
    object_ids: Iterable[str | None] | None = None,
) -> EvidenceObject:
    """Evidence quoting ledger rows; subjects/objects default to the rows' approvers/vendors."""
    quote = prefix + rows_quote(rows, max_rows)
    return make(
        test_id=test_id,
        direction=direction,
        strength=strength,
        summary=summary,
        quote=quote,
        kind=SourceKind.ledger_rows,
        refs=[r.row_id for r in rows],
        records=[r.model_dump(mode="json") for r in rows],
        subject_ids=subject_ids if subject_ids is not None else [r.approver_id for r in rows],
        object_ids=object_ids if object_ids is not None else [r.vendor_id for r in rows],
    )
