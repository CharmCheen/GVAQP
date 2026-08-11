"""Fail-closed unit-probability calibration boundary for physical ARC.

ARC requires Bernoulli relevance probabilities, while the frozen Y8 proxy emits
empirical percentile scores.  Those quantities are not interchangeable.  A
physical run therefore requires an explicitly deployable, provenance-bound
calibrator; exploratory or unsupported artifacts are rejected before any model
or video is opened.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, Sequence

import numpy as np


class CalibrationContractError(RuntimeError):
    """Raised when no scientifically deployable calibrator is available."""


class UnitProbabilityCalibrator(Protocol):
    artifact_id: str
    artifact_sha256: str
    test_only: bool

    def predict(self, query_id: str, raw_scores: Sequence[float]) -> np.ndarray:
        """Return finite Bernoulli relevance probabilities in input order."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_probabilities(values: np.ndarray, expected: int) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if values.shape != (expected,):
        raise CalibrationContractError("calibrator output does not align with unit scores")
    if np.any(~np.isfinite(values)) or np.any((values < 0.0) | (values > 1.0)):
        raise CalibrationContractError(
            "calibrator must return finite probabilities in [0, 1]"
        )
    return values


@dataclass(frozen=True)
class FrozenPiecewiseLinearCalibrator:
    """A frozen monotone lookup table with query-specific interpolation knots."""

    artifact_id: str
    artifact_sha256: str
    proxy_family: str
    proxy_config_hash: str
    query_knots: dict[str, tuple[tuple[float, float], ...]]
    test_only: bool = False

    def predict(self, query_id: str, raw_scores: Sequence[float]) -> np.ndarray:
        raw = np.asarray(raw_scores, dtype=float)
        if raw.ndim != 1 or np.any(~np.isfinite(raw)):
            raise CalibrationContractError("raw proxy scores must be a finite vector")
        knots = self.query_knots.get(str(query_id))
        if knots is None:
            raise CalibrationContractError(f"calibrator has no mapping for {query_id}")
        x = np.asarray([row[0] for row in knots], dtype=float)
        y = np.asarray([row[1] for row in knots], dtype=float)
        return _validate_probabilities(np.interp(raw, x, y), len(raw))


@dataclass(frozen=True)
class TestIdentityCalibrator:
    """Explicitly test-only adapter for deterministic CPU safety tests."""

    __test__ = False
    artifact_id: str = "TEST-ONLY-IDENTITY-CALIBRATOR"
    artifact_sha256: str = "test-only"
    test_only: bool = True

    def predict(self, query_id: str, raw_scores: Sequence[float]) -> np.ndarray:
        del query_id
        raw = np.asarray(raw_scores, dtype=float)
        return _validate_probabilities(raw, len(raw))


def load_deployable_calibrator(
    path: Path,
    *,
    expected_proxy_family: str,
    expected_proxy_config_hash: str,
) -> FrozenPiecewiseLinearCalibrator:
    """Load the only accepted physical schema, rejecting exploratory artifacts."""

    path = Path(path)
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    support = payload.get("final_calibration_support", {})
    deployable = payload.get("deployable", support.get("deployable"))
    if deployable is not True:
        status = support.get("status", payload.get("decision", "unspecified"))
        raise CalibrationContractError(
            f"calibrator is not deployable ({status}): {path}"
        )
    if payload.get("model_type") != "piecewise_linear_v1":
        raise CalibrationContractError("unsupported physical calibrator model_type")
    if payload.get("proxy_family") != expected_proxy_family:
        raise CalibrationContractError("calibrator proxy-family identity mismatch")
    if payload.get("proxy_config_hash") != expected_proxy_config_hash:
        raise CalibrationContractError("calibrator proxy-config identity mismatch")
    if payload.get("heldout_opened") is not False:
        raise CalibrationContractError("calibrator heldout-visibility declaration is unsafe")
    raw_knots = payload.get("query_knots")
    if set(raw_knots or {}) != {"Q1", "Q2"}:
        raise CalibrationContractError("calibrator must bind exactly Q1 and Q2")
    query_knots: dict[str, tuple[tuple[float, float], ...]] = {}
    for query_id, rows in raw_knots.items():
        knots = tuple((float(row[0]), float(row[1])) for row in rows)
        if len(knots) < 2:
            raise CalibrationContractError(f"{query_id} needs at least two knots")
        x = np.asarray([row[0] for row in knots], dtype=float)
        y = np.asarray([row[1] for row in knots], dtype=float)
        if (
            np.any(~np.isfinite(x))
            or np.any(~np.isfinite(y))
            or np.any(np.diff(x) <= 0)
            or np.any(np.diff(y) < 0)
            or x[0] > 0.0
            or x[-1] < 1.0
            or np.any((y < 0.0) | (y > 1.0))
        ):
            raise CalibrationContractError(f"invalid monotone {query_id} knots")
        query_knots[query_id] = knots
    return FrozenPiecewiseLinearCalibrator(
        artifact_id=str(payload["artifact_id"]),
        artifact_sha256=sha256_file(path),
        proxy_family=str(payload["proxy_family"]),
        proxy_config_hash=str(payload["proxy_config_hash"]),
        query_knots=query_knots,
    )
