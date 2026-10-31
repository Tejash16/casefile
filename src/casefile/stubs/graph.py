"""Stub for casefile.graph (b3): approval edges only, no path evidence."""

from __future__ import annotations

import networkx as nx

from casefile.schemas import EvidenceObject, LedgerRow, StaffRecord, VendorRecord


def build(rows: list[LedgerRow], vendors: list[VendorRecord], staff: list[StaffRecord]) -> nx.Graph:
    G = nx.Graph()
    for r in rows:
        if r.approver_id and r.vendor_id:
            G.add_edge(f"staff:{r.approver_id}", f"vendor:{r.vendor_id}", reason="approved")
    return G


def path_evidence(G: nx.Graph, staff_id: str, vendor_id: str, max_len: int = 3) -> EvidenceObject | None:
    return None


def centrality(G: nx.Graph) -> dict[str, float]:
    return {}
