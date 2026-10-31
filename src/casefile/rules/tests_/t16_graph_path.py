"""T16 graph_path: shortest strong path (<= `graph_max_len` edges, approvals excluded) from each
approver, or hypothesis subject, to the vendor, via shared attributes or Crustdata ids. The
pipeline also calls `graph.path_evidence` per hypothesis pair; this screens ledger pairs."""

from __future__ import annotations

from casefile.rules.context import RuleContext
from casefile.schemas import EvidenceObject


def run(ctx: RuleContext) -> list[EvidenceObject]:
    from casefile import graph  # lazy: graph imports rules.normalize

    G = ctx.graph
    if G is None:
        G = graph.build(
            list(ctx.ledger.values()), list(ctx.vendors.values()), list(ctx.staff.values())
        )
    df = ctx.rows[ctx.rows.vendor_id.notna() & ctx.rows.approver_id.notna()]
    pairs = set(zip(df.approver_id, df.vendor_id, strict=True))
    for h in ctx.hypotheses:
        pairs |= {(s, v) for s in h.subjects for v in h.objects}
    out: list[EvidenceObject] = []
    for sid, vid in sorted(pairs):
        e = graph.path_evidence(G, sid, vid, max_len=ctx.th("graph_max_len"))
        if e is not None:
            out.append(e)
    return out
