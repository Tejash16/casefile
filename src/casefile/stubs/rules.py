"""Stub for casefile.rules (b3): three canned evidence objects on the first vendor/approver pair."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from casefile.audit.payloads import put
from casefile.schemas import (
    Direction,
    EvidenceObject,
    Hypothesis,
    LedgerRow,
    Source,
    SourceKind,
    StaffRecord,
    VendorRecord,
)

THRESHOLDS: dict[str, Any] = {}
TESTS: dict[str, Any] = {}  # unknown tests link by entity overlap only


@dataclass
class StubContext:
    rows: list[LedgerRow]
    vendors: list[VendorRecord]
    staff: list[StaffRecord]
    graph: Any = None
    audit: Any = None
    evidence_counter: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


def build_context(rows, vendors, staff, graph=None, audit=None) -> StubContext:
    return StubContext(rows=rows, vendors=vendors, staff=staff, graph=graph, audit=audit)


def _evidence(
    ctx: StubContext,
    test_id: str,
    direction: Direction,
    strength: float,
    summary: str,
    rows: list[LedgerRow],
    kind: SourceKind = SourceKind.ledger_rows,
) -> EvidenceObject:
    rid = ctx.audit.pre("rule_test", {"name": test_id}) if ctx.audit else "no-audit"
    ctx.evidence_counter += 1
    quote = "; ".join(f"{r.row_id} {r.date} {r.vendor_name_raw} {r.amount}" for r in rows)
    ev = EvidenceObject(
        evidence_id=f"E{ctx.evidence_counter}",
        test_id=test_id,
        subject_ids=sorted({r.approver_id for r in rows if r.approver_id}),
        object_ids=sorted({r.vendor_id for r in rows if r.vendor_id}),
        direction=direction,
        strength=strength,
        summary=summary,
        quote=quote,
        source=Source(kind=kind, refs=[r.row_id for r in rows]),
        sha256=put(quote),
        log_record_id=rid,
    )
    if ctx.audit:
        ctx.audit.post(rid, {"status": "ok", "evidence_ids": [ev.evidence_id], "stub": True})
    return ev


def run_tests(test_ids: list[str], ctx: StubContext) -> list[EvidenceObject]:
    if not ctx.vendors:
        return []
    vid = ctx.vendors[0].vendor_id
    rows = [r for r in ctx.rows if r.vendor_id == vid] or ctx.rows[:1]
    return [
        _evidence(
            ctx,
            "T15",
            Direction.supports,
            0.9,
            "Stub: approver previously worked at the vendor.",
            rows[:1],
        ),
        _evidence(
            ctx,
            "T05",
            Direction.supports,
            0.7,
            "Stub: invoices fall just under the approver's limit.",
            rows,
        ),
        _evidence(
            ctx,
            "T02",
            Direction.neutral,
            0.3,
            "Stub: vendor address is residential.",
            rows[:1],
            SourceKind.vendor_master,
        ),
    ]


def rerank(
    hypotheses: list[Hypothesis], evidence: list[EvidenceObject], centrality: dict[str, float]
) -> list[Hypothesis]:
    return sorted(hypotheses, key=lambda h: -h.prior_score)
