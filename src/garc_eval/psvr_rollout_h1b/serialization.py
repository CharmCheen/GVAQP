"""Round-trip helpers for implementation traces."""
from __future__ import annotations
import json
from .trace_schema import PlannerTrace
def canonical_trace_json(trace: PlannerTrace) -> str:
    return json.dumps(trace.to_dict(), sort_keys=True, separators=(",", ":"))
