from __future__ import annotations

from dataclasses import dataclass
import math
from collections.abc import Mapping, Sequence
from typing import Any, Callable

from garc.controller.frontier import Candidate

from .materialize import MaterializationError, materialize_candidate, materialize_confirm_result


class ConfirmActionError(RuntimeError):
    """Base error for a CONFIRM action that cannot complete atomically."""

    def __init__(self, message: str, *, actual_cost_sec: float = 0.0):
        super().__init__(message)
        self.actual_cost_sec = float(actual_cost_sec)


class ConfirmExecutionError(ConfirmActionError):
    pass


class ConfirmParseError(ConfirmActionError):
    pass


@dataclass(frozen=True)
class ParsedConfirmResult:
    candidate_id: str
    unit_id: int
    positive: bool
    raw_utility_ids: tuple[Any, ...]
    actual_cost_sec: float
    materialized: dict[str, Any]


def parse_confirm_result(raw: Mapping[str, Any], candidate: Candidate,
                         materialized: dict[str, Any]) -> ParsedConfirmResult:
    """Parse one backend response without performing event materialization."""
    if not isinstance(raw, Mapping):
        raise ConfirmParseError("CONFIRM result must be a mapping")
    try:
        cost = float(raw.get("actual_cost_sec", 0.0))
    except (TypeError, ValueError) as error:
        raise ConfirmParseError("actual_cost_sec must be numeric") from error
    if not math.isfinite(cost) or cost < 0:
        raise ConfirmParseError("actual_cost_sec must be finite and non-negative")
    if raw.get("completed", True) is not True or str(raw.get("status", "ok")).lower() in {"failed", "error"}:
        raise ConfirmExecutionError(str(raw.get("error", "CONFIRM did not complete")), actual_cost_sec=cost)
    positive = bool(raw.get("positive", False))
    values = raw.get("distinct_utility_ids", ())
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ConfirmParseError("distinct_utility_ids must be a sequence", actual_cost_sec=cost)
    return ParsedConfirmResult(candidate.candidate_id, candidate.unit_id, positive,
                               tuple(values), cost, materialized)


@dataclass(frozen=True)
class ConfirmOutcome:
    candidate_id: str
    unit_id: int
    positive: bool
    distinct_utility_ids: tuple[str, ...]
    actual_cost_sec: float
    materialized: dict[str, Any]


class ConfirmAdapter:
    """Adapter around a replay mapping or caller-supplied physical CONFIRM function."""

    def __init__(self, backend: Mapping[int, dict[str, Any]] | Callable[[dict[str, Any]], dict[str, Any]],
                 *, materializer: Callable[[Candidate], dict[str, Any]] = materialize_candidate,
                 event_materializer: Callable[[bool, Sequence[Any]], tuple[str, ...]] = materialize_confirm_result):
        self.backend = backend
        self.materializer = materializer
        self.event_materializer = event_materializer

    def confirm(self, candidate: Candidate) -> ConfirmOutcome:
        try:
            request = self.materializer(candidate)
        except MaterializationError:
            raise
        except Exception as error:
            raise MaterializationError(str(error)) from error
        try:
            raw = self.backend(request) if callable(self.backend) else self.backend[candidate.unit_id]
        except Exception as error:
            raise ConfirmExecutionError(f"CONFIRM backend failed: {error}") from error
        parsed = parse_confirm_result(raw, candidate, request)
        try:
            utility_ids = self.event_materializer(parsed.positive, parsed.raw_utility_ids)
        except MaterializationError as error:
            raise MaterializationError(str(error), actual_cost_sec=parsed.actual_cost_sec) from error
        except Exception as error:
            raise MaterializationError(str(error), actual_cost_sec=parsed.actual_cost_sec) from error
        return ConfirmOutcome(parsed.candidate_id, parsed.unit_id, parsed.positive,
                              utility_ids, parsed.actual_cost_sec, parsed.materialized)
