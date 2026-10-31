"""T16 graph_path: strongest path (<= `graph_max_len` edges, approvals excluded) from each approver
to each vendor it approved, via shared attributes or Crustdata ids.

The pipeline calls `graph.path_evidence` itself for every hypothesis subject-object pair, so when
the context carries hypotheses those pairs are left to it here (one exhibit per pair, not two)."""

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
        pairs -= {(s, v) for s in h.subjects for v in h.objects}
    out: list[EvidenceObject] = []
    for sid, vid in sorted(pairs):
        e = graph.path_evidence(G, sid, vid, max_len=ctx.th("graph_max_len"))
        if e is not None:
            out.append(e)
    return out
