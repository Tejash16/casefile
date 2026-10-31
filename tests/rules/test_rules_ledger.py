"""Ledger tests T04-T12: one positive and one negative example each."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

import numpy as np
from rules_factory import Book, ctx_for, of, staff, th, vendor

from casefile.rules.config import STRENGTH
from casefile.rules.tests_ import (
    t04_duplicates,
    t05_threshold,
    t06_round_amounts,
    t07_sequential,
    t08_benford,
    t09_off_hours,
    t10_dormant,
    t11_segregation,
    t12_velocity,
)

LIMIT = Decimal("500000")
BIG = Decimal("100000000")


def limited_staff():
    """S001 with a 5L limit; S900 (background approver) with a limit far above every amount."""
    return [staff("S001", "Asha Rao", approval_limit=LIMIT), staff("S900", approval_limit=BIG)]


def _below(limit: Decimal, k: int) -> float:
    """An amount inside the threshold band, k thousand under the limit."""
    band = float(limit) * th("threshold_band_pct") / 100
    return float(limit) - min(band, 1000 * k)


# ---------------------------------------------------------------- T04


def test_t04_same_invoice_number_paid_twice():
    b = Book()
    b.background()
    a = b.add("V100", date(2025, 2, 6), 342180, "SFL/24-25/0457")
    c = b.add("V100", date(2025, 2, 15), 342180, "SFL/24-25/0457")
    evs = t04_duplicates.run(ctx_for(b))
    sup = of(evs, "T04", "supports", "V100")
    assert len(sup) == 1  # the window rule does not re-report the same pair
    assert sup[0].strength == STRENGTH["t04_same_invoice_no"]
    assert sup[0].source.refs == [a.row_id, c.row_id]
    assert a.row_id in sup[0].quote and "3,42,180" in sup[0].quote


def test_t04_same_number_and_amount_across_vendors():
    b = Book()
    b.background()
    b.add("V101", date(2025, 3, 1), 77000, "A-1")
    b.add("V102", date(2025, 6, 1), 77000, "A-1")
    sup = of(t04_duplicates.run(ctx_for(b)), direction="supports")
    assert [e.strength for e in sup] == [STRENGTH["t04_same_same_different"]]
    assert sup[0].object_ids == ["V101", "V102"]


def test_t04_clean_vendors_refute():
    b = Book()
    b.background()
    evs = t04_duplicates.run(ctx_for(b))
    assert not of(evs, direction="supports")
    ref = of(evs, direction="refutes")
    assert len(ref) == 6 and all(e.strength == STRENGTH["t04_refute"] for e in ref)


# ---------------------------------------------------------------- T05


def test_t05_band_under_limit_supports():
    b = Book()
    b.background(start=date(2024, 4, 3))
    for i in range(3):
        b.add(
            "V100",
            date(2025, 1, 18) + timedelta(days=30 * i),
            _below(LIMIT, 2 + i),
            approver_id="S001",
        )
    evs = t05_threshold.run(ctx_for(b, staff_list=limited_staff()))
    sup = of(evs, "T05", "supports", "V100", "S001")
    assert len(sup) == 1 and sup[0].strength == STRENGTH["t05_band_majority"]
    assert not of(evs, direction="supports", obj="V800")


def test_t05_split_over_limit_supports():
    b = Book()
    b.background()
    window = th("split_window_days")
    b.add("V101", date(2025, 5, 1), float(LIMIT) * 0.6, approver_id="S001")
    b.add(
        "V101",
        date(2025, 5, 1) + timedelta(days=window - 1),
        float(LIMIT) * 0.5,
        approver_id="S001",
    )
    sup = of(t05_threshold.run(ctx_for(b, staff_list=limited_staff())), "T05", "supports", "V101")
    assert [e.strength for e in sup] == [STRENGTH["t05_split"]]
    assert "split" in sup[0].quote


def test_t05_population_pattern_refutes():
    b = Book()
    b.background()
    evs = t05_threshold.run(ctx_for(b, staff_list=limited_staff()))
    assert not of(evs, direction="supports")
    assert {e.strength for e in of(evs, direction="refutes")} == {STRENGTH["t05_refute"]}


# ---------------------------------------------------------------- T06


def test_t06_round_vendor_supports_and_population_refutes():
    b = Book()
    b.background()
    unit = th("round_unit_inr")
    for i in range(5):
        b.add("V100", date(2025, 1, 10) + timedelta(days=20 * i), unit * (490 + i))
    evs = t06_round_amounts.run(ctx_for(b))
    sup = of(evs, "T06", "supports", "V100")
    assert len(sup) == 1 and sup[0].strength == STRENGTH["t06_round_many"]
    assert not of(evs, direction="supports", obj="V800")
    assert of(evs, direction="refutes", obj="V800")[0].strength == STRENGTH["t06_refute"]


def test_t06_round_population_does_not_flag_vendor():
    """When every invoice in the ledger is round, one more round vendor is not elevated."""
    b = Book()
    unit = th("round_unit_inr")
    for v in range(4):
        for i in range(4):
            b.add(f"V{v}", date(2025, 1, 1) + timedelta(days=11 * i + v), unit * (10 + v + i))
    evs = t06_round_amounts.run(ctx_for(b))
    assert not of(evs, direction="supports")


# ---------------------------------------------------------------- T07


def test_t07_gap_free_and_narrow_support():
    b = Book()
    b.background()
    for i in range(1, 6):
        b.add("V100", date(2025, 1, 1) + timedelta(days=30 * i), 1000 + i, f"BET/{i:03d}")
    for i, n in enumerate([10, 11, 13]):
        b.add("V101", date(2025, 1, 2) + timedelta(days=30 * i), 2000 + i, f"Q-{n}")
    evs = t07_sequential.run(ctx_for(b))
    assert of(evs, "T07", "supports", "V100")[0].strength == STRENGTH["t07_gap_free"]
    assert of(evs, "T07", "supports", "V101")[0].strength == STRENGTH["t07_narrow"]


def test_t07_spread_numbers_refute():
    b = Book()
    b.background()
    evs = t07_sequential.run(ctx_for(b))
    assert not of(evs, direction="supports")
    assert {e.strength for e in of(evs, direction="refutes")} == {STRENGTH["t07_refute"]}


# ---------------------------------------------------------------- T08


def _log_uniform(b: Book, n: int) -> None:
    for i, u in enumerate(np.linspace(2, 6, n, endpoint=False)):
        b.add(f"V{i % 20}", date(2024, 4, 1) + timedelta(days=i % 360), round(10**u, 2))


def test_t08_small_population_is_a_neutral_note():
    b = Book()
    b.background()
    evs = t08_benford.run(ctx_for(b))
    assert len(evs) == 1 and evs[0].direction == "neutral" and evs[0].strength == 0


def test_t08_spike_supports_capped():
    b = Book()
    _log_uniform(b, th("benford_min_n") + 200)
    for i in range(150):
        b.add("V999", date(2025, 1, 1) + timedelta(days=i % 200), 49_000 + 7 * i)
    evs = t08_benford.run(ctx_for(b))
    sup = of(evs, "T08", "supports")
    assert sup and sup[0].quote.startswith("first-two digits 49")
    assert all(e.strength <= STRENGTH["t08_cap"] for e in sup)


def test_t08_conforming_population_has_no_spike():
    b = Book()
    _log_uniform(b, th("benford_min_n") + 200)
    evs = t08_benford.run(ctx_for(b))
    assert not of(evs, direction="supports")
    assert of(evs, direction="neutral")


# ---------------------------------------------------------------- T09


def test_t09_night_postings_support():
    b = Book()
    b.background()
    start, _ = th("off_hours")
    for i in range(4):
        d = date(2025, 1, 6) + timedelta(days=7 * i)  # Mondays
        b.add("V100", d, 1000 + i, posted_at=datetime(d.year, d.month, d.day, start + 1, 12))
    evs = t09_off_hours.run(ctx_for(b))
    sup = of(evs, "T09", "supports", "V100")
    assert len(sup) == 1 and sup[0].strength == STRENGTH["t09_off_hours"]
    assert "posted" in sup[0].quote


def test_t09_business_hours_do_not_flag():
    b = Book()
    b.background()
    assert t09_off_hours.run(ctx_for(b)) == []


# ---------------------------------------------------------------- T10


def test_t10_dormant_vendor_supports():
    b = Book()
    b.background()
    first = b.add("V100", date(2024, 1, 10), 5000)
    b.add("V100", first.date + timedelta(days=th("dormant_days") + 20), 6000)
    evs = t10_dormant.run(ctx_for(b))
    assert [e.object_ids for e in evs] == [["V100"]]
    assert evs[0].strength == STRENGTH["t10_dormant"]


def test_t10_regular_vendor_does_not_flag():
    b = Book()
    b.background()
    assert t10_dormant.run(ctx_for(b)) == []


# ---------------------------------------------------------------- T11


def _deshpande():
    return staff("S003", "Mr. Anil Deshpande", email="anil.deshpande@halvexa.example")


def test_t11_creator_also_approves():
    b = Book()
    b.add("V023", date(2025, 1, 18), 490000, approver_id="S003", created_by="adeshpande")
    v = vendor("V023", created_by="adeshpande", created_on=date(2025, 1, 10))
    evs = t11_segregation.run(ctx_for(b, [v], [_deshpande(), staff("S008", "Priya Nair")]))
    assert len(evs) == 1 and evs[0].subject_ids == ["S003"]
    assert "created_by adeshpande (S003)" in evs[0].quote
    assert evs[0].strength == STRENGTH["t11_same_user"]


def test_t11_different_creator_does_not_flag():
    b = Book()
    b.add("V023", date(2025, 1, 18), 490000, approver_id="S003", created_by="spatil")
    v = vendor("V023", created_by="pnair")
    staff_list = [_deshpande(), staff("S008", "Priya Nair"), staff("S006", "Sunita Patil")]
    assert t11_segregation.run(ctx_for(b, [v], staff_list)) == []


# ---------------------------------------------------------------- T12


def test_t12_dominant_growing_vendor_supports_others_refute():
    b = Book()
    b.background()
    for i in range(4):
        b.add("V100", date(2025, 3, 1) + timedelta(days=30 * i), 500000 + 1000 * i)
    evs = t12_velocity.run(ctx_for(b))
    sup = of(evs, "T12", "supports")
    assert [e.object_ids for e in sup] == [["V100"]]
    ref = of(evs, "T12", "refutes")
    assert ref and all(e.strength == STRENGTH["t12_refute"] for e in ref)
    assert "V100" not in {o for e in ref for o in e.object_ids}


def test_t12_even_spend_has_no_support():
    b = Book()
    for v in range(5):
        for i in range(4):
            b.add(f"V{v}", date(2024, 4, 1) + timedelta(days=45 * i + v), 10000 + 10 * v + i)
    evs = t12_velocity.run(ctx_for(b))
    assert not of(evs, direction="supports")
    assert len(of(evs, direction="refutes")) == 5
