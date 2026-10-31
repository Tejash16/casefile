"""Path evidence (T16) and vendor centrality for ranking (b3)."""

from __future__ import annotations

from itertools import combinations

import networkx as nx

from casefile.rules import evidence as ev
from casefile.rules.config import STRENGTH
from casefile.schemas import Direction, EvidenceObject, SourceKind

TEST = "T16"
IDENTITY = {"resolution", "profile"}  # same entity, not a link: no strength penalty
EDGE_STRENGTH = {
    "phone": "t16_identifier",
    "bank": "t16_identifier",
    "taxid": "t16_identifier",
    "email": "t16_identifier",
    "employment": "t16_career",
    "founder": "t16_career",
    "address": "t16_address",
}


def _edge_strength(G: nx.Graph, a: str, b: str) -> float | None:
    data = G.edges[a, b]
    kind = data.get("kind")
    if kind in IDENTITY:
        return None
    if kind == "address":
        addr = a if a.startswith("addr:") else b
        if G.nodes[addr].get("coworking"):
            return STRENGTH["t16_coworking"]
    if kind == "employment" and not data.get("timing"):
        return STRENGTH["t16_stale_career"]  # job far from the payments (T15's rule)
    return STRENGTH.get(EDGE_STRENGTH.get(kind, ""), STRENGTH["t16_coworking"])


def _path_strength(G: nx.Graph, path: list[str]) -> float:
    vals = [s for a, b in zip(path, path[1:], strict=False) if (s := _edge_strength(G, a, b))]
    return min(vals) if vals else STRENGTH["t16_identifier"]


def _without_approvals(G: nx.Graph) -> nx.Graph:
    """G minus approval edges, cached on G (keyed by its size, so a changed graph rebuilds)."""
    key = (G.number_of_nodes(), G.number_of_edges())
    cached = G.graph.get("_no_approvals")
    if cached is None or cached[0] != key:
        H = nx.Graph()
        H.add_nodes_from(G.nodes)
        H.add_edges_from((a, b) for a, b, k in G.edges(data="kind") if k != "approval")
        G.graph["_no_approvals"] = cached = (key, H)
    return cached[1]


def path_evidence(
    G: nx.Graph, staff_id: str, vendor_id: str, max_len: int = 3
) -> EvidenceObject | None:
    """Strongest (then shortest) simple path of <= max_len edges from staff to vendor that does
    not use approval edges. None when there is none."""
    s, v = f"staff:{staff_id}", f"vendor:{vendor_id}"
    if s not in G or v not in G:
        return None
    H = _without_approvals(G)
    if not nx.has_path(H, s, v):
        return None
    best: tuple[float, int, list[str]] | None = None
    for path in nx.all_simple_paths(H, s, v, cutoff=max_len):
        key = (_path_strength(G, path), -len(path), path)
        if best is None or key[:2] > best[:2] or (key[:2] == best[:2] and path < best[2]):
            best = key
    if best is None:
        return None
    strength, _, path = best
    hops = []
    for a, b in zip(path, path[1:], strict=False):
        d = G.edges[a, b]
        hops.append(f"-[{d.get('kind')}: {d.get('reason', '')}]-")
    quote = path[0] + "".join(f" {h} {n}" for h, n in zip(hops, path[1:], strict=True))
    kinds = [G.edges[a, b].get("kind") for a, b in zip(path, path[1:], strict=False)]
    links = ", ".join(dict.fromkeys(k for k in kinds if k not in IDENTITY))
    support = strength >= STRENGTH["t16_support_min"]
    weak = [
        "a shared coworking address"
        if G.edges[a, b].get("kind") == "address"
        else "employment far from the payments"
        for a, b in zip(path, path[1:], strict=False)
        if (st := _edge_strength(G, a, b)) is not None and st < STRENGTH["t16_support_min"]
    ]
    summary = (
        f"Staff member {staff_id} is linked to vendor {vendor_id} in {len(path) - 1} steps "
        f"through {links or 'shared identity'}."
        if support
        else f"Staff member {staff_id} is linked to vendor {vendor_id} only through "
        + " and ".join(dict.fromkeys(weak))
        + "."
    )
    return ev.make(
        test_id=TEST,
        direction=Direction.supports if support else Direction.neutral,
        strength=strength,
        summary=summary,
        quote=quote,
        kind=SourceKind.graph,
        refs=path,
        records=[
            {"from": a, "to": b, **{k: v for k, v in G.edges[a, b].items()}}
            for a, b in zip(path, path[1:], strict=False)
        ],
        subject_ids=[staff_id],
        object_ids=[vendor_id],
    )


def vendor_projection(G: nx.Graph) -> nx.Graph:
    """Vendors joined when they share any neighbour (approver, identifier, Crustdata company)."""
    P = nx.Graph()
    P.add_nodes_from(n for n, d in G.nodes(data=True) if d.get("kind") == "vendor")
    for n in G.nodes:
        if G.nodes[n].get("kind") == "vendor":
            continue
        vs = sorted(m for m in G.neighbors(n) if G.nodes[m].get("kind") == "vendor")
        for a, b in combinations(vs, 2):
            w = P.edges[a, b]["weight"] + 1 if P.has_edge(a, b) else 1
            P.add_edge(a, b, weight=w)
    return P


def centrality(G: nx.Graph) -> dict[str, float]:
    """Eigenvector centrality of each vendor in the vendor projection, keyed by vendor id."""
    P = vendor_projection(G)
    if P.number_of_nodes() == 0:
        return {}
    if P.number_of_edges() == 0:
        scores = dict.fromkeys(P.nodes, 0.0)
    else:
        try:
            scores = nx.eigenvector_centrality(P, max_iter=1000, weight="weight")
        except nx.PowerIterationFailedConvergence:
            scores = nx.degree_centrality(P)
        scores |= {n: 0.0 for n in nx.isolates(P)}  # power iteration leaves residue on these
    return {n.removeprefix("vendor:"): round(float(c), 6) for n, c in sorted(scores.items())}
