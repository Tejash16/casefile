"""Entities tab (casefile.ui.entities): row building and empty/filled render. No network."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("streamlit")

from casefile.ui import entities  # noqa: E402

ENTITIES = {
    "vendors": [
        {
            "vendor_id": "V017",
            "name_raw": "DocRack",
            "resolution": {"status": "resolved", "method": "identify_exact", "confidence": 1.0},
            "crustdata": {
                "crustdata_company_id": "71095782",
                "name": "DocRack",
                "headcount_total": 2,
                "updated_at": "2026-10-30T00:23:30Z",
            },
        },
        {"vendor_id": "V023", "name_raw": "Brindora", "resolution": {"status": "unresolved"}},
    ],
    "staff": [
        {
            "staff_id": "S004",
            "name_raw": "T. C.",
            "resolution": {"status": "resolved", "method": "linkedin_url", "confidence": 1.0},
            "crustdata": {
                "crustdata_person_id": "177265563",
                "updated_at": "2026-10-26T16:58:10Z",
                "employment": [
                    {
                        "company_name": "DocRack",
                        "crustdata_company_id": "71095782",
                        "is_current": True,
                    }
                ],
            },
        }
    ],
    "credits_used": 4.0,
    "crustdata_calls": 9,
}


def test_rows_carry_status_and_citations() -> None:
    v = entities.vendor_rows(ENTITIES["vendors"])
    assert v[0]["Citation"] == "crustdata:company:71095782@2026-10-30T00:23:30Z"
    assert v[1]["Status"] == "unresolved" and v[1]["Citation"] == ""
    s = entities.staff_rows(ENTITIES["staff"], {"S004"})
    assert s[0]["Named in allegation"] == "yes"
    assert entities.employment_rows(ENTITIES["staff"][0]["crustdata"])[0]["To"] == "present"


def test_named_subjects_reads_any_subjects_list(tmp_path: Path) -> None:
    (tmp_path / "findings.json").write_text(json.dumps({"h": [{"subjects": ["S004", "S005"]}]}))
    assert entities.named_subjects(tmp_path) == {"S004", "S005"}
    assert entities.named_subjects(tmp_path / "nope") == set()


def _app(out: str, running: bool) -> None:
    from pathlib import Path

    from casefile.ui.entities import render

    render(Path(out), {"running": running, "redact": True})


def test_render_empty_and_filled(tmp_path: Path) -> None:
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_app, args=(str(tmp_path), False)).run()
    assert not at.exception and "No entities yet" in at.info[0].value
    (tmp_path / "entities.json").write_text(json.dumps(ENTITIES), encoding="utf-8")
    at = AppTest.from_function(_app, args=(str(tmp_path), False)).run()
    assert not at.exception
    assert {m.label: m.value for m in at.metric}["Vendors resolved"] == "1/2"
    assert len(at.dataframe) == 3  # vendors, staff, one employment history
