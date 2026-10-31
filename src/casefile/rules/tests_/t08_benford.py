"""T08 benford_population: first-two-digit test on the whole population only. Below
`benford_min_n` rows it emits one neutral note and stops. Spikes (observed above Benford with
Nigrini's z >= `benford_z`) are leads, never proof: strength is capped at the `t08_cap` scale."""

from __future__ import annotations

import numpy as np

from casefile.rules import evidence as ev
from casefile.rules.config import STRENGTH
from casefile.rules.context import RuleContext
from casefile.schemas import Direction, EvidenceObject, SourceKind

TEST = "T08"
DIGITS = np.arange(10, 100)
EXPECTED = np.log10(1 + 1 / DIGITS)


def first_two(amounts: np.ndarray) -> np.ndarray:
    a = amounts[amounts >= 10]
    return np.floor(a / 10 ** (np.floor(np.log10(a)) - 1)).astype(int)


def run(ctx: RuleContext) -> list[EvidenceObject]:
    df = ctx.rows[ctx.rows.amount >= 10]
    n, min_n = len(df), ctx.th("benford_min_n")
    if n < min_n:
        quote = f"population: {n} amounts >= 10; benford_min_n {min_n}; test not run"
        return [
            ev.make(
                test_id=TEST,
                direction=Direction.neutral,
                strength=STRENGTH["t08_note"],
                summary=f"Benford's first-two-digit test was not run: the ledger has {n} usable "
                f"amounts, fewer than the {min_n} it needs.",
                quote=quote,
                kind=SourceKind.derived_stat,
                refs=["ledger:population"],
                records={"n": n, "benford_min_n": min_n},
            )
        ]
    d = first_two(df.amount.to_numpy())
    observed = np.bincount(d, minlength=100)[10:100] / n
    mad = float(np.mean(np.abs(observed - EXPECTED)))
    z = (np.abs(observed - EXPECTED) - 1 / (2 * n)) / np.sqrt(EXPECTED * (1 - EXPECTED) / n)
    zcrit, cap = ctx.th("benford_z"), STRENGTH["t08_cap"]
    out = [
        ev.make(
            test_id=TEST,
            direction=Direction.neutral,
            strength=STRENGTH["t08_note"],
            summary=f"Across {n} amounts the first-two-digit distribution has mean absolute "
            f"deviation {mad:.4f} from Benford's law.",
            quote=f"population: {n} amounts; first-two-digit MAD {mad:.4f}",
            kind=SourceKind.derived_stat,
            refs=["ledger:population"],
            records={"n": n, "mad": round(mad, 6), "observed": observed.round(6).tolist()},
        )
    ]
    spikes = [i for i in np.argsort(-z) if z[i] >= zcrit and observed[i] > EXPECTED[i]]
    for i in spikes:
        digit = int(DIGITS[i])
        g = df[d == digit]
        rows = ctx.rows_for(list(g.row_id))
        out.append(
            ev.from_rows(
                test_id=TEST,
                direction=Direction.supports,
                strength=min(cap, cap * float(z[i]) / (2 * zcrit)),
                summary=f"Amounts starting with {digit} make up {100 * observed[i]:.2f}% of the "
                f"population against Benford's {100 * EXPECTED[i]:.2f}%; a lead, not proof.",
                rows=rows,
                max_rows=ctx.th("quote_max_rows"),
                prefix=f"first-two digits {digit}: {len(g)} of {n} ({100 * observed[i]:.2f}% vs "
                f"Benford {100 * EXPECTED[i]:.2f}%, z {z[i]:.1f}): ",
                subject_ids=[],
            )
        )
    return out
