"""ui/inputs.py renders headless (streamlit AppTest) for an empty out_dir and for a planted case,
with and without redaction; under redaction no team member's name reaches the page."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

CASE = Path(__file__).resolve().parents[2] / "cases" / "career_overlap"

SCRIPT = """
from pathlib import Path
from casefile.ui.inputs import render
out = Path({out!r})
render(out, {{"tip": out / "tip.txt", "ledger": out / "ledger.csv", "vendors": out / "vendors.csv",
             "staff": out / "staff.csv", "running": False, "redact": {redact}}})
"""


def _run(out: Path, redact: bool) -> AppTest:
    at = AppTest.from_string(SCRIPT.format(out=str(out), redact=redact), default_timeout=60)
    return at.run()


def _text(at: AppTest) -> str:
    parts = [m.value for m in at.markdown] + [t.value for t in at.text_area]
    parts += [i.value for i in at.info]
    for d in at.dataframe:  # full contents: a truncated repr could hide a leaked name
        v = d.value
        parts.append(v.to_csv() if hasattr(v, "to_csv") else v.data.to_csv())
    return "\n".join(str(p) for p in parts)


def test_empty_out_dir_shows_info(tmp_path):
    at = _run(tmp_path, redact=False)
    assert not at.exception
    assert at.info and "appear here" in at.info[0].value


@pytest.mark.parametrize("redact", [False, True])
def test_planted_case_renders(tmp_path, redact):
    for f in ("tip.txt", "ledger.csv", "vendors.csv", "staff.csv"):
        shutil.copy(CASE / f, tmp_path / f)
    at = _run(tmp_path, redact=redact)
    assert not at.exception, at.exception
    assert len(at.dataframe) == 3 and len(at.metric) == 4
    text = _text(at)
    assert "vendor spellings merged" in text
    for name in ("Tejash", "Chauhan", "tejash-chauhan"):
        assert (name in text) is not redact, name
