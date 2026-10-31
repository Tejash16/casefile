"""Each test starts with an empty payload store."""

from __future__ import annotations

import pytest

from casefile.audit.payloads import default_store


@pytest.fixture(autouse=True)
def _clean_payloads():
    default_store.clear()
    yield
    default_store.clear()
