"""NetworkX graph of staff, vendors, shared identifiers and Crustdata ids (b3).

Nodes: `staff:S004`, `vendor:V017`, `addr:<norm>`, `phone:<norm>`, `bank:<norm>`,
`taxid:<norm>`, `email:<norm>`, `cdco:<crustdata_company_id>`, `cdperson:<crustdata_person_id>`,
`person:<linkedin profile>` (or `person:name:<norm>` for founders without one).

Edges carry `kind` (approval, address, phone, bank, taxid, email, resolution, employment,
founder, profile) and `reason`, a literal statement of the fields that make the link. Approval
edges carry `weight` = number of approved invoices. Fuzzy-equal addresses (token set ratio >=
`fuzzy_identifier_min`) share one `addr:` node, flagged `coworking` when any of them is.
"""

from __future__ import annotations

from collections import Counter

import networkx as nx

from casefile.rules import normalize as norm
from casefile.rules.config import THRESHOLDS
from casefile.rules.match import address_score, employment_at_vendor, staff_profile
from casefile.schemas import LedgerRow, StaffRecord, VendorRecord


def _address_clusters(entries: list[tuple[str, str]], fuzzy_min: int, min_tokens: int) -> dict:
    """norm address -> canonical norm address (first in sorted order of its cluster)."""
    addrs = sorted({a for _, a in entries})
    parent = {a: a for a in addrs}

    def find(a: str) -> str:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for i, a in enumerate(addrs):
        if len(a.split()) < min_tokens:
            continue
        for b in addrs[i + 1 :]:
            if address_score(a, b, fuzzy_min, min_tokens) is not None:
                ra, rb = find(a), find(b)
                if ra != rb:
                    parent[max(ra, rb)] = min(ra, rb)
    return {a: find(a) for a in addrs}


def build(rows: list[LedgerRow], vendors: list[VendorRecord], staff: list[StaffRecord]) -> nx.Graph:
    fuzzy_min = THRESHOLDS["fuzzy_identifier_min"].value
    min_tokens = THRESHOLDS["address_min_tokens"].value
    G = nx.Graph()
    for v in vendors:
        G.add_node(f"vendor:{v.vendor_id}", kind="vendor", label=v.name_raw)
    for s in staff:
        G.add_node(f"staff:{s.staff_id}", kind="staff", label=s.name_raw)

    # approvals
    counts = Counter((r.approver_id, r.vendor_id) for r in rows if r.approver_id and r.vendor_id)
    for (sid, vid), n in sorted(counts.items()):
        G.add_edge(
            f"staff:{sid}",
            f"vendor:{vid}",
            kind="approval",
            weight=n,
            reason=f"{sid} approved {n} invoices of {vid}",
        )

    # shared identifiers
    parties = [("vendor", v.vendor_id, v) for v in vendors] + [
        ("staff", s.staff_id, s) for s in staff
    ]
    addr_entries = [
        (f"{k}:{i}", a) for k, i, rec in parties if (a := norm.address(rec.address)) is not None
    ]
    canon = _address_clusters(addr_entries, fuzzy_min, min_tokens)
    for kind, pid, rec in parties:
        node = f"{kind}:{pid}"
        idents = {
            "phone": norm.phone(rec.phone),
            "bank": norm.bank_account(rec.bank_account),
            "taxid": norm.tax_id(getattr(rec, "tax_id", None)),
            "email": norm.email(rec.email),
        }
        raw = {
            "phone": rec.phone,
            "bank": rec.bank_account,
            "taxid": getattr(rec, "tax_id", None),
            "email": rec.email,
        }
        for attr, value in idents.items():
            if value:
                G.add_node(f"{attr}:{value}", kind=attr)
                G.add_edge(
                    node, f"{attr}:{value}", kind=attr, reason=f'{node} {attr} "{raw[attr]}"'
                )
        a = norm.address(rec.address)
        if a is not None:
            anode = f"addr:{canon[a]}"
            cow = (
                norm.is_coworking(rec.address) or getattr(rec, "address_type", None) == "coworking"
            )
            if anode in G:
                G.nodes[anode]["coworking"] = G.nodes[anode].get("coworking", False) or cow
            else:
                G.add_node(anode, kind="address", coworking=cow)
            G.add_edge(node, anode, kind="address", reason=f'{node} address "{rec.address}"')

    # Crustdata: vendor -> company, staff -> person -> employers, company -> founders
    cdco_of: dict[str, str] = {}
    for v in vendors:
        if v.crustdata is not None:
            cd = v.crustdata
            co = f"cdco:{cd.crustdata_company_id}"
            cdco_of[v.vendor_id] = co
            G.add_node(co, kind="cdco", label=cd.name)
            G.add_edge(f"vendor:{v.vendor_id}", co, kind="resolution", reason=f"{cd.citation}")
            for role, people in (("founder", cd.founders), ("decision_maker", cd.decision_makers)):
                for p in people:
                    url = norm.profile_url(p.linkedin_url)
                    pnode = f"person:{url}" if url else f"person:name:{norm.person_name(p.name)}"
                    G.add_node(pnode, kind="person", label=p.name)
                    G.add_edge(
                        co,
                        pnode,
                        kind="founder",
                        reason=f'{cd.citation} {role} "{p.name}", {p.title or "title unknown"}',
                    )
    for s in staff:
        snode = f"staff:{s.staff_id}"
        url = staff_profile(s)
        if url:
            G.add_node(f"person:{url}", kind="person", label=s.name_raw)
            G.add_edge(snode, f"person:{url}", kind="profile", reason=f"{snode} profile {url}")
        p = s.crustdata
        if p is None:
            continue
        pnode = f"cdperson:{p.crustdata_person_id}"
        G.add_node(pnode, kind="cdperson", label=p.name)
        G.add_edge(snode, pnode, kind="resolution", reason=p.citation)
        for i, e in enumerate(p.employment):
            targets = (
                {f"cdco:{e.crustdata_company_id}"}
                if e.crustdata_company_id
                else {
                    cdco_of.get(v.vendor_id) or f"vendor:{v.vendor_id}"
                    for v in vendors
                    if employment_at_vendor(e, v, fuzzy_min)
                }
            )
            end = (
                "present" if e.is_current else (e.end_date.isoformat() if e.end_date else "unknown")
            )
            start = e.start_date.isoformat() if e.start_date else "unknown"
            for t in sorted(targets):
                G.add_node(t, kind=G.nodes[t].get("kind", "cdco") if t in G else "cdco")
                G.add_edge(
                    pnode,
                    t,
                    kind="employment",
                    reason=f"{p.citation} employment[{i}]: {e.company_name}, "
                    f"{e.title or 'title unknown'}, {start} to {end}",
                )
    return G
