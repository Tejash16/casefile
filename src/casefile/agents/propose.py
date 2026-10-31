"""Stage 2: propose 3 to 8 typed hypotheses from the tip, ledger statistics and the masters.

The model sees statistics, never ledger rows. It may only use typologies from the menu and test ids
from the registry; anything else fails validation and is retried with the error fed back.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Sequence
from typing import Any

from casefile.agents import client
from casefile.agents._audit import AuditSink
from casefile.agents.models import ProposeOutput, registry_test_ids
from casefile.audit.log import jsonable
from casefile.schemas import Hypothesis, StaffRecord, Tip, Typology, VendorRecord

MIN_HYPOTHESES = 3
MAX_HYPOTHESES = 8
# A hypothesis about four approvers and four vendors cannot be tested as one allegation.
MAX_SUBJECTS = 2
MAX_OBJECTS = 2
# Keys under which ingest.ledger_stats may carry per-vendor aggregates (spend, invoice count).
PER_VENDOR_KEYS = ("per_vendor", "vendors", "by_vendor", "spend_per_vendor")


class LedgerRowsInPrompt(ValueError):
    """Raised if anything resembling a raw ledger row would reach the prompt."""


def _assert_no_rows(obj: Any, path: str = "ledger_stats") -> None:
    if isinstance(obj, dict):
        if "row_id" in obj:
            raise LedgerRowsInPrompt(f"{path} contains a ledger row (has row_id)")
        for k, v in obj.items():
            _assert_no_rows(v, f"{path}.{k}")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            _assert_no_rows(v, f"{path}[{i}]")


def _per_vendor(ledger_stats: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Split per-vendor aggregates out of ledger_stats: ({vendor_id: stats}, remaining stats).

    Accepts nested shapes under PER_VENDOR_KEYS and flat `<metric>_per_vendor: {vendor_id: value}`
    maps (ingest.ledger_stats), merged into one dict per vendor keyed by metric name.
    """
    rest = dict(ledger_stats)
    out: dict[str, dict[str, Any]] = {}
    for key in list(rest):
        raw = rest[key]
        if key.endswith("_per_vendor") and isinstance(raw, dict):
            metric = key.removesuffix("_per_vendor")
            for vid, v in raw.items():
                out.setdefault(str(vid), {})[metric] = v
            rest.pop(key)
        elif key in PER_VENDOR_KEYS:
            if isinstance(raw, dict):
                for vid, v in raw.items():
                    out.setdefault(str(vid), {}).update(v if isinstance(v, dict) else {"spend": v})
                rest.pop(key)
            elif isinstance(raw, list):
                for item in raw:
                    if isinstance(item, dict) and item.get("vendor_id"):
                        out.setdefault(str(item["vendor_id"]), {}).update(
                            {k: v for k, v in item.items() if k != "vendor_id"}
                        )
                rest.pop(key)
    return out, rest


def _first(agg: dict[str, Any], *keys: str) -> Any:
    """Pop and return the first present key (so it is not repeated under its raw name)."""
    for k in keys:
        if k in agg:
            return agg.pop(k)
    return None


def _jsonl(rows: Iterable[dict[str, Any]]) -> str:
    return "\n".join(json.dumps(jsonable(r), ensure_ascii=False) for r in rows)


def _typology_menu(typologies: Sequence[str] | None) -> str:
    menu = client.load_reference("typologies")
    if not typologies:
        return menu
    allowed = {str(t) for t in typologies}
    keep = []
    for line in menu.splitlines():
        m = re.match(r"\| `([a-z_]+)` \|", line)
        if m and m.group(1) not in allowed:
            continue
        keep.append(line)
    return "\n".join(keep)


def build_request(
    tip: Tip | str,
    ledger_stats: dict[str, Any],
    vendors: Sequence[VendorRecord],
    staff: Sequence[StaffRecord],
    typologies: Sequence[str] | None = None,
) -> tuple[list[str], list[dict[str, Any]]]:
    """System blocks and messages for the propose call (exposed for tests and prompt review)."""
    stats = dict(ledger_stats or {})
    _assert_no_rows(stats)
    per_vendor, stats = _per_vendor(stats)
    system_text, instructions = client.load_prompt("propose")
    system_blocks = [
        system_text,
        f"<typologies>\n{_typology_menu(typologies)}\n</typologies>",
        f"<tests>\n{client.load_reference('tests')}\n</tests>",
    ]
    tip_text = tip.text if isinstance(tip, Tip) else str(tip)
    vendor_rows = []
    for v in vendors:
        agg = dict(per_vendor.get(v.vendor_id, {}))
        row = {
            "id": v.vendor_id,
            "name_norm": v.name_norm,
            "created_on": v.created_on,
            "address_type": v.address_type,
            "city": v.city,
            "spend_inr": _first(agg, "spend", "spend_inr", "total"),
            "invoice_count": _first(agg, "invoices", "invoice_count", "count", "n"),
        }
        row.update(agg)  # remaining per-vendor metrics, e.g. approvers, round_amount_share
        vendor_rows.append(row)
    known = {v.vendor_id for v in vendors}
    unlinked = {k: v for k, v in per_vendor.items() if k not in known}
    if unlinked:
        stats["unlinked_vendor_keys"] = unlinked
    staff_rows = [
        {
            "id": s.staff_id,
            "name_norm": s.name_norm,
            "title": s.title,
            "department": s.department,
            "approval_limit_inr": s.approval_limit,
        }
        for s in staff
    ]
    stats_json = json.dumps(jsonable(stats), indent=1, ensure_ascii=False)
    user = (
        f"<tip>\n{tip_text.strip()}\n</tip>\n\n"
        f"<ledger_stats>\n{stats_json}\n</ledger_stats>\n\n"
        f"<vendors>\n{_jsonl(vendor_rows)}\n</vendors>\n\n"
        f"<staff>\n{_jsonl(staff_rows)}\n</staff>\n\n"
        f"{instructions}"
    )
    return system_blocks, [{"role": "user", "content": user}]


def _validator(vendor_ids: set[str], staff_ids: set[str], typologies: set[str], test_ids: set[str]):
    def validate(out: ProposeOutput) -> None:
        errors = []
        n = len(out.hypotheses)
        if not MIN_HYPOTHESES <= n <= MAX_HYPOTHESES:
            errors.append(f"expected {MIN_HYPOTHESES}-{MAX_HYPOTHESES} hypotheses, got {n}")
        for i, h in enumerate(out.hypotheses, 1):
            if typologies and str(h.typology) not in typologies:
                errors.append(f"hypothesis {i}: typology {h.typology} not in menu")
            if not h.tests_to_run:
                errors.append(f"hypothesis {i}: tests_to_run is empty")
            bad_tests = [t for t in h.tests_to_run if t not in test_ids]
            if bad_tests:
                errors.append(f"hypothesis {i}: unknown test ids {bad_tests}")
            bad_s = [s for s in h.subjects if s not in staff_ids]
            if bad_s:
                errors.append(f"hypothesis {i}: unknown staff ids {bad_s}")
            bad_o = [o for o in h.objects if o not in vendor_ids]
            if bad_o:
                errors.append(f"hypothesis {i}: unknown vendor ids {bad_o}")
            if not h.subjects and not h.objects:
                errors.append(f"hypothesis {i}: names neither a staff id nor a vendor id")
            if len(set(h.subjects)) > MAX_SUBJECTS or len(set(h.objects)) > MAX_OBJECTS:
                errors.append(
                    f"hypothesis {i}: at most {MAX_SUBJECTS} staff ids and {MAX_OBJECTS} vendor "
                    "ids; split it into one hypothesis per staff-vendor pair"
                )
        if out.hypotheses and not any(h.alternative_to_tip for h in out.hypotheses):
            errors.append(
                "no hypothesis has alternative_to_tip=true; add one whose support would refute "
                "the tip's reading (a different subject, or an innocent explanation)"
            )
        if errors:
            raise ValueError("; ".join(errors))

    return validate


def propose(
    tip: Tip | str,
    ledger_stats: dict[str, Any],
    vendors: Sequence[VendorRecord],
    staff: Sequence[StaffRecord],
    typologies: Sequence[str] | None = None,
    *,
    audit: AuditSink | None = None,
) -> list[Hypothesis]:
    typologies = list(typologies) if typologies else [t.value for t in Typology]
    system_blocks, messages = build_request(tip, ledger_stats, vendors, staff, typologies)
    validate = _validator(
        {v.vendor_id for v in vendors},
        {s.staff_id for s in staff},
        {str(t) for t in typologies},
        set(registry_test_ids()),
    )
    result = client.call(
        "propose",
        system_blocks,
        messages,
        model=client.MODEL_STRONG,
        output_schema=ProposeOutput,
        validate=validate,
        temperature=0.3,
        effort="low",  # 12 s vs 24 s at medium on the fixture, same coverage
        audit=audit,
    )
    out: ProposeOutput = result.output
    return [
        Hypothesis(
            hypothesis_id=f"H{i}",
            typology=h.typology,
            statement=h.statement.strip(),
            subjects=list(dict.fromkeys(h.subjects)),
            objects=list(dict.fromkeys(h.objects)),
            tests_to_run=list(dict.fromkeys(h.tests_to_run)),
            prior_score=h.prior_score,
            origin=h.origin,
            rationale=("Alternative to the tip. " if h.alternative_to_tip else "")
            + h.rationale.strip(),
        )
        for i, h in enumerate(out.hypotheses, 1)
    ]
