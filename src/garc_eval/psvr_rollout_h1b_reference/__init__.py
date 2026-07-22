"""V1 fail-closed independent-reference verifier package.

No production H1B transition, planner, statistic, or evaluator module is
imported from this package.
"""

from .evidence_reader import PrimitiveEvidenceError, require_primitive_evidence

__all__ = ("PrimitiveEvidenceError", "require_primitive_evidence")
