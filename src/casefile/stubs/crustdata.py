"""Stub for casefile.crustdata.client and casefile.resolve (b2): no network, everything resolved."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from casefile.schemas import (
    Resolution,
    ResolutionMethod,
    ResolutionStatus,
    StaffRecord,
    VendorRecord,
)


class CrustdataClient:
    def __init__(
        self,
        api_key: str | None,
        cache_dir: str | Path,
        offline: bool = False,
        audit: Any = None,
    ) -> None:
        self.offline = offline
        self.audit = audit

    def credits(self) -> dict[str, Any]:
        return {"stub": True}


def _resolved(method: ResolutionMethod) -> Resolution:
    return Resolution(
        status=ResolutionStatus.resolved, method=method, confidence=0.9, candidates_considered=1
    )


def resolve_vendors(vendors: list[VendorRecord], client: Any, judge: Any = None):
    res = _resolved(ResolutionMethod.identify_exact)
    return [v.model_copy(update={"resolution": res}) for v in vendors]


def resolve_staff(staff: list[StaffRecord], client: Any, judge: Any = None):
    res = _resolved(ResolutionMethod.person_search)
    return [s.model_copy(update={"resolution": res}) for s in staff]
