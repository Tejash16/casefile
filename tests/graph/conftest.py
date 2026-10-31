"""Graph tests reuse the rules test builders and start with an empty payload store."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rules"))

from casefile.audit.payloads import default_store  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_payloads():
    default_store.clear()
    yield
    default_store.clear()
