"""Seeded planted-case generator (b1). Writes case directories per docs/contract.md section 8.

    uv run python cases/gen.py --all                         # the six named cases into cases/
    uv run python cases/gen.py --name heldout --seed <private> --plants career_overlap,false_lead,\
duplicate,shell --vendors 14 --rows 140 --shuffle-ids --out <dir outside the repo>

Real companies and people come from docs/dataset-design.md: every real vendor was checked with
Crustdata `POST /company/identify` on 31 Oct 2026, and every fictional name returned no match.
Never add a company name here without that check. No network, no model calls.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import random
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PERIOD = (date(2024, 4, 1), date(2026, 3, 31))
COMPANY = "Halvexa Precision Components Pvt Ltd"
SHELL_VERDICT = (
    "Substantiated"  # reachable since contract s7 rev (31 Oct): see docs/dataset-design.md
)
MANAGER_LIMIT = 500_000
BAND = Decimal("0.95")  # background amounts stay below 95% of the approver's limit

PLANTS = ("career_overlap", "shell", "false_lead", "duplicate", "shared_office")
SIX = {
    "career_overlap": ["career_overlap"],
    "shell_vendor": ["shell"],
    "false_lead": ["false_lead"],
    "duplicate_billing": ["duplicate"],
    "clean_controls": [],
    "shared_office_honest": ["shared_office"],
}
SEEDS = {name: 1000 + i for i, name in enumerate(SIX)}
# career_overlap runs to today so DocRack's billing (from March 2026, when S004's role there
# starts) has months to grow in; every other vendor keeps its cadence through the extra months.
PERIOD_END = {"career_overlap": date(2026, 10, 31)}


@dataclass
class Vendor:
    key: str
    vid: str
    name: str
    variants: list[str]
    website: str | None
    address: str
    city: str
    state: str
    country: str = "India"
    desc: str = ""
    lo: int = 0
    hi: int = 0
    prefix: str = "INV"
    created_on: date = date(2019, 4, 1)
    created_by: str = "mdm.admin"
    phone: str = ""
    email: str = ""
    bank: str = ""
    real: bool = True


@dataclass
class Staff:
    sid: str
    name: str
    title: str
    dept: str
    address: str
    phone: str
    email: str
    joined: date
    limit: int | None
    linkedin: str = ""
    orig: str = ""  # id before --shuffle-ids

    @property
    def user(self) -> str:
        return self.email.split("@")[0]


@dataclass
class Row:
    d: date
    vendor: Vendor
    vendor_raw: str
    invoice: str
    amount: Decimal
    approver: Staff | None
    approver_raw: str
    created_by: str
    posted: datetime
    desc: str
    po: str
    bank: str = ""


@dataclass
class Case:
    name: str
    seed: int
    rng: random.Random
    vendors: dict[str, Vendor] = field(default_factory=dict)
    staff: dict[str, Staff] = field(default_factory=dict)
    rows: list[Row] = field(default_factory=list)
    expected: list[dict] = field(default_factory=list)
    must_clear: list[str] = field(default_factory=list)
    tip: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    period: tuple[date, date] = PERIOD


# ---------------------------------------------------------------- pools (checked 31 Oct 2026)

# key: (vid, name, variants, website, address, city, state, country, desc, lo, hi, prefix)
REAL_VENDORS: dict[str, tuple] = {
    "tata_steel": (
        "V001",
        "Tata Steel Limited",
        ["TATA STEEL LTD", "Tata Steel Ltd."],
        "tatasteel.com",
        "Bombay House, 24 Homi Mody Street, Fort",
        "Mumbai",
        "Maharashtra",
        "India",
        "HR coil and bar stock",
        1_200_000,
        2_300_000,
        "TSL/",
    ),
    "bharat_forge": (
        "V002",
        "Bharat Forge Ltd",
        ["BHARAT FORGE LIMITED"],
        "bharatforge.com",
        "Mundhwa, Pune Cantonment",
        "Pune",
        "Maharashtra",
        "India",
        "Forged crankshaft blanks",
        600_000,
        940_000,
        "BFL-",
    ),
    "sundram": (
        "V003",
        "Sundram Fasteners Limited",
        ["Sundram Fasteners Ltd."],
        "sundram.com",
        "98-A, Dr. Radhakrishnan Salai, Mylapore",
        "Chennai",
        "Tamil Nadu",
        "India",
        "High-tensile bolts",
        250_000,
        420_000,
        "SFL/",
    ),
    "mahindra_logistics": (
        "V004",
        "Mahindra Logistics Ltd",
        ["MAHINDRA LOGISTICS LIMITED"],
        "mahindralogistics.com",
        "Mahindra Towers, P.K. Kurne Chowk, Worli",
        "Mumbai",
        "Maharashtra",
        "India",
        "Inbound freight",
        80_000,
        250_000,
        "MLL",
    ),
    "blue_dart": (
        "V005",
        "Blue Dart Express Ltd",
        ["BLUE DART EXPRESS LIMITED"],
        "bluedart.com",
        "Blue Dart Centre, Sahar Airport Road, Andheri East",
        "Mumbai",
        "Maharashtra",
        "India",
        "Courier",
        15_000,
        60_000,
        "BD",
    ),
    "pune_metrology": (
        "V006",
        "Pune Metrology",
        [],
        "punemetrology.in",
        "MIDC Bhosari",
        "Pune",
        "Maharashtra",
        "India",
        "CMM inspection",
        40_000,
        120_000,
        "PM/",
    ),
    "atomic_gauges": (
        "V007",
        "Atomic Gauges",
        ["ATOMIC GAUGES"],
        "atomicgauges.co.in",
        "",
        "",
        "",
        "India",
        "Plug and ring gauges",
        60_000,
        180_000,
        "AG-",
    ),
    "fox_tooling": (
        "V009",
        "Fox Precision Tooling",
        [],
        "foxprecisiontooling.co.uk",
        "",
        "",
        "",
        "United Kingdom",
        "Die-casting tooling",
        200_000,
        300_000,
        "FPT-",
    ),
    "forbes_marshall": (
        "V010",
        "Forbes Marshall Pvt Ltd",
        ["FORBES MARSHALL PRIVATE LIMITED"],
        "forbesmarshall.com",
        "Opp 106 Milestone, Bombay Pune Road, Kasarwadi",
        "Pune",
        "Maharashtra",
        "India",
        "Steam traps and instrumentation",
        90_000,
        450_000,
        "FM/",
    ),
    "praj": (
        "V011",
        "Praj Industries Ltd",
        ["PRAJ INDUSTRIES LIMITED"],
        "praj.net",
        "Praj Tower, 274-275 Bhumkar Chowk, Hinjewadi",
        "Pune",
        "Maharashtra",
        "India",
        "Effluent treatment plant AMC",
        150_000,
        460_000,
        "PIL/",
    ),
    "tcs": (
        "V012",
        "Tata Consultancy Services Limited",
        ["TATA CONSULTANCY SERVICES LTD"],
        "tcs.com",
        "TCS House, Raveline Street, Fort",
        "Mumbai",
        "Maharashtra",
        "India",
        "ERP licences and support",
        300_000,
        900_000,
        "TCS",
    ),
    "persistent": (
        "V013",
        "Persistent Systems Limited",
        ["PERSISTENT SYSTEMS LTD"],
        "persistent.com",
        "Bhageerath, 402 Senapati Bapat Road",
        "Pune",
        "Maharashtra",
        "India",
        "MES integration services",
        250_000,
        800_000,
        "PSL/",
    ),
}
CONTROLS = ["tata_steel", "bharat_forge"]
UNRESOLVED_NAMES = [
    "Zentravik Industrial Supplies Pvt Ltd",
    "Varnetta Industrial Traders",
    "Melkora Tool Supplies",
]
SHELL_NAMES = [
    "Brindora Engineering Traders Pvt Ltd",
    "Oskavi Engineering Works",
    "Quillmere Fabrication Supplies",
    "Drovanta Supplies",
]
# Real, unrelated companies at WeWork Futura, Magarpatta Road, Pune (Crustdata company search
# on locations.street_address, 31 Oct 2026): TechLadd 958646, E Giraffes Digital 615149.
SHARED_OFFICE = [
    (
        "V041",
        "TechLadd",
        ["TECHLADD"],
        "techladd.com",
        "Suite 03-112, WeWork Futura, Magarpatta Road, Kirtane Baugh, Hadapsar",
        "Shop-floor app development",
        150_000,
        400_000,
        "TL/",
    ),
    (
        "V042",
        "E Giraffes Digital Pvt Ltd",
        ["E GIRAFFES DIGITAL PRIVATE LIMITED"],
        "egiraffes.com",
        "01-145 We Work Futura, Magarpatta Rd, Hadapsar",
        "Digital marketing retainer",
        60_000,
        180_000,
        "EGD-",
    ),
]

# Fictional staff (two pools so the held-out case uses different names)
BASE_STAFF = [
    ("S001", "Meera Kulkarni", "Director - Finance", "Finance", "Baner, Pune", 2_500_000),
    ("S002", "Vikram Shah", "Senior Manager", "Operations", "Wakad, Pune", 1_000_000),
    (
        "S003",
        "Anil Deshpande",
        "Manager - Procurement",
        "Procurement",
        "Flat 7, Shivneri Apartments, Karve Road, Kothrud, Pune 411038",
        MANAGER_LIMIT,
    ),
    ("S004", "Rohan Joshi", "Manager - Procurement", "Procurement", "Aundh, Pune", MANAGER_LIMIT),
    ("S005", "Rahul Verma", "Analyst", "Finance", "Hadapsar, Pune", None),
    ("S006", "Sunita Patil", "AP Clerk", "Finance", "Pimpri, Pune", None),
    (
        "S007",
        "Farhan Qureshi",
        "Manager - Procurement",
        "Procurement",
        "Kharadi, Pune",
        MANAGER_LIMIT,
    ),
    ("S008", "Priya Nair", "Manager - Finance", "Finance", "Viman Nagar, Pune", MANAGER_LIMIT),
]
ALT_NAMES = [
    "Nandini Iyer",
    "Suresh Menon",
    "Prakash Gokhale",
    "Amit Bhosale",
    "Neha Kapoor",
    "Ganesh Pawar",
    "Imran Shaikh",
    "Deepa Rao",
]
ALT_HOME = "Flat 12, Gulmohar Residency, Paud Road, Kothrud, Pune 411038"

# Team members (consent): Crustdata persons 177265563 and 420958731
TEJASH = ("Tejash Chauhan", "https://www.linkedin.com/in/tejash-chauhan-5424a9252")
KEDAR = ("Kedar Sharma", "https://www.linkedin.com/in/kedar-sharma-67aa9b253/")


# ---------------------------------------------------------------- formatting (messiness)


def lakh(n: Decimal, paise: bool = False) -> str:
    whole = int(n)
    s = str(whole)
    if len(s) > 3:
        head, tail, parts = s[:-3], s[-3:], []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    return s + (f".{int((n - whole) * 100):02d}" if paise else "")


def fmt_amount(rng: random.Random, n: Decimal) -> str:
    return rng.choice([lakh(n), f"{n:.2f}", f"₹ {lakh(n, paise=True)}", f"Rs. {lakh(n)}"])


def fmt_date(rng: random.Random, d: date) -> str:
    return rng.choice([d.strftime("%d/%m/%Y"), d.isoformat(), d.strftime("%d-%b-%y")])


def typo(rng: random.Random, name: str) -> str:
    """Drop one interior letter from the longest word: Engineering -> Enginering."""
    words = name.split()
    i = max(range(len(words)), key=lambda k: len(words[k]))
    w = words[i]
    j = rng.randrange(2, len(w) - 2)
    words[i] = w[:j] + w[j + 1 :]
    return " ".join(w for w in words if w.lower() not in ("pvt", "ltd", "limited", "private"))


def upper_legal(name: str) -> str:
    s = name.upper().replace(" PVT LTD", " PRIVATE LIMITED").replace(" LTD", " LIMITED")
    return s


def weekday_near(rng: random.Random, d: date, spread: int = 0, end: date = PERIOD[1]) -> date:
    d = d + timedelta(days=rng.randint(-spread, spread)) if spread else d
    d = min(max(d, PERIOD[0]), end)
    step = timedelta(days=1 if d + timedelta(days=2) <= end else -1)
    while d.weekday() >= 5:
        d += step
    return d


def office_time(rng: random.Random) -> time:
    return time(rng.randint(9, 17), rng.choice([5, 12, 20, 35, 41, 50]))


def non_round(rng: random.Random, lo: int, hi: int) -> Decimal:
    n = rng.randint(lo, hi)
    if n % 100 == 0:
        n += rng.randint(1, 99)
    paise = rng.choice([0, 0, 0, 50, 25])
    return Decimal(n) + Decimal(paise) / 100


# ---------------------------------------------------------------- building blocks


def add_real_vendor(case: Case, key: str) -> Vendor:
    vid, name, variants, web, addr, city, state, country, desc, lo, hi, prefix = REAL_VENDORS[key]
    v = Vendor(
        key,
        vid,
        name,
        variants,
        web,
        addr,
        city,
        state,
        country,
        desc,
        lo,
        hi,
        prefix,
        created_on=date(case.rng.randint(2016, 2022), case.rng.randint(1, 12), 1)
        + timedelta(days=case.rng.randint(0, 27)),
    )
    case.vendors[v.vid] = v
    return v


def add_unresolved_vendor(case: Case, name: str, vid: str = "V008") -> Vendor:
    v = Vendor(
        "unresolved",
        vid,
        name,
        [name.replace(" Pvt Ltd", "")],
        None,
        "Shop 12, Market Yard",
        "Pune",
        "Maharashtra",
        "India",
        "Shop-floor consumables",
        100_000,
        200_000,
        "ZIS",
        created_on=date(2023, 10, 5),
        phone="020 2426 1180",
        real=False,
    )
    case.vendors[v.vid] = v
    return v


def base_staff(case: Case, alt_names: bool) -> None:
    for i, (sid, name, title, dept, addr, limit) in enumerate(BASE_STAFF):
        if alt_names:
            name = ALT_NAMES[i]
            addr = ALT_HOME if sid == "S003" else addr
        first, last = name.lower().split()
        joined = date(
            case.rng.randint(2015, 2022), case.rng.randint(1, 12), case.rng.randint(1, 28)
        )
        phone = f"98500{case.rng.randint(10000, 99999)}"
        email = f"{first}.{last}@halvexa.example"
        case.staff[sid] = Staff(sid, name, title, dept, addr, phone, email, joined, limit, orig=sid)


def approvers_for(case: Case, amount: Decimal, exclude: set[str]) -> Staff:
    """Lowest-tier approver whose limit keeps `amount` out of the 5% band under it."""
    ok = [
        s
        for s in case.staff.values()
        if s.limit and s.sid not in exclude and amount < Decimal(s.limit) * BAND
    ]
    tier = min(s.limit for s in ok)
    return case.rng.choice([s for s in ok if s.limit == tier])


def approver_raw(rng: random.Random, s: Staff) -> str:
    first, last = s.name.split()
    return rng.choice([s.name, s.name, s.name.lower(), f"{first[0]}. {last}"])


def background_rows(case: Case, v: Vendor, k: int, exclude: set[str]) -> None:
    """k invoices spread over the period: weekday office hours, non-round, gap < 365 days."""
    rng = case.rng
    start, end = case.period
    seg = (end - start).days / k
    inv = rng.randint(1000, 90000)
    for i in range(k):
        d = weekday_near(
            rng,
            start + timedelta(days=int(seg * i + seg * rng.uniform(0.25, 0.75))),
            end=end,
        )
        amount = non_round(rng, v.lo, v.hi)
        appr = approvers_for(case, amount, exclude)
        inv += rng.randint(37, 400)
        case.rows.append(
            Row(
                d,
                v,
                rng.choice([v.name] * 3 + v.variants) if v.variants else v.name,
                f"{v.prefix}{inv}",
                amount,
                appr,
                approver_raw(rng, appr),
                "sunita.patil",
                datetime.combine(d, office_time(rng)),
                v.desc,
                f"PO-{rng.randint(4000, 9999)}",
            )
        )


# ---------------------------------------------------------------- plants


def plant_career_overlap(case: Case, vid: str = "V017") -> None:
    s = case.staff["S004"]
    s.name, s.linkedin = TEJASH
    s.email, s.joined, s.address = (
        "tejash.chauhan@halvexa.example",
        date(2025, 1, 15),
        "Aundh, Pune",
    )
    # An ordinary-looking vendor file (decision 31 Oct, B/a1 option b): commercial address, phone,
    # set up by master-data admin months before the first invoice, so the case reads as a
    # conflict of interest only. No website on purpose: docrack.ai resolves to another record.
    v = Vendor(
        "docrack",
        vid,
        "DocRack",
        ["DOCRACK", "Docrak"],
        None,
        "Office 304, 3rd Floor, Powai",
        "Mumbai",
        "Maharashtra",
        desc="Document audit automation services",
        created_on=date(2025, 10, 6),
        phone="022 4971 3302",
    )
    case.vendors[vid] = v
    rng = case.rng
    # Monthly from March 2026, when S004's DocRack role starts, through the end of the ledger;
    # amounts grow every month (T12) and stay below 95% of S004's limit.
    end = case.period[1]
    targets = [date(2026, m, 10) for m in range(3, 13) if date(2026, m, 10) <= end]
    # DocRack bills other clients too: invoice numbers jump like other real vendors' (no T07).
    # A separate generator keeps every other draw in the case unchanged.
    inv_rng = random.Random(case.seed + 17)
    inv = inv_rng.randint(100, 300)
    for k, t in enumerate(targets):
        d = weekday_near(rng, t, spread=4, end=end)
        amount = non_round(rng, 110_000 + 45_000 * k, 118_000 + 45_000 * k)
        inv += inv_rng.randint(37, 400)
        case.rows.append(
            Row(
                d,
                v,
                [v.name, *v.variants][k % 3],
                f"DR/{d.year}/{inv}",
                amount,
                s,
                approver_raw(rng, s),
                "sunita.patil",
                datetime.combine(d, office_time(rng)),
                v.desc,
                f"PO-{4700 + k}",
            )
        )
    case.expected.append(
        {
            "typology": "conflict_of_interest",
            "subjects": [s.sid],
            "objects": [vid],
            "verdict": "Substantiated",
        }
    )
    case.tip.append(
        "For the last year a manager in procurement has been pushing payments to "
        "DocRack. They only started billing us in March, the amounts grow every month, and "
        "the same manager signs off every one of their invoices."
    )
    case.notes.append(
        f"{s.sid} {s.name} (team member, consent) is Co-Founder at DocRack, "
        "Crustdata company 71095782, from 2026-03-01 (person 177265563). "
        f"{vid}'s {len(targets)} invoices run monthly from 2026-03 to {targets[-1]:%Y-%m}, "
        f"all approved by {s.sid} and all during that employment, growing every month. "
        f"{vid}'s vendor file looks ordinary (commercial address, phone, created by mdm.admin on "
        "2025-10-06); it has no website on purpose: docrack.ai resolves to another record."
    )


def plant_shell(case: Case, name: str, vid: str = "V023") -> None:
    rng = case.rng
    s = case.staff["S003"]
    s.phone = (
        "9822041736" if s.address.startswith("Flat 7") else f"98{rng.randint(10000000, 99999999)}"
    )
    digits = s.phone
    addr = (
        s.address.replace("Flat 7", "Flat No. 7")
        .replace("Apartments", "Apts")
        .replace("Residency", "Resi.")
        .replace("Road", "Rd")
        .replace(" Pune 4", " Pune - 4")
    )
    brand = name.split()[0]
    v = Vendor(
        "shell",
        vid,
        name,
        [upper_legal(name), typo(rng, name)],
        None,
        addr,
        "Pune",
        "Maharashtra",
        desc="Misc. engineering supplies",
        created_on=date(2025, 1, 10),
        created_by=s.user,
        phone=f"+91 {digits[:5]} {digits[5:]}",
        email=f"{brand.lower()}.traders@gmail.example",
        bank=f"50100{rng.randint(100000000, 999999999)}",
        real=False,
    )
    case.vendors[vid] = v
    first = date(2025, 1, 18)
    amounts = rng.sample(range(490_000, 500_000, 1000), 8)
    prefix = "".join(w[0] for w in name.split()[:3]).upper()
    for k in range(8):
        d = first if k == 0 else weekday_near(rng, first + timedelta(days=28 * k), spread=3)
        late = k % 2 == 0
        t = time(rng.randint(22, 23), rng.randint(0, 59)) if late else office_time(rng)
        case.rows.append(
            Row(
                d,
                v,
                [v.name, *v.variants][k % 3],
                f"{prefix}/{k + 1:03d}",
                Decimal(amounts[k]),
                s,
                approver_raw(rng, s),
                s.user,
                datetime.combine(d, t),
                v.desc,
                "",
                v.bank,
            )
        )
    case.expected.append({"typology": "shell_company", "objects": [vid], "verdict": SHELL_VERDICT})
    case.tip.append(
        f"{brand} didn't exist before January 2025 and nobody on the shop floor has "
        "seen anything delivered from them. Their invoices are always just under five "
        "lakh and some get approved late at night."
    )
    case.notes.append(
        f"{vid} {name} is fictional (Crustdata identify: no match). Address and "
        f"phone equal {s.sid}'s (spelled differently); created 2025-01-10 by "
        f"{s.user}, who also posts and approves its 8 round invoices just under "
        f"{s.sid}'s 5,00,000 limit, half of them after 22:00."
    )


def plant_false_lead(case: Case, vid: str = "V031") -> None:
    s = case.staff["S005"]
    s.name, s.linkedin = KEDAR
    s.email = "kedar.sharma@halvexa.example"
    v = Vendor(
        "hcltech",
        vid,
        "HCL Technologies Ltd",
        ["HCL TECHNOLOGIES LIMITED"],
        "hcltech.com",
        "Technology Hub, SEZ, Plot 3A, Sector 126",
        "Noida",
        "Uttar Pradesh",
        desc="ERP support and AMC",
        lo=350_000,
        hi=800_000,
        prefix="HCL",
        created_on=date(2018, 5, 14),
    )
    case.vendors[vid] = v
    background_rows(case, v, 5, exclude={s.sid})
    case.expected.append(
        {
            "typology": "conflict_of_interest",
            "subjects": [s.sid],
            "objects": [vid],
            "verdict": "Unfounded",
        }
    )
    case.must_clear.append(vid)
    case.tip.append(
        "I also heard Kedar Sharma used to work for HCLTech and still gets them contracts."
    )
    case.notes.append(
        f"False lead: a namesake Kedar Sharma in Noida (Crustdata person 6677240) "
        f"worked at HCLTech (company 1910) 2023-02 to 2025-03. Our {s.sid} "
        "(person 420958731, resolved by LinkedIn URL) never did, approves nothing, "
        f"and appears on no {vid} row."
    )


def lookalike(rng: random.Random, name: str) -> str:
    """Drop one interior letter of the longest word, keeping the legal suffix."""
    words = name.split()
    i = max(range(len(words)), key=lambda k: len(words[k]))
    j = rng.randrange(2, len(words[i]) - 2)
    words[i] = words[i][:j] + words[i][j + 1 :]
    return " ".join(words)


def plant_duplicate(case: Case, vid: str = "V003", dup_vid: str = "V044") -> None:
    """The same invoice paid again through a look-alike copy of the vendor's master record."""
    rng = case.rng
    rows = sorted((r for r in case.rows if r.vendor.vid == vid), key=lambda r: r.d)
    orig = rows[len(rows) // 2]
    d = weekday_near(rng, orig.d + timedelta(days=rng.randint(6, 14)))
    v, appr = orig.vendor, orig.approver
    dup = Vendor(
        "duplicate_record",
        dup_vid,
        lookalike(rng, v.name),
        [],
        v.website,
        v.address,
        v.city,
        v.state,
        v.country,
        desc=v.desc,
        created_on=d - timedelta(days=rng.randint(10, 30)),
    )
    case.vendors[dup_vid] = dup
    case.rows.append(
        Row(
            d,
            dup,
            dup.name,
            orig.invoice,
            orig.amount,
            appr,
            approver_raw(rng, appr),
            "sunita.patil",
            datetime.combine(d, office_time(rng)),
            orig.desc,
            orig.po,
        )
    )
    case.expected.append(
        {"typology": "duplicate_billing", "objects": [vid], "verdict": "Substantiated"}
    )
    case.tip.append(
        f"I am also fairly sure we paid {v.name.split(' Limited')[0]} twice for the "
        "same invoice last year."
    )
    case.notes.append(
        f"{vid} invoice {orig.invoice} for {lakh(orig.amount, True)} paid on {orig.d}, then "
        f"paid again on {d} through {dup_vid} {dup.name!r}, a look-alike copy of {vid}'s master "
        f"record (same website) created {dup.created_on}. Billing (T04: same number and amount "
        f"across vendors) and identity (T14: look-alike names under two ids) both fire; {vid} "
        "itself is real and otherwise clean."
    )


def plant_shared_office(case: Case, shuffle: dict[str, str] | None = None) -> None:
    names = []
    for vid, name, variants, web, addr, desc, lo, hi, prefix in SHARED_OFFICE:
        vid = (shuffle or {}).get(vid, vid)
        v = Vendor(
            "shared_office",
            vid,
            name,
            variants,
            web,
            addr,
            "Pune",
            "Maharashtra",
            desc=desc,
            lo=lo,
            hi=hi,
            prefix=prefix,
            created_on=date(case.rng.randint(2022, 2023), case.rng.randint(1, 12), 3),
        )
        case.vendors[vid] = v
        background_rows(case, v, case.rng.randint(4, 6), exclude=set())
        case.must_clear.append(vid)
        names.append(name.replace(" Pvt Ltd", ""))
    case.tip.append(
        f"{names[0]} and {names[1]} are registered at the same address in "
        "Magarpatta. Two vendors, one office: it looks like the same people run both."
    )
    case.notes.append(
        "Honest shared office: TechLadd (958646) and E Giraffes Digital (615149) are "
        "real, unrelated tenants of WeWork Futura, Magarpatta Road, Pune; no shared "
        "phone, bank, tax id or staff link."
    )


# ---------------------------------------------------------------- case assembly


def build(
    name: str,
    seed: int,
    plants: list[str],
    n_vendors: int,
    n_rows: int,
    shuffle_ids: bool = False,
    period_end: date | None = None,
) -> Case:
    rng = random.Random(seed)
    case = Case(name, seed, rng, period=(PERIOD[0], period_end or PERIOD[1]))
    # n_rows is per standard two-year period; a longer ledger keeps the same monthly cadence
    n_rows = round(n_rows * (case.period[1] - PERIOD[0]).days / (PERIOD[1] - PERIOD[0]).days)
    base_staff(case, alt_names=shuffle_ids)
    # clean vendors: the two controls, the duplicate host, one unresolved, then fill
    keys = [*CONTROLS, "sundram"]
    pool = [k for k in REAL_VENDORS if k not in keys]
    rng.shuffle(pool)
    n_fill = max(0, n_vendors - len(keys) - 1 - len(plants))
    keys += pool[:n_fill]
    for k in keys:
        add_real_vendor(case, k)
    unresolved = rng.choice(UNRESOLVED_NAMES[1:]) if shuffle_ids else UNRESOLVED_NAMES[0]
    add_unresolved_vendor(case, unresolved)
    plant_staff = {"career_overlap": "S004", "shell": "S003", "false_lead": "S005"}
    exclude = {plant_staff[p] for p in plants if p in plant_staff}
    weights = {v.vid: (3 if v.hi > 1_000_000 else 2) for v in case.vendors.values()}
    total = sum(weights.values())
    for v in list(case.vendors.values()):
        background_rows(case, v, max(4, round(n_rows * weights[v.vid] / total)), exclude)
    case.must_clear += [
        v.vid
        for v in case.vendors.values()
        if v.real and not (v.vid == "V003" and "duplicate" in plants)
    ]
    if "career_overlap" in plants:
        plant_career_overlap(case)
    if "shell" in plants:
        shell = SHELL_NAMES[0] if not shuffle_ids else rng.choice(SHELL_NAMES[1:])
        plant_shell(case, shell)
    if "false_lead" in plants:
        plant_false_lead(case)
    if "duplicate" in plants:
        plant_duplicate(case)
    if "shared_office" in plants:
        plant_shared_office(case)
    if not plants:
        case.tip.append(
            "Tata Steel and Bharat Forge take a huge share of our spend and their "
            "invoices sail through approval. Someone senior must be getting something "
            "on the side from one of them."
        )
        case.notes.append(
            "Clean controls: every vendor is real or plainly unresolved, invoices "
            "follow normal patterns, and no staff member links to any vendor."
        )
    if shuffle_ids:
        reassign_ids(case)
    case.must_clear = sorted(set(case.must_clear))
    return case


def reassign_ids(case: Case) -> None:
    """Held-out: every vendor and staff id moves to a fresh random number."""
    rng = case.rng
    vmap = dict(
        zip(
            sorted(case.vendors),
            (f"V{n}" for n in rng.sample(range(100, 400), len(case.vendors))),
            strict=True,
        )
    )
    smap = dict(
        zip(
            sorted(case.staff),
            (f"S{n}" for n in rng.sample(range(100, 200), len(case.staff))),
            strict=True,
        )
    )
    for v in case.vendors.values():
        v.vid = vmap[v.vid]
    for s in case.staff.values():
        s.sid = smap[s.sid]
    case.vendors = {v.vid: v for v in case.vendors.values()}
    case.staff = {s.sid: s for s in case.staff.values()}
    for e in case.expected:
        for k, m in (("subjects", smap), ("objects", vmap)):
            if k in e:
                e[k] = [m[x] for x in e[k]]
    case.must_clear = [vmap[x] for x in case.must_clear]
    case.notes = [_remap(n, {**vmap, **smap}) for n in case.notes]


def _remap(text: str, m: dict[str, str]) -> str:
    return re.sub(r"\b[VS]\d{3}\b", lambda x: m.get(x.group(0), x.group(0)), text)


# ---------------------------------------------------------------- writing


def write_case(case: Case, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(case.seed + 7)
    hdr = {
        "date": rng.choice(["Txn Date", "Invoice Date", "Posting Date"]),
        "vendor": rng.choice(["Supplier", "Vendor", "Payee"]),
        "invoice": rng.choice(["Invoice No", "Inv No", "Bill No"]),
        "amount": rng.choice(["Amount INR ", "Amt ", "Amount (INR) "]),
        "approver": rng.choice(["Approved By", "Approver"]),
        "created": rng.choice(["Created By", "Entered By"]),
        "posted": rng.choice(["Posted At", "Entry Time"]),
        "desc": rng.choice(["Description", "Narration"]),
        "po": rng.choice(["PO Number", "PO No"]),
        "bank": rng.choice(["Bank Account", "Beneficiary Account"]),
    }
    header = list(hdr.values())
    rows = sorted(case.rows, key=lambda r: (r.d, r.invoice))
    buf = io.StringIO(newline="")
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(header)
    blank_at, repeat_at = len(rows) // 3, (2 * len(rows)) // 3
    for i, r in enumerate(rows):
        if i == blank_at:
            w.writerow([""] * len(header))
        if i == repeat_at:
            w.writerow(header)
        w.writerow(
            [
                fmt_date(rng, r.d),
                r.vendor_raw,
                r.invoice,
                fmt_amount(rng, r.amount),
                r.approver_raw,
                r.created_by,
                r.posted.strftime("%Y-%m-%d %H:%M"),
                r.desc,
                r.po,
                r.bank,
            ]
        )
    (out / "ledger.csv").write_bytes(b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8"))

    vendors = sorted(case.vendors.values(), key=lambda v: v.vid)
    _write_csv(
        out / "vendors.csv",
        [
            "Vendor Code",
            "Vendor Name",
            "Address",
            "City",
            "State",
            "Country",
            "Phone",
            "Email",
            "Website",
            "GSTIN",
            "Bank Account",
            "Created On",
            "Created By",
        ],
        [
            [
                v.vid,
                v.name,
                v.address,
                v.city,
                v.state,
                v.country,
                v.phone,
                v.email,
                v.website or "",
                "",
                v.bank,
                fmt_date(rng, v.created_on),
                v.created_by,
            ]
            for v in vendors
        ],
    )
    staff = sorted(case.staff.values(), key=lambda s: s.sid)
    _write_csv(
        out / "staff.csv",
        [
            "Emp ID",
            "Full Name",
            "Designation",
            "Department",
            "Address",
            "Mobile",
            "Email",
            "Bank A/c",
            "Date of Joining",
            "Approval Limit",
            "LinkedIn",
        ],
        [
            [
                s.sid,
                ("Mr. " if s.orig == "S003" else "") + s.name,
                s.title,
                s.dept,
                s.address,
                s.phone,
                s.email,
                "",
                fmt_date(rng, s.joined),
                lakh(Decimal(s.limit)) if s.limit else "",
                s.linkedin,
            ]
            for s in staff
        ],
    )
    tip = (
        "Subject: procurement payments - please look\n\n"
        f"I work in finance at {COMPANY.split()[0]} and I see most of the payment runs before "
        "they go out. "
        + (
            ""
            if len(case.tip) > 2
            else "I have kept quiet for a while because I could be "
            "wrong, but some things do not add up. "
        )
        + " ".join(case.tip)
        + " Something is off with how fast these get approved. Please look at the invoices "
        "from last year. I'd rather not say who I am.\n"
    )
    (out / "tip.txt").write_text(tip, encoding="utf-8", newline="\n")
    spec = {
        "name": case.name,
        "inputs": {
            "tip": "tip.txt",
            "ledger": "ledger.csv",
            "vendors": "vendors.csv",
            "staff": "staff.csv",
        },
        "expected": case.expected,
        "must_clear": case.must_clear,
        "notes": f"seed {case.seed}. " + " ".join(case.notes),
    }
    (out / "case.json").write_text(
        json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    buf = io.StringIO(newline="")
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    path.write_text(buf.getvalue(), encoding="utf-8", newline="")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--all", action="store_true", help="write the six named cases into cases/")
    ap.add_argument("--name", default="custom")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--plants", default="", help=f"comma list from {', '.join(PLANTS)}")
    ap.add_argument("--vendors", type=int, default=10)
    ap.add_argument("--rows", type=int, default=80)
    ap.add_argument("--shuffle-ids", action="store_true", help="fresh ids and names (held-out)")
    ap.add_argument("--period-end", type=date.fromisoformat, default=None, help="YYYY-MM-DD")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    if args.all:
        for name, plants in SIX.items():
            case = build(
                name, SEEDS[name], plants, args.vendors, args.rows, period_end=PERIOD_END.get(name)
            )
            write_case(case, ROOT / name)
            print(
                f"{name}: {len(case.rows)} rows, {len(case.vendors)} vendors, "
                f"expected {len(case.expected)}, must_clear {len(case.must_clear)}"
            )
        return 0
    plants = [p for p in args.plants.split(",") if p]
    bad = [p for p in plants if p not in PLANTS]
    if bad:
        ap.error(f"unknown plant(s): {', '.join(bad)}")
    case = build(
        args.name, args.seed, plants, args.vendors, args.rows, args.shuffle_ids, args.period_end
    )
    write_case(case, args.out or ROOT / args.name)
    print(f"{args.name}: {len(case.rows)} rows, {len(case.vendors)} vendors -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
