"""RuleContext: everything a rule test reads, built once per run (b3)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from casefile.rules.config import THRESHOLDS, Threshold
from casefile.schemas import Hypothesis, LedgerRow, PersonBrief, StaffRecord, VendorRecord

LEDGER_COLUMNS = [
    "row_id",
    "date",
    "vendor",
    "vendor_id",
    "vendor_name_raw",
    "invoice_no",
    "amount",
    "approver_id",
    "created_by",
    "posted_at",
    "po_number",
]


@dataclass
class RuleContext:
    rows: pd.DataFrame  # one row per LedgerRow, columns LEDGER_COLUMNS, sorted by date
    ledger: dict[str, LedgerRow]  # row_id -> the original row, for quotes and payloads
    vendors: dict[str, VendorRecord]
    staff: dict[str, StaffRecord]
    graph: Any = None
    thresholds: dict[str, Threshold] = field(default_factory=lambda: dict(THRESHOLDS))
    evidence_counter: int = 0
    audit: Any = None
    vendor_people: dict[str, list[PersonBrief]] = field(default_factory=dict)
    hypotheses: list[Hypothesis] = field(default_factory=list)

    def th(self, name: str) -> Any:
        """The value of a named threshold."""
        return self.thresholds[name].value

    def rows_for(self, row_ids: list[str]) -> list[LedgerRow]:
        return [self.ledger[r] for r in row_ids]


def _naive(ts: Any) -> Any:
    """Wall-clock time without tz: off-hours is about the poster's local hour."""
    return ts.replace(tzinfo=None) if ts is not None and ts.tzinfo else ts


def ledger_frame(rows: list[LedgerRow]) -> pd.DataFrame:
    df = pd.DataFrame(
        {
            "row_id": [r.row_id for r in rows],
            "date": pd.to_datetime([r.date for r in rows]),
            "vendor": [r.vendor_id or f"key:{r.vendor_key}" for r in rows],
            "vendor_id": [r.vendor_id for r in rows],
            "vendor_name_raw": [r.vendor_name_raw for r in rows],
            "invoice_no": [(r.invoice_no or "").strip() or None for r in rows],
            "amount": [float(r.amount) for r in rows],
            "approver_id": [r.approver_id for r in rows],
            "created_by": [r.created_by for r in rows],
            "posted_at": pd.to_datetime([_naive(r.posted_at) for r in rows]),
            "po_number": [r.po_number for r in rows],
        },
        columns=LEDGER_COLUMNS,
    )
    return df.sort_values(["date", "row_id"], kind="stable").reset_index(drop=True)


def _default_vendor_people() -> Callable[[VendorRecord], list[PersonBrief]]:
    """b2's resolve.vendor_people when it has landed, else founders + decision makers."""
    try:
        from casefile.resolve import vendor_people  # type: ignore[attr-defined]

        return vendor_people
    except (ImportError, AttributeError):

        def local(v: VendorRecord) -> list[PersonBrief]:
            if v.crustdata is None:
                return []
            return [*v.crustdata.founders, *v.crustdata.decision_makers]

        return local


def build_context(
    rows: list[LedgerRow],
    vendors: list[VendorRecord],
    staff: list[StaffRecord],
    graph: Any = None,
    audit: Any = None,
    hypotheses: list[Hypothesis] | None = None,
    thresholds: dict[str, Threshold] | None = None,
) -> RuleContext:
    people = _default_vendor_people()
    return RuleContext(
        rows=ledger_frame(rows),
        ledger={r.row_id: r for r in rows},
        vendors={v.vendor_id: v for v in vendors},
        staff={s.staff_id: s for s in staff},
        graph=graph,
        thresholds=dict(thresholds or THRESHOLDS),
        audit=audit,
        vendor_people={v.vendor_id: list(people(v)) for v in vendors},
        hypotheses=list(hypotheses or []),
    )
