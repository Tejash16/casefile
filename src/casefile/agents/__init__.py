"""Model call sites (propose, match, critique, write) and the deterministic verdict gate.

The pipeline calls `set_audit(log)` once per run so agent records land in the run's hash chain.
"""

from casefile.agents._audit import get_audit, set_audit

__all__ = ["get_audit", "set_audit"]
