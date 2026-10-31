"""Named thresholds and the evidence-strength scale for every rule test (b3).

THRESHOLDS print in the case file under "Assumptions"; each carries a rationale and the source
it rests on (docs/research-brief.md). No rule test may use a literal number: read it from here.
STRENGTH is the documented 0..1 scale each test assigns to its evidence objects. The gate
(docs/contract.md section 7) treats >= 0.6 as allegation-grade support and >= 0.7 as a refutation
that blocks Substantiated, so the scale below is set against those two lines.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DILIGENT = "https://www.diligent.com/insights/fraud/identify-accounts-payable-fraud"
TULSA = "https://www.cityoftulsa.org/media/2452/2015-vendortoemployeereport.pdf"
WELLS = (
    "https://www.journalofaccountancy.com/issues/2002/jul/"
    "billingschemespart1shellcompaniesthatdontdeliver/"
)
MN_AUDITOR = (
    "https://www.osa.state.mn.us/audit-resources/audit-guidance/avoiding-pitfalls-articles/"
    "phantom-vendors"
)
VONA = (
    "https://na.eventscloud.com/file_uploads/"
    "3cb0d524fa84069d7f653991827b937c_Tuesday_4_Vona_02_Handout.pdf"
)
IDEA = "https://www.ideascripting.com/Same-Same-Different-Test"
AZ_AUDITOR = "https://www.azauditor.gov/sites/default/files/2023-11/18-406.pdf"
SEQUENCE = "https://www.sequenceinc.com/fraudfiles/detecting-billing-schemes"
JOFA_BENFORD = "https://www.journalofaccountancy.com/issues/1998/nov/audit-nov-1998/"
SUH_BENFORD = "https://core.ac.uk/download/67751317.pdf"
DELOITTE = (
    "https://www2.deloitte.com/content/dam/Deloitte/sg/Documents/risk/"
    "sea-risk-sap-governance-risk-compliance-red-flag-brochure.pdf"
)
WEAVER = (
    "https://info.weaver.com/hubfs/3E.%20Leveraging%20Data%20Monitoring%20and%20Analytics"
    "%20for%20Fraud%20Detection%20%20Prevention_EL%20Edits%200907.pdf"
)
CASE_IQ = (
    "https://pages.caseiq.com/rs/219-YZJ-775/images/"
    "16-ways-to-identify-fictitious-vendors-version-2.pdf?version=0"
)
FINCEN = "https://www.fincen.gov/system/files/2026-05/FinCEN-Alert-IRGC.pdf"
CRUSTDATA_IDENTIFY = "https://docs.crustdata.com/company-docs/identify/introduction.md"
ACFE_NEXUS = (
    "https://acfeinsights.squarespace.com/acfe-insights/2022/12/22/"
    "case-study-the-employee-and-vendor-nexus"
)
NETWORK = "https://arxiv.org/abs/2512.19491"


@dataclass(frozen=True)
class Threshold:
    name: str
    value: Any
    unit: str
    rationale: str
    source_url: str

    def __str__(self) -> str:
        return f"{self.value} {self.unit}".strip()


_ALL = [
    Threshold(
        "new_vendor_days",
        90,
        "days",
        "Vendor created or founded within this many days of its first invoice (T03).",
        VONA,
    ),
    Threshold(
        "threshold_band_pct",
        5,
        "% under limit",
        "Invoices in this band just under the approver's limit look sized to avoid review (T05).",
        DILIGENT,
    ),
    Threshold(
        "band_ratio_min",
        2.0,
        "x population",
        "A vendor's in-band share must exceed the population's by this factor to support (T05).",
        DILIGENT,
    ),
    Threshold(
        "split_window_days",
        14,
        "days",
        "Invoices each under the limit whose sum crosses it within this window are splits (T05).",
        WELLS,
    ),
    Threshold(
        "round_unit_inr",
        1000,
        "INR",
        "An amount divisible by this is round (ends in 000) (T06).",
        AZ_AUDITOR,
    ),
    Threshold(
        "round_ratio_min",
        2.0,
        "x population",
        "A vendor's round-amount share must exceed the population's by this factor (T06).",
        AZ_AUDITOR,
    ),
    Threshold(
        "pattern_min_invoices",
        3,
        "invoices",
        "Vendor-level pattern tests (T04-T07, T09) need at least this many invoices.",
        SEQUENCE,
    ),
    Threshold(
        "pattern_min_hits",
        2,
        "invoices",
        "A vendor-level pattern (band, round, off-hours) needs at least this many hits "
        "(T05, T06, T09).",
        SEQUENCE,
    ),
    Threshold(
        "band_majority_share",
        0.5,
        "share of invoices",
        "Above this share of a vendor's invoices in the band, T05 rates the pattern stronger.",
        DILIGENT,
    ),
    Threshold(
        "velocity_min_vendors",
        3,
        "vendors",
        "Share and growth z-scores need at least this many paid vendors (T12).",
        WEAVER,
    ),
    Threshold(
        "benford_full_z_mult",
        2.0,
        "x benford_z",
        "A spike reaches the Benford strength cap at this multiple of benford_z (T08).",
        JOFA_BENFORD,
    ),
    Threshold(
        "duplicate_window_days",
        30,
        "days",
        "Same vendor and amount within this window is a possible duplicate payment (T04).",
        DILIGENT,
    ),
    Threshold(
        "sequential_min_invoices",
        5,
        "invoices",
        "T07 needs this many numbered invoices: three in a row from a small supplier is normal.",
        SEQUENCE,
    ),
    Threshold(
        "sequential_step_max",
        1.5,
        "invoice numbers per invoice",
        "Mean step between a vendor's invoice numbers at or below this: we are its only "
        "customer (T07).",
        SEQUENCE,
    ),
    Threshold(
        "sequential_spread_min",
        25.0,
        "invoice numbers per invoice",
        "Mean step at or above this: the vendor bills many customers (T07 refutes).",
        SEQUENCE,
    ),
    Threshold(
        "fuzzy_identifier_min",
        92,
        "RapidFuzz score",
        "Address and person-name matches at or above this score count as the same (T01, T15, T17).",
        TULSA,
    ),
    Threshold(
        "address_min_tokens",
        4,
        "tokens",
        "Both addresses need this many tokens before a fuzzy match counts, so a bare city "
        "name never matches a full address (T01).",
        TULSA,
    ),
    Threshold(
        "lookalike_name_min",
        90,
        "RapidFuzz score",
        "Vendor names this close under different vendor ids are look-alikes (T14).",
        CASE_IQ,
    ),
    Threshold(
        "coworking_markers",
        [
            "regus",
            "wework",
            "awfis",
            "91springboard",
            "virtual office",
            "business centre",
            "business center",
        ],
        "address terms",
        "An address containing one of these is a coworking address: shared by unrelated "
        "tenants, so an address match there is neutral unless phone, bank or tax id also "
        "match (T01), and it is not a thin-footprint signal by itself (T02).",
        FINCEN,
    ),
    Threshold(
        "personal_email_providers",
        ["gmail", "yahoo", "ymail", "hotmail", "outlook", "rediffmail", "protonmail"],
        "mail providers (first domain label)",
        "A vendor using a personal mailbox has a thin footprint (T02).",
        MN_AUDITOR,
    ),
    Threshold(
        "shell_headcount_max",
        2,
        "employees",
        "Crustdata headcount at or below this is consistent with a shell (T13).",
        FINCEN,
    ),
    Threshold(
        "established_headcount_min",
        50,
        "employees",
        "Crustdata headcount at or above this, with a website, refutes a shell (T13).",
        VONA,
    ),
    Threshold(
        "volume_per_head_max_inr",
        5_000_000,
        "INR billed per employee",
        "Billed volume per Crustdata employee above this exceeds the vendor's capacity (T13).",
        VONA,
    ),
    Threshold(
        "career_gap_days",
        365,
        "days",
        "Employment at the vendor ending within this many days before the first payment "
        "counts as a career link (T15).",
        ACFE_NEXUS,
    ),
    Threshold(
        "velocity_z",
        2.0,
        "z-score",
        "Vendor spend share or growth this many standard deviations above other vendors (T12).",
        WEAVER,
    ),
    Threshold(
        "velocity_sd_floor",
        0.25,
        "x mean share; absolute on the -1..1 growth index",
        "z-scores use at least this standard deviation, so near-equal vendors never look like "
        "outliers (T12).",
        WEAVER,
    ),
    Threshold(
        "velocity_normal_z",
        1.0,
        "z-score",
        "Share and growth both below this: spend pattern is normal (T12 refutes).",
        WEAVER,
    ),
    Threshold(
        "benford_min_n",
        1000,
        "rows",
        "Benford first-two-digit test runs only on a population at least this large (T08).",
        SUH_BENFORD,
    ),
    Threshold(
        "benford_z",
        1.96,
        "z-score",
        "A first-two-digit bucket this far above Benford's expectation is a spike (T08).",
        JOFA_BENFORD,
    ),
    Threshold(
        "off_hours",
        (22, 6),
        "hours (start, end)",
        "Postings between these local hours, on weekends or on national holidays are "
        "off-hours (T09).",
        AZ_AUDITOR,
    ),
    Threshold(
        "off_hours_ratio_min",
        2.0,
        "x population",
        "A vendor's off-hours share must exceed the population's by this factor (T09).",
        AZ_AUDITOR,
    ),
    Threshold(
        "holidays_mm_dd",
        ["01-26", "08-15", "10-02"],
        "dates",
        "Indian national holidays treated as off-hours (T09).",
        AZ_AUDITOR,
    ),
    Threshold(
        "dormant_days",
        365,
        "days",
        "A payment after this many idle days is a reactivated dormant vendor (T10).",
        VONA,
    ),
    Threshold(
        "identify_accept",
        0.85,
        "confidence",
        "Crustdata resolutions at or above this confidence are trusted enough to refute (T15).",
        CRUSTDATA_IDENTIFY,
    ),
    Threshold(
        "graph_max_len",
        3,
        "edges",
        "Longest staff-to-vendor path through shared attributes or Crustdata ids (T16).",
        NETWORK,
    ),
    Threshold(
        "quote_max_rows",
        25,
        "rows",
        "Longest list of ledger rows quoted in one exhibit; the payload keeps every row.",
        DILIGENT,
    ),
]

THRESHOLDS: dict[str, Threshold] = {t.name: t for t in _ALL}


# Evidence strength scale (0..1). Gate lines: support >= 0.6 counts, refute >= 0.7 blocks.
STRENGTH: dict[str, float] = {
    # T01 identifier match, by matched attribute
    "t01_bank": 0.9,
    "t01_tax_id": 0.9,
    "t01_phone": 0.8,
    "t01_email": 0.8,
    "t01_address": 0.7,
    "t01_extra_match": 0.05,  # added per further matched attribute
    "t01_cap": 0.95,
    "t01_coworking": 0.2,  # neutral
    # T02 thin footprint
    "t02_address": 0.6,
    "t02_no_contact": 0.6,
    "t02_personal_email": 0.5,
    "t02_extra_signal": 0.1,
    "t02_cap": 0.85,
    "t02_coworking": 0.1,  # neutral note
    # T03 vendor age
    "t03_new": 0.6,
    "t03_both": 0.7,
    "t03_paid_before_founded": 0.7,
    # T04 duplicates
    "t04_same_invoice_no": 0.9,
    "t04_same_same_different": 0.8,
    "t04_same_amount_window": 0.6,
    "t04_refute": 0.7,
    # T05 threshold structuring
    "t05_band": 0.7,
    "t05_band_majority": 0.8,
    "t05_split": 0.75,
    "t05_refute": 0.7,
    # T06 round amounts
    "t06_round": 0.6,
    "t06_round_many": 0.7,
    "t06_refute": 0.7,
    # T07 sequential invoice numbers
    "t07_narrow": 0.6,
    "t07_gap_free": 0.7,
    "t07_refute": 0.5,
    # T08 Benford (lead, not proof)
    "t08_cap": 0.4,
    "t08_note": 0.0,
    # T09 off-hours
    "t09_off_hours": 0.6,
    # T10 dormant
    "t10_dormant": 0.6,
    # T11 segregation of duties
    "t11_same_user": 0.7,  # created the vendor and approved its invoices
    "t11_posted_only": 0.5,  # created it and posted, an independent approver still signed
    # T12 velocity and share
    "t12_share": 0.5,  # biggest supplier by share is a lead without a category field
    "t12_growth": 0.6,
    "t12_refute": 0.5,
    # T13 existence and capacity
    "t13_unresolved": 0.5,
    "t13_thin": 0.7,
    "t13_volume": 0.6,
    "t13_refute": 0.8,
    # T14 look-alike names
    "t14_lookalike": 0.6,
    "t14_same_tax_id": 0.8,
    # T15 career overlap
    "t15_overlap": 0.9,
    "t15_non_approver": 0.5,  # career link, but no spend control
    "t15_old_employment": 0.3,  # neutral
    "t15_unresolved": 0.0,  # neutral data-gap note
    "t15_refute": 0.75,
    "t15_refute_low_confidence": 0.5,
    # T16 graph path, by weakest edge on the path
    "t16_identifier": 0.8,
    "t16_career": 0.75,
    "t16_address": 0.6,
    "t16_coworking": 0.2,
    "t16_stale_career": 0.2,  # employment more than career_gap_days from the payments
    "t16_support_min": 0.5,
    # T17 founders
    "t17_same_profile": 0.9,
    "t17_name_only": 0.5,
    "t17_namesake": 0.2,  # neutral
}

# rules/rank.py: prior' = prior + support*(1-e^-S) - refute*(1-e^-R) + centrality*c/max(c)
RANK_WEIGHTS: dict[str, float] = {"support": 0.3, "refute": 0.2, "centrality": 0.1}
