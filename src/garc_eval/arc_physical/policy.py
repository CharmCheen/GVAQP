"""ARC policy plugin: exhaustive proxy observation, then online refinement."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np

from garc_eval.arc_cached_replay import (
    ARCConfig,
    ARCSelector,
    Selection,
    sequential_js_clusters,
)

from .calibration import UnitProbabilityCalibrator


class ProxyPassIncompleteError(RuntimeError):
    """Raised if refinement is requested before every frozen unit was scanned."""


@dataclass(frozen=True)
class PhysicalObservation:
    unit_id: int
    outcome: str
    parse_status: str
    physically_verified: bool


def physical_outcome(result: dict[str, Any]) -> PhysicalObservation:
    """Preserve indeterminate parser states rather than coercing them negative."""

    if result.get("physical_oracle_invocation") is not True:
        raise RuntimeError("VERIFY result was not produced by the physical oracle")
    if result.get("cache_replay") is not False:
        raise RuntimeError("cached oracle output is forbidden in the physical baseline")
    parse_status = str(result.get("parse_status", "missing")).strip().lower()
    raw_label = str(result.get("parsed_label", "unusable")).strip().lower()
    if parse_status != "ok":
        outcome = "parse_failure"
    elif raw_label in {"positive", "negative", "abstain"}:
        outcome = raw_label
    else:
        outcome = "unusable"
    return PhysicalObservation(
        unit_id=int(result["unit_id"]),
        outcome=outcome,
        parse_status=parse_status,
        physically_verified=True,
    )


class ARCPhysicalPolicy:
    """A leakage-free policy capability suitable for the shared physical loop."""

    def __init__(
        self,
        unit_ids: Sequence[int],
        *,
        query_id: str,
        seed: int,
        calibrator: UnitProbabilityCalibrator,
        config: ARCConfig | None = None,
    ) -> None:
        self.unit_ids = tuple(int(value) for value in unit_ids)
        if self.unit_ids != tuple(range(len(self.unit_ids))):
            raise ValueError("ARC physical units must be contiguous and zero-based")
        if getattr(calibrator, "test_only", False) and not str(
            getattr(calibrator, "artifact_id", "")
        ).startswith("TEST-ONLY-"):
            raise ValueError("invalid test-only calibrator identity")
        self.query_id = str(query_id)
        self.seed = int(seed)
        self.calibrator = calibrator
        self.config = config or ARCConfig()
        if self.config.tau_units != 1:
            raise ValueError("ARC-UNIT-INSPIRED-PHYS-v1 freezes tau=1 unit")
        self._raw_scores: dict[int, float] = {}
        self._selector: ARCSelector | None = None
        self._selection_ids: set[int] = set()
        self._physical_observations: list[PhysicalObservation] = []

    @property
    def proxy_pass_complete(self) -> bool:
        return len(self._raw_scores) == len(self.unit_ids)

    @property
    def refinement_started(self) -> bool:
        return self._selector is not None

    def observe_proxy_score(self, unit_id: int, score: float) -> None:
        if self.refinement_started:
            raise RuntimeError("proxy observations cannot change after refinement starts")
        unit_id = int(unit_id)
        if unit_id not in self.unit_ids:
            raise ValueError(f"unknown unit {unit_id}")
        if unit_id in self._raw_scores:
            raise RuntimeError(f"duplicate proxy observation for unit {unit_id}")
        score = float(score)
        if not np.isfinite(score) or not 0.0 <= score <= 1.0:
            raise ValueError("proxy score must be finite in [0, 1]")
        self._raw_scores[unit_id] = score

    def finish_proxy_pass(self) -> dict[str, Any]:
        if not self.proxy_pass_complete:
            missing = sorted(set(self.unit_ids) - set(self._raw_scores))
            raise ProxyPassIncompleteError(
                f"complete proxy pass required before refinement; missing {len(missing)} units"
            )
        if self._selector is not None:
            raise RuntimeError("proxy pass was already finalized")
        raw = np.asarray([self._raw_scores[unit_id] for unit_id in self.unit_ids])
        probabilities = self.calibrator.predict(self.query_id, raw)
        clusters = sequential_js_clusters(
            probabilities, self.config.cluster_threshold
        )
        # The wall-clock driver controls the query count by stopping admissions;
        # using the whole unit universe here prevents an artificial call budget.
        self._selector = ARCSelector(
            probabilities,
            clusters,
            budget=len(self.unit_ids),
            seed=self.seed,
            config=self.config,
        )
        return {
            "raw_unit_scores": raw.tolist(),
            "calibrated_probabilities": probabilities.tolist(),
            "bernoulli_vectors": np.column_stack(
                (1.0 - probabilities, probabilities)
            ).tolist(),
            "cluster_labels": clusters.astype(int).tolist(),
            "cluster_count": int(len(np.unique(clusters))),
            "calibrator_artifact_id": self.calibrator.artifact_id,
            "calibrator_sha256": self.calibrator.artifact_sha256,
        }

    def select_next(self) -> Selection | None:
        if self._selector is None:
            raise ProxyPassIncompleteError("ARC refinement cannot start before proxy finalization")
        selection = self._selector.select_next()
        if selection is not None:
            if selection.unit_id in self._selection_ids:
                raise RuntimeError("duplicate logical VERIFY selected by ARC")
            self._selection_ids.add(selection.unit_id)
        return selection

    def observe_verify(self, selection: Selection, result: dict[str, Any]) -> PhysicalObservation:
        if self._selector is None:
            raise ProxyPassIncompleteError("VERIFY cannot be observed before proxy finalization")
        observation = physical_outcome(result)
        if observation.unit_id != selection.unit_id:
            raise RuntimeError("physical VERIFY result does not match ARC selection")
        self._selector.observe(selection, observation.outcome)
        self._physical_observations.append(observation)
        return observation

    def comparable_queried_rows(self) -> list[dict[str, Any]]:
        """Return explicit determinate VERIFY rows only; never propagated labels."""

        return [
            {"unit_id": row.unit_id, "parsed_label": row.outcome}
            for row in self._physical_observations
            if row.outcome in {"positive", "negative"}
        ]

    def diagnostics(self) -> dict[str, Any]:
        selector = None if self._selector is None else self._selector.diagnostics()
        return {
            "proxy_pass_complete": self.proxy_pass_complete,
            "observed_proxy_units": len(self._raw_scores),
            "refinement_started": self.refinement_started,
            "logical_oracle_calls": len(self._physical_observations),
            "selected_unit_ids": sorted(self._selection_ids),
            "physical_observations": [row.__dict__ for row in self._physical_observations],
            "selector": selector,
            "propagated_labels_visibility": "scheduling_diagnostics_only",
            "event_relation_source": "explicit_determinate_physical_VERIFY_only",
        }
