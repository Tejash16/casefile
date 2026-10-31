"""Entity resolution against Crustdata (b2). The pipeline imports the two resolvers from here."""

from __future__ import annotations

from casefile.resolve.people import vendor_people
from casefile.resolve.staff import resolve_staff
from casefile.resolve.vendors import resolve_vendors

__all__ = ["resolve_staff", "resolve_vendors", "vendor_people"]
