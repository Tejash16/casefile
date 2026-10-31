"""Ingest (b1): messy CSVs in, contract models and data-quality notes out. Pure parsing, no I/O
beyond reading the input files, no network, no model calls."""

from casefile.ingest.link import link_ledger, link_notes
from casefile.ingest.load import load_ledger, load_staff, load_tip, load_vendors
from casefile.ingest.names import normalize_company_name, normalize_person_name
from casefile.ingest.stats import ledger_stats

__all__ = [
    "ledger_stats",
    "link_ledger",
    "link_notes",
    "load_ledger",
    "load_staff",
    "load_tip",
    "load_vendors",
    "normalize_company_name",
    "normalize_person_name",
]
