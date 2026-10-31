"""Robust CSV reading: encoding and delimiter sniffing, header normalisation, junk-row removal.

Nothing is fixed silently: every decision lands in the returned notes as a human sentence.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from pathlib import Path

from charset_normalizer import from_bytes

# Header synonyms per table: normalised header -> canonical field name
LEDGER_SYNONYMS: dict[str, str] = {
    **dict.fromkeys(
        [
            "date",
            "txn_date",
            "transaction_date",
            "invoice_date",
            "posting_date",
            "doc_date",
            "value_date",
            "bill_date",
        ],
        "date",
    ),
    **dict.fromkeys(
        [
            "vendor",
            "supplier",
            "payee",
            "vendor_name",
            "supplier_name",
            "payee_name",
            "party",
            "party_name",
            "vendor_name_raw",
        ],
        "vendor_name_raw",
    ),
    **dict.fromkeys(
        [
            "invoice_no",
            "invoice",
            "invoice_number",
            "inv_no",
            "bill_no",
            "invoice_ref",
            "invoice_id",
            "voucher_no",
        ],
        "invoice_no",
    ),
    **dict.fromkeys(
        [
            "amount",
            "amt",
            "amount_inr",
            "value",
            "net_amount",
            "invoice_amount",
            "amount_rs",
            "gross_amount",
            "amount_in_inr",
        ],
        "amount",
    ),
    **dict.fromkeys(
        [
            "approved_by",
            "approver",
            "approver_name",
            "authorised_by",
            "authorized_by",
            "approver_name_raw",
        ],
        "approver_name_raw",
    ),
    **dict.fromkeys(["created_by", "entered_by", "posted_by", "user", "user_id"], "created_by"),
    **dict.fromkeys(
        ["posted_at", "posting_time", "entry_time", "posted_on", "timestamp", "entry_timestamp"],
        "posted_at",
    ),
    **dict.fromkeys(["description", "narration", "particulars", "remarks", "memo"], "description"),
    **dict.fromkeys(["po_number", "po_no", "po", "purchase_order"], "po_number"),
    **dict.fromkeys(
        ["bank_account", "bank_ac", "bank_a_c", "account_no", "beneficiary_account"],
        "bank_account",
    ),
    **dict.fromkeys(["currency", "ccy", "curr"], "currency"),
}

VENDOR_SYNONYMS: dict[str, str] = {
    **dict.fromkeys(
        ["vendor_code", "vendor_id", "vendor_no", "supplier_code", "supplier_id"], "vendor_id"
    ),
    **dict.fromkeys(
        ["vendor_name", "name", "supplier_name", "vendor", "supplier", "name_raw"], "name_raw"
    ),
    **dict.fromkeys(["address", "registered_address", "addr"], "address"),
    "city": "city",
    "state": "state",
    "country": "country",
    **dict.fromkeys(["phone", "mobile", "contact", "telephone", "phone_no", "contact_no"], "phone"),
    **dict.fromkeys(["email", "e_mail", "email_id"], "email"),
    **dict.fromkeys(["website", "url", "web", "domain"], "website"),
    **dict.fromkeys(["gstin", "gst", "gst_no", "pan", "tax_id", "gstin_pan"], "tax_id"),
    **dict.fromkeys(["bank_account", "bank_ac", "bank_a_c", "account_no"], "bank_account"),
    **dict.fromkeys(["created_on", "created", "creation_date", "date_created"], "created_on"),
    "created_by": "created_by",
}

STAFF_SYNONYMS: dict[str, str] = {
    **dict.fromkeys(["emp_id", "employee_id", "staff_id", "emp_code", "employee_code"], "staff_id"),
    **dict.fromkeys(["full_name", "name", "employee_name", "staff_name", "name_raw"], "name_raw"),
    **dict.fromkeys(["designation", "title", "role", "job_title"], "title"),
    **dict.fromkeys(["department", "dept", "function"], "department"),
    **dict.fromkeys(["address", "home_address", "residential_address"], "address"),
    **dict.fromkeys(["mobile", "phone", "phone_no", "contact", "mobile_no"], "phone"),
    **dict.fromkeys(["email", "e_mail", "email_id"], "email"),
    **dict.fromkeys(
        ["bank_account", "bank_ac", "bank_a_c", "account_no", "salary_account"], "bank_account"
    ),
    **dict.fromkeys(
        ["date_of_joining", "doj", "joined_on", "joining_date", "join_date"], "joined_on"
    ),
    **dict.fromkeys(
        ["approval_limit", "limit", "approval_limit_inr", "authority_limit"], "approval_limit"
    ),
    **dict.fromkeys(
        ["linkedin", "linkedin_url", "profile_url", "linkedin_profile"], "linkedin_url"
    ),
}


@dataclass
class Table:
    """A parsed CSV: canonical column names and rows as {canonical: raw string}."""

    name: str
    columns: list[str]
    rows: list[dict[str, str]] = field(default_factory=list)
    line_numbers: list[int] = field(default_factory=list)  # 1-based physical line of each row
    notes: list[str] = field(default_factory=list)


def snake(header: str) -> str:
    """`Amount INR ` -> `amount_inr`; `Bank A/c` -> `bank_a_c`."""
    s = re.sub(r"[^0-9a-z]+", "_", header.strip().lower())
    return s.strip("_")


def decode(data: bytes, name: str) -> tuple[str, list[str]]:
    """Bytes to text. UTF-8 first (BOM stripped and noted), else charset_normalizer's guess."""
    notes: list[str] = []
    if data.startswith(b"\xef\xbb\xbf"):
        notes.append(f"{name}: UTF-8 byte-order mark removed.")
        data = data[3:]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        best = from_bytes(data).best()
        enc = best.encoding if best else "latin-1"
        text = data.decode(enc, errors="replace")
        notes.append(f"{name}: not valid UTF-8; decoded as {enc}.")
    if "\r\n" in text:
        notes.append(f"{name}: Windows (CRLF) line endings.")
    return text, notes


def sniff_delimiter(text: str) -> str:
    sample = "\n".join(text.splitlines()[:20])
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        return ","


def read_table(path: str | Path, synonyms: dict[str, str]) -> Table:
    """Read one CSV into a Table with canonical columns; junk rows dropped and noted."""
    p = Path(path)
    name = p.name
    text, notes = decode(p.read_bytes(), name)
    delim = sniff_delimiter(text)
    if delim != ",":
        notes.append(f"{name}: delimiter detected as {delim!r}.")
    records = list(csv.reader(io.StringIO(text, newline=""), delimiter=delim))
    # first non-blank record is the header
    start = next((i for i, r in enumerate(records) if any(c.strip() for c in r)), None)
    if start is None:
        return Table(name=name, columns=[], notes=[*notes, f"{name}: file is empty."])
    raw_header = records[start]
    columns: list[str] = []
    for h in raw_header:
        if h != h.strip():
            notes.append(f"{name}: column {h!r} had surrounding whitespace; trimmed.")
        key = snake(h)
        canon = synonyms.get(key)
        if canon is None:
            notes.append(f"{name}: column {h!r} not recognised; ignored.")
            canon = f"_x_{key}"
        elif canon in columns:
            notes.append(f"{name}: second column mapping to {canon!r} ({h!r}) ignored.")
            canon = f"_x_{key}"
        columns.append(canon)
    renamed = [
        f"{h.strip()!r} -> {c}"
        for h, c in zip(raw_header, columns, strict=True)
        if h.strip() != c and not c.startswith("_x_")
    ]
    if renamed:
        notes.append(f"{name}: columns mapped to the contract: {', '.join(renamed)}.")
    header_key = [snake(h) for h in raw_header]

    table = Table(name=name, columns=columns, notes=notes)
    blank, repeated, ragged = [], [], []
    for i, rec in enumerate(records[start + 1 :], start=start + 2):
        if not any(c.strip() for c in rec):
            blank.append(i)
            continue
        if [snake(c) for c in rec] == header_key:
            repeated.append(i)
            continue
        if len(rec) != len(columns):
            ragged.append(i)
            rec = (rec + [""] * len(columns))[: len(columns)]
        table.rows.append(dict(zip(columns, rec, strict=True)))
        table.line_numbers.append(i)
    if blank:
        notes.append(f"{name}: {len(blank)} blank row(s) dropped (line {_lines(blank)}).")
    if repeated:
        notes.append(
            f"{name}: {len(repeated)} repeated header row(s) dropped (line {_lines(repeated)})."
        )
    if ragged:
        notes.append(
            f"{name}: {len(ragged)} row(s) with the wrong number of cells padded or cut "
            f"(line {_lines(ragged)})."
        )
    return table


def _lines(nums: list[int], limit: int = 10) -> str:
    shown = ", ".join(str(n) for n in nums[:limit])
    return shown + (f" and {len(nums) - limit} more" if len(nums) > limit else "")
