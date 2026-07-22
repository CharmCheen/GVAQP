#!/usr/bin/env python3
"""Run the four-arm native ARC/PSTR experiment from cached oracle labels.

This is intentionally an exploratory replay: every included label source was
already open before PSTR was proposed.  The runner nevertheless isolates the
PSTR selector behind a proxy-only seal, audits every ARC oracle access, keeps
native and shared materializers separate, and recomputes all reported metrics
from the persisted prediction files.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import itertools
import json
import math
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd


PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parent
OUTPUT = PACKAGE / "outputs" / "native_arc_vs_pstr"
BENCHMARK_LIB = (
    REPO
    / "Audited_Event_Hypothesis_AQP_Design_Pack_v1"
    / "agent_run"
    / "clean_baseline_benchmark_v2_strict"
    / "scripts"
    / "benchmark_lib.py"
)
ARC_ROOT = REPO / "refe_repos" / "ARC-main" / "arc"
ARC_ADAPTER = REPO / "refe_repos" / "adapter" / "arc_baseline" / "run.py"
PSTR_SEALER = PACKAGE / "scripts" / "seal_pstr_selections.py"
PSTR_PROTOCOL = PACKAGE / "config" / "frozen_external_confirmation_v5.json"
PSTR_LODO = PACKAGE / "outputs" / "pstr_exploration_v2" / "leave_one_domain_out.csv"

BUDGETS = [5, 10, 20, 50, 80, 100]
SEEDS = [0, 1, 2, 3, 4]
ARC_CONFIG = {
    "proxy_threshold": 0.4,
    "cluster_algorithm": "ARC sequential Jensen-Shannon change points",
    "cluster_threshold": 0.001,
    "cluster_input": "two-class public-proxy posterior [1-s,s]",
    "tau_units": 1,
    "confidence": 0.9,
    "iou_threshold": 0.5,
    "startup_sampling_rate": 0.002,
    "tc_enabled": True,
    "ps_enabled": True,
    "lp_enabled": True,
    "exact_fill": False,
}
K3_CONFIG = {"g_max": 1, "d_core_max": 40.0, "d_seg_max": 60.0}
METRICS = [
    "event_precision",
    "event_recall",
    "event_f1",
    "tiou_03",
    "tiou_05",
    "matched_mean_iou",
    "overmerge",
    "oversplit",
    "returned_seconds",
    "overcoverage_ratio",
    "predicted_event_count",
    "reference_event_count",
]
PRIMARY_METRICS = ["event_precision", "event_recall", "event_f1"]


def import_from_path(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BENCH = import_from_path("native_arc_pstr_benchmark_lib", BENCHMARK_LIB)
sys.path.insert(0, str(ARC_ROOT))
from arc import arc as original_arc  # noqa: E402
from pruning_phase import perform_clustering  # noqa: E402
from tools import findCandClips  # noqa: E402


@dataclass
class DomainData:
    dataset: str
    domain: str
    video_id: str
    absolute_slice_seconds: tuple[float, float]
    units: pd.DataFrame
    proxy: pd.DataFrame
    oracle: pd.DataFrame
    reference: pd.DataFrame
    raw_sources: dict[str, Path]

    @property
    def benchmark_id(self) -> str:
        return str(self.units["benchmark_id"].iloc[0])


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def standard_units(
    benchmark_id: str,
    video_id: str,
    unit_ids: pd.Series,
    starts: pd.Series,
    ends: pd.Series,
) -> pd.DataFrame:
    out = pd.DataFrame(
        {
            "benchmark_id": benchmark_id,
            "video_id": video_id,
            "unit_id": unit_ids.astype(int),
            "start_time": starts.astype(float),
            "end_time": ends.astype(float),
        }
    )
    if out.unit_id.tolist() != list(range(len(out))):
        raise RuntimeError(f"noncontiguous unit IDs for {benchmark_id}")
    if not np.all(out.end_time.to_numpy(float) > out.start_time.to_numpy(float)):
        raise RuntimeError(f"invalid unit duration for {benchmark_id}")
    return out


def standard_reference(
    benchmark_id: str,
    video_id: str,
    events: pd.DataFrame,
    units: pd.DataFrame,
    id_column: str,
    start_column: str,
    end_column: str,
    event_type_column: str,
) -> pd.DataFrame:
    rows = []
    for event in events.itertuples(index=False):
        start = float(getattr(event, start_column))
        end = float(getattr(event, end_column))
        overlap = units[
            (units.end_time.astype(float) > start) & (units.start_time.astype(float) < end)
        ].unit_id.astype(int)
        rows.append(
            {
                "benchmark_id": benchmark_id,
                "video_id": video_id,
                "reference_event_id": str(getattr(event, id_column)),
                "start_time": start,
                "core_start_time": start,
                "core_end_time": end,
                "end_time": end,
                "canonical_anchor_time": start,
                "source_unit_ids": "|".join(map(str, overlap.tolist())),
                "event_type": str(getattr(event, event_type_column)),
                "reference_type": "VLM_DEFINED_PSEUDO_ORACLE",
                "reference_version": "native_arc_vs_pstr_replay_v1",
                "adjudication_status": "not_human_adjudicated",
            }
        )
    return pd.DataFrame(rows)


def load_dataset3() -> DomainData:
    strict = (
        REPO
        / "Audited_Event_Hypothesis_AQP_Design_Pack_v1"
        / "agent_run"
        / "clean_baseline_benchmark_v2_strict"
    )
    paths = {
        "units": strict / "frozen_inputs" / "units.csv",
        "oracle": strict / "frozen_inputs" / "oracle_observations.csv",
        "reference": strict / "frozen_inputs" / "event_reference.csv",
        "proxy": strict / "frozen_inputs" / "public_proxy.csv",
    }
    raw_units = pd.read_csv(paths["units"])
    units = standard_units(
        "nativecmp_dataset3", "long_video_dataset3", raw_units.unit_id,
        raw_units.start_time, raw_units.end_time,
    )
    raw_proxy = pd.read_csv(
        paths["proxy"], usecols=["unit_id", "proxy_name", "proxy_score_normalized"]
    )
    raw_proxy = raw_proxy[
        raw_proxy.proxy_name.astype(str) == "score_fusion_yolo_motion"
    ].sort_values("unit_id")
    proxy = pd.DataFrame(
        {
            "unit_id": raw_proxy.unit_id.astype(int),
            "proxy_score": raw_proxy.proxy_score_normalized.astype(float),
        }
    )
    raw_oracle = pd.read_csv(paths["oracle"], usecols=["unit_id", "parsed_label"])
    oracle = pd.DataFrame(
        {
            "unit_id": raw_oracle.unit_id.astype(int),
            "oracle_label": raw_oracle.parsed_label.astype(str).str.lower(),
        }
    ).sort_values("unit_id")
    reference = pd.read_csv(paths["reference"])
    reference = reference.copy()
    reference["benchmark_id"] = "nativecmp_dataset3"
    if len(units) != 347 or len(proxy) != len(units) or len(oracle) != len(units):
        raise RuntimeError("dataset3 population mismatch")
    return DomainData(
        "dataset3", "dataset3_development", "long_video_dataset3", (0.0, 3470.0),
        units, proxy, oracle, reference, paths,
    )


def load_realcartest_2000_3200() -> DomainData:
    paths = {
        "grid": REPO / "outputs" / "real_video_protocol_pilot_v1" / "frame_scores_adapter_ready.csv",
        "reference": REPO / "outputs" / "real_video_protocol_pilot_v1" / "reference_segments_adapter_ready.csv",
    }
    grid = pd.read_csv(paths["grid"])
    units = standard_units(
        "nativecmp_realcartest_2000_3200", "realcartest",
        grid.frame_idx, grid.start_time, grid.end_time,
    )
    proxy = pd.DataFrame(
        {"unit_id": grid.frame_idx.astype(int), "proxy_score": grid.proxy_score.astype(float)}
    )
    oracle = pd.DataFrame(
        {
            "unit_id": grid.frame_idx.astype(int),
            "oracle_label": np.where(grid.oracle_label.astype(int) > 0, "positive", "negative"),
        }
    )
    events = pd.read_csv(paths["reference"])
    reference = standard_reference(
        "nativecmp_realcartest_2000_3200", "realcartest", events, units,
        "source_event_id", "start_time", "end_time", "event_type",
    )
    if len(units) != 120:
        raise RuntimeError("realcartest_2000_3200 population mismatch")
    return DomainData(
        "realcartest", "realcartest_2000_3200", "realcartest", (2000.0, 3200.0),
        units, proxy, oracle, reference, paths,
    )


def load_realcartest_0_1570() -> DomainData:
    paths = {
        "grid": REPO / "outputs" / "late_aqp_frozen_cross_segment_v1" / "grid_realcartest_0_1570.csv",
        "reference": REPO / "outputs" / "late_aqp_frozen_cross_segment_v1" / "ref_events_realcartest_0_1570.csv",
    }
    grid = pd.read_csv(paths["grid"])
    units = standard_units(
        "nativecmp_realcartest_0_1570", "realcartest",
        grid.bin_idx, grid.t_start, grid.t_end,
    )
    proxy = pd.DataFrame(
        {"unit_id": grid.bin_idx.astype(int), "proxy_score": grid.prior_score_max.astype(float)}
    )
    oracle = pd.DataFrame(
        {
            "unit_id": grid.bin_idx.astype(int),
            "oracle_label": np.where(grid.is_positive.astype(bool), "positive", "negative"),
        }
    )
    events = pd.read_csv(paths["reference"])
    reference = standard_reference(
        "nativecmp_realcartest_0_1570", "realcartest", events, units,
        "event_id", "t_start", "t_end", "event_type",
    )
    if len(units) != 157:
        raise RuntimeError("realcartest_0_1570 population mismatch")
    return DomainData(
        "realcartest", "realcartest_0_1570", "realcartest", (0.0, 1570.0),
        units, proxy, oracle, reference, paths,
    )


def load_domains() -> list[DomainData]:
    return [load_dataset3(), load_realcartest_0_1570(), load_realcartest_2000_3200()]


def persist_frozen_inputs(domains: list[DomainData], root: Path) -> dict[str, dict[str, Path]]:
    input_root = root / "frozen_inputs"
    input_root.mkdir(parents=True, exist_ok=True)
    paths: dict[str, dict[str, Path]] = {}
    for data in domains:
        domain_root = input_root / data.domain
        domain_root.mkdir(parents=True, exist_ok=True)
        paths[data.domain] = {
            "units": domain_root / "units.csv",
            "proxy": domain_root / "proxy_only.csv",
            "oracle": domain_root / "oracle_labels.csv",
            "reference": domain_root / "reference_events.csv",
        }
        data.units.to_csv(paths[data.domain]["units"], index=False)
        data.proxy[["unit_id", "proxy_score"]].to_csv(paths[data.domain]["proxy"], index=False)
        data.oracle[["unit_id", "oracle_label"]].to_csv(paths[data.domain]["oracle"], index=False)
        data.reference.to_csv(paths[data.domain]["reference"], index=False)
    return paths


def make_manifest(
    domains: list[DomainData], frozen_paths: dict[str, dict[str, Path]], root: Path
) -> dict:
    runner = Path(__file__).resolve()
    dataset_rows = []
    for data in domains:
        dataset_rows.append(
            {
                "dataset": data.dataset,
                "domain": data.domain,
                "video_id": data.video_id,
                "absolute_slice_seconds": list(data.absolute_slice_seconds),
                "unit_count": len(data.units),
                "reference_event_count": len(data.reference),
                "frozen_files": {
                    key: {"path": str(path.relative_to(REPO)), "sha256": sha256_file(path)}
                    for key, path in frozen_paths[data.domain].items()
                },
                "raw_sources": {
                    key: {"path": str(path.relative_to(REPO)), "sha256": sha256_file(path)}
                    for key, path in data.raw_sources.items()
                },
            }
        )
    lodo = pd.read_csv(PSTR_LODO)
    lodo_selected = {
        row.heldout_domain: float(row.selected_overhead) for row in lodo.itertuples()
    }
    lodo_aliases = {"realcartest_0_1570": "confirmatory"}
    if any(
        not math.isclose(lodo_selected[lodo_aliases.get(data.domain, data.domain)], 0.25)
        for data in domains
    ):
        raise RuntimeError("included domains do not share the frozen LODO PSTR overhead 0.25")
    return {
        "schema_version": "native_arc_vs_pstr_v1",
        "frozen_utc": utc_now(),
        "frozen_before_method_execution": True,
        "research_status": "EXPLORATORY_POSTHOC_OPEN_LABEL_REPLAY",
        "objective": "Compare full native ARC and native PSTR; use shared K3 only as a mechanism control.",
        "budgets": BUDGETS,
        "seeds": SEEDS,
        "datasets": dataset_rows,
        "oracle_cost": {
            "definition": "one first access to one unique ten-second unit label equals one logical exact-oracle call",
            "same_for_arc_and_pstr": True,
            "upper_bound_rule": "exact_oracle_calls <= budget",
            "duplicate_queries_forbidden": True,
        },
        "arc": {
            "configuration": ARC_CONFIG,
            "source_files": {
                str(path.relative_to(REPO)): sha256_file(path)
                for path in [
                    ARC_ROOT / "arc.py",
                    ARC_ROOT / "refinement_phase.py",
                    ARC_ROOT / "pruning_phase.py",
                    ARC_ROOT / "tools.py",
                    ARC_ADAPTER,
                ]
            },
            "native_output_version": "arc_native_candidate_clips_with_exposed_native_confidence_v1",
            "adaptation_warning": (
                "Original ARC CDF features are unavailable on these videos. The native ARC "
                "change-point clustering algorithm is applied to [1-public_proxy, public_proxy]."
            ),
        },
        "pstr": {
            "method_id": "pstr_5_to_4",
            "cell_overhead": 0.25,
            "selection_rule": "M=min(n,B+floor(B/4)); best proxy unit per temporal cell; top B winners",
            "selection_policy_frozen": True,
            "parameter_source": "five-domain leave-one-domain-out development replay",
            "parameter_source_path": str(PSTR_LODO.relative_to(REPO)),
            "parameter_source_sha256": sha256_file(PSTR_LODO),
            "sealer_path": str(PSTR_SEALER.relative_to(REPO)),
            "sealer_sha256": sha256_file(PSTR_SEALER),
            "posthoc_warning": (
                "All included target domains were open before PSTR was proposed; LODO reduces "
                "same-domain tuning but is not prospective or cross-video-independent."
            ),
        },
        "native_materializers": {
            "native_arc": "ARC cand_clips, ARC boundaries, and ARC per-candidate confidence",
            "native_pstr": {
                "name": "pstr_native_minimal_materializer",
                "version": "v1",
                "rule": "one exact unit-boundary event per queried-positive unit; no merging or bridging",
                "reason": "PSTR has no independent repository-native clip materializer",
            },
        },
        "shared_k3": {
            "name": "k3_bridge_safe",
            "configuration": K3_CONFIG,
            "implementation_path": str(BENCHMARK_LIB.relative_to(REPO)),
            "implementation_sha256": sha256_file(BENCHMARK_LIB),
            "terminal_only": True,
            "arc_exact_fill": False,
        },
        "evaluator": {
            "version": "benchmark_lib overlap-any one-to-one Hungarian matching",
            "path": str(BENCHMARK_LIB.relative_to(REPO)),
            "sha256": sha256_file(BENCHMARK_LIB),
            "matching_rule": "maximize overlap cardinality, then temporal IoU; one prediction and one reference at most once",
            "tiou_denominator": "reference event count",
        },
        "runner": {"path": str(runner.relative_to(REPO)), "sha256": sha256_file(runner)},
        "statistical_plan": {
            "pairing": "domain x video x ARC seed x budget; deterministic PSTR repeated only to form ARC-seed pairs",
            "bootstrap_seed": 20260713,
            "bootstrap_resamples": 10000,
            "bootstrap_unit": "independent source video after seed and within-video-domain averaging",
            "permutation_unit": "independent source video",
            "multiple_comparison_correction": "Holm within comparison and metric across six budgets",
            "power_rule": "fewer than five independent source videos => statistical_power_insufficient",
        },
        "decision_rule": {
            "pstr_superior": (
                "native recall AUC significantly higher, native precision AUC not significantly lower, "
                "recall no lower at most budgets, and no single-domain dominance"
            ),
            "arc_superior": "symmetric rule",
            "otherwise": "BUDGET_DEPENDENT or INCONCLUSIVE per preregistered conditions",
            "forced_status_for_posthoc_or_low_power": "INCONCLUSIVE",
        },
        "output_root": str(root.relative_to(REPO)),
    }


def seal_pstr(domains: list[DomainData], frozen_paths: dict[str, dict[str, Path]], root: Path) -> None:
    for data in domains:
        output = root / "sealed_pstr" / data.domain
        command = [
            sys.executable,
            str(PSTR_SEALER),
            "--proxy-input",
            str(frozen_paths[data.domain]["proxy"]),
            "--protocol",
            str(PSTR_PROTOCOL),
            "--output",
            str(output),
            "--budgets",
            ",".join(map(str, BUDGETS)),
            "--execute",
        ]
        completed = subprocess.run(command, cwd=REPO, text=True, capture_output=True)
        if completed.returncode != 0:
            raise RuntimeError(
                f"PSTR seal failed for {data.domain}\nstdout={completed.stdout}\nstderr={completed.stderr}"
            )


class OracleTracker:
    """Unique-unit oracle accessor exposed to ARC only through __getitem__."""

    def __init__(self, labels: np.ndarray):
        self._labels = np.asarray(labels, dtype=int)
        self.calls: list[int] = []
        self._seen: set[int] = set()

    def read(self, unit_id: int) -> int:
        unit_id = int(unit_id)
        if unit_id not in self._seen:
            self._seen.add(unit_id)
            self.calls.append(unit_id)
        return int(self._labels[unit_id])


class OraclePosterior:
    def __init__(self, tracker: OracleTracker):
        self.tracker = tracker

    def __getitem__(self, index):
        if np.isscalar(index):
            label = self.tracker.read(int(index))
            return np.asarray([1 - label, label], dtype=float)
        indices = np.asarray(index)
        labels = np.asarray([self.tracker.read(int(i)) for i in indices.ravel()], dtype=int)
        return np.column_stack((1 - labels, labels)).reshape((*indices.shape, 2)).astype(float)


class OracleBinary:
    def __init__(self, tracker: OracleTracker):
        self.tracker = tracker

    def __getitem__(self, index):
        if np.isscalar(index):
            return self.tracker.read(int(index))
        indices = np.asarray(index)
        return np.asarray([self.tracker.read(int(i)) for i in indices.ravel()], dtype=int).reshape(indices.shape)


def trace_frame(
    selected: list[int], data: DomainData, reason: str
) -> pd.DataFrame:
    labels = data.oracle.set_index("unit_id").oracle_label.astype(str)
    scores = data.proxy.set_index("unit_id").proxy_score.astype(float)
    columns = [
        "call_idx", "unit_id", "oracle_label_after_query", "proxy_score", "selection_reason"
    ]
    return pd.DataFrame(
        [
            {
                "call_idx": rank - 1,
                "unit_id": unit_id,
                "oracle_label_after_query": labels.loc[unit_id],
                "proxy_score": scores.loc[unit_id],
                "selection_reason": reason,
            }
            for rank, unit_id in enumerate(selected, 1)
        ],
        columns=columns,
    )


def arc_clusters(data: DomainData, root: Path) -> np.ndarray:
    scores = np.clip(data.proxy.sort_values("unit_id").proxy_score.to_numpy(float), 0.0, 1.0)
    distributions = np.column_stack((1.0 - scores, scores))
    labels = perform_clustering(
        distributions,
        ARC_CONFIG["cluster_threshold"],
        data.domain,
        str(root / "arc_clusters"),
    )
    clusters = labels.iloc[:, 0].astype(int).to_numpy()
    if len(clusters) != len(data.units) or clusters[0] != 0 or np.any(np.diff(clusters) < 0):
        raise RuntimeError(f"invalid ARC clusters for {data.domain}")
    return clusters


def run_arc_selector(
    data: DomainData, clusters: np.ndarray, seed: int, budget: int
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray, dict]:
    public_scores = np.clip(
        data.proxy.sort_values("unit_id").proxy_score.to_numpy(float), 0.0, 1.0
    )
    proxy = np.column_stack((1.0 - public_scores, public_scores))
    proxy_binary = (public_scores >= ARC_CONFIG["proxy_threshold"]).astype(int)
    initial = findCandClips(proxy_binary, ">", 0, ARC_CONFIG["tau_units"])
    labels = (
        data.oracle.sort_values("unit_id").oracle_label.astype(str).str.lower() == "positive"
    ).astype(int).to_numpy()
    tracker = OracleTracker(labels)
    np.random.seed(seed)
    if len(initial) == 0:
        result = {
            "cand_clips": initial,
            "cand_clip_confidences": np.asarray([], dtype=float),
            "tau_confidence": math.nan,
            "B": 0,
            "tc_enabled": True,
        }
    else:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = original_arc(
                proxy=proxy,
                oracle=OraclePosterior(tracker),
                proxy_score=proxy_binary.copy(),
                oracle_score=OracleBinary(tracker),
                B=budget + 1,
                op=">",
                constant=0,
                tau=ARC_CONFIG["tau_units"],
                confidence=ARC_CONFIG["confidence"],
                IOUThreshold=ARC_CONFIG["iou_threshold"],
                clusters=clusters,
                startup_sampling_rate=ARC_CONFIG["startup_sampling_rate"],
                tc_enabled=True,
                ps_enabled=True,
                lp_enabled=True,
            )
    if len(tracker.calls) > budget or len(tracker.calls) != len(set(tracker.calls)):
        raise RuntimeError(f"ARC oracle audit failed {data.domain} seed={seed} B={budget}")
    trace = trace_frame(tracker.calls, data, "arc_progressive_sampling_label_propagation")
    return (
        trace,
        np.asarray(result["cand_clips"], dtype=int).reshape(-1, 2),
        np.asarray(result["cand_clip_confidences"], dtype=float),
        result,
    )


def native_arc_predictions(
    data: DomainData,
    trace: pd.DataFrame,
    clips: np.ndarray,
    confidences: np.ndarray,
    meta: dict,
) -> pd.DataFrame:
    unit_map = data.units.set_index("unit_id")
    positives = set(
        trace.loc[
            trace.oracle_label_after_query.astype(str).str.lower() == "positive", "unit_id"
        ].astype(int)
    )
    negatives = set(
        trace.loc[
            trace.oracle_label_after_query.astype(str).str.lower() == "negative", "unit_id"
        ].astype(int)
    )
    cfg_hash = canonical_hash({"name": "arc_native_candidate_clips", **ARC_CONFIG})
    rows = []
    for index, (left, right) in enumerate(clips):
        ids = list(range(int(left), int(right) + 1))
        start = float(unit_map.loc[int(left), "start_time"])
        end = float(unit_map.loc[int(right), "end_time"])
        confidence = float(confidences[index]) if index < len(confidences) else math.nan
        rows.append(
            {
                **meta,
                "event_id": f"{meta['run_id']}_event_{index:04d}",
                "start_time": start,
                "core_start_time": start,
                "core_end_time": end,
                "end_time": end,
                "anchor_unit_ids": "|".join(map(str, sorted(set(ids) & positives))),
                "evidence_unit_ids": "|".join(map(str, ids)),
                "num_positive_anchors": len(set(ids) & positives),
                "num_negative_barriers": len(set(ids) & negatives),
                "verification_state": "arc_native_mixed",
                "confidence": confidence,
                "returned_seconds": end - start,
                "materializer": "arc_native_candidate_clips",
                "materializer_config_hash": cfg_hash,
            }
        )
    return pd.DataFrame(rows, columns=BENCH.EVENT_SEGMENT_COLUMNS)


def native_pstr_predictions(
    data: DomainData, trace: pd.DataFrame, meta: dict
) -> pd.DataFrame:
    units = data.units.set_index("unit_id")
    scores = data.proxy.set_index("unit_id").proxy_score.astype(float)
    positive_ids = trace.loc[
        trace.oracle_label_after_query.astype(str).str.lower() == "positive", "unit_id"
    ].astype(int).tolist()
    cfg = {
        "name": "pstr_native_minimal_materializer",
        "version": "v1",
        "merge": False,
        "boundary": "exact selected unit",
    }
    rows = []
    for index, unit_id in enumerate(positive_ids):
        start = float(units.loc[unit_id, "start_time"])
        end = float(units.loc[unit_id, "end_time"])
        rows.append(
            {
                **meta,
                "event_id": f"{meta['run_id']}_event_{index:04d}",
                "start_time": start,
                "core_start_time": start,
                "core_end_time": end,
                "end_time": end,
                "anchor_unit_ids": str(unit_id),
                "evidence_unit_ids": str(unit_id),
                "num_positive_anchors": 1,
                "num_negative_barriers": 0,
                "verification_state": "oracle_confirmed",
                "confidence": float(scores.loc[unit_id]),
                "returned_seconds": end - start,
                "materializer": "pstr_native_minimal_materializer",
                "materializer_config_hash": canonical_hash(cfg),
            }
        )
    return pd.DataFrame(rows, columns=BENCH.EVENT_SEGMENT_COLUMNS)


def method_meta(data: DomainData, method: str, variant: str, seed: int, budget: int) -> dict:
    safe_domain = data.domain.replace("/", "_")
    return {
        "benchmark_id": data.benchmark_id,
        "run_id": f"{safe_domain}_{method}_s{seed:03d}_b{budget}",
        "method": method,
        "method_variant": variant,
        "seed": seed,
        "horizon_budget": budget,
    }


def save_run(
    data: DomainData,
    method: str,
    variant: str,
    seed: int,
    budget: int,
    trace: pd.DataFrame,
    predicted: pd.DataFrame,
    evaluator_hash: str,
    root: Path,
    state: dict | None = None,
) -> dict:
    run_dir = root / "runs" / data.domain / method / f"seed_{seed:03d}" / f"budget_{budget}"
    run_dir.mkdir(parents=True, exist_ok=True)
    trace_path = run_dir / "selection_trace.csv"
    oracle_path = run_dir / "oracle_log.csv"
    prediction_path = run_dir / "predictions.csv"
    match_path = run_dir / "event_matches.csv"
    trace.to_csv(trace_path, index=False)
    trace[["call_idx", "unit_id", "oracle_label_after_query"]].to_csv(oracle_path, index=False)
    predicted.to_csv(prediction_path, index=False)
    meta = method_meta(data, method, variant, seed, budget)
    matches, metrics = BENCH.evaluate_events(predicted, data.reference, meta, evaluator_hash)
    matches.to_csv(match_path, index=False)
    if state is not None:
        write_json(run_dir / "native_state.json", state)
    metric_map = dict(zip(metrics.metric_name.astype(str), metrics.metric_value.astype(float)))
    return {
        "dataset": data.dataset,
        "domain": data.domain,
        "video_id": data.video_id,
        "method": method,
        "method_variant": variant,
        "seed": seed,
        "budget": budget,
        "exact_oracle_calls": len(trace),
        **{name: float(metric_map[name]) for name in METRICS},
        "selection_trace_path": str(trace_path.relative_to(REPO)),
        "prediction_path": str(prediction_path.relative_to(REPO)),
        "oracle_log_path": str(oracle_path.relative_to(REPO)),
        "materializer": (
            str(predicted.materializer.iloc[0]) if len(predicted) else {
                "native_arc": "arc_native_candidate_clips",
                "native_pstr": "pstr_native_minimal_materializer",
                "arc_shared_k3": "k3_bridge_safe",
                "pstr_shared_k3": "k3_bridge_safe",
            }[method]
        ),
        "evaluator_hash": evaluator_hash,
    }


def load_sealed_pstr(data: DomainData, budget: int, root: Path) -> list[int]:
    sealed = pd.read_csv(root / "sealed_pstr" / data.domain / "sealed_selections.csv")
    rows = sealed[sealed.budget.astype(int) == budget].sort_values("selection_rank")
    selected = rows.unit_id.astype(int).tolist()
    if len(selected) != budget or len(selected) != len(set(selected)):
        raise RuntimeError(f"invalid PSTR seal {data.domain} B={budget}")
    return selected


def execute(domains: list[DomainData], root: Path, evaluator_hash: str) -> pd.DataFrame:
    rows = []
    clusters = {data.domain: arc_clusters(data, root) for data in domains}
    for data in domains:
        for seed in SEEDS:
            for budget in BUDGETS:
                arc_trace, clips, confidences, arc_state = run_arc_selector(
                    data, clusters[data.domain], seed, budget
                )
                arc_native_meta = method_meta(
                    data, "native_arc", "arc_native_clustered_posterior_v1", seed, budget
                )
                native_arc = native_arc_predictions(
                    data, arc_trace, clips, confidences, arc_native_meta
                )
                rows.append(
                    save_run(
                        data, "native_arc", "arc_native_clustered_posterior_v1", seed,
                        budget, arc_trace, native_arc, evaluator_hash, root,
                        state={
                            "candidate_clips": clips.tolist(),
                            "candidate_clip_confidences": confidences.tolist(),
                            "tau_confidence": float(arc_state.get("tau_confidence", math.nan)),
                            "arc_reported_B": int(arc_state.get("B", len(arc_trace))),
                            "cluster_count": int(len(np.unique(clusters[data.domain]))),
                            "query_trace_is_pre_materialization": True,
                        },
                    )
                )
                arc_shared_meta = method_meta(
                    data, "arc_shared_k3", "native_arc_trace_terminal_k3", seed, budget
                )
                arc_shared = BENCH.materialize_from_trace(
                    arc_trace, data.units, arc_shared_meta, "k3_bridge_safe", K3_CONFIG
                )
                rows.append(
                    save_run(
                        data, "arc_shared_k3", "native_arc_trace_terminal_k3", seed,
                        budget, arc_trace, arc_shared, evaluator_hash, root,
                    )
                )

                pstr_selected = load_sealed_pstr(data, budget, root)
                pstr_trace = trace_frame(pstr_selected, data, "sealed_label_blind_pstr_5_to_4")
                pstr_native_meta = method_meta(
                    data, "native_pstr", "pstr_native_minimal_materializer", seed, budget
                )
                native_pstr = native_pstr_predictions(data, pstr_trace, pstr_native_meta)
                rows.append(
                    save_run(
                        data, "native_pstr", "pstr_native_minimal_materializer", seed,
                        budget, pstr_trace, native_pstr, evaluator_hash, root,
                    )
                )
                pstr_shared_meta = method_meta(
                    data, "pstr_shared_k3", "pstr_5_to_4_terminal_k3", seed, budget
                )
                pstr_shared = BENCH.materialize_from_trace(
                    pstr_trace, data.units, pstr_shared_meta, "k3_bridge_safe", K3_CONFIG
                )
                rows.append(
                    save_run(
                        data, "pstr_shared_k3", "pstr_5_to_4_terminal_k3", seed,
                        budget, pstr_trace, pstr_shared, evaluator_hash, root,
                    )
                )
    return pd.DataFrame(rows)


def paired_rows(per_run: pd.DataFrame, comparison: str, arc: str, pstr: str) -> pd.DataFrame:
    keys = ["dataset", "domain", "video_id", "seed", "budget"]
    left = per_run[per_run.method == arc].set_index(keys)
    right = per_run[per_run.method == pstr].set_index(keys)
    if not left.index.equals(right.index):
        raise RuntimeError(f"unpaired comparison {comparison}")
    rows = []
    for key in left.index:
        a = left.loc[key]
        p = right.loc[key]
        rows.append(
            {
                **dict(zip(keys, key)),
                "comparison": comparison,
                "method_arc": arc,
                "method_pstr": pstr,
                "precision_arc": float(a.event_precision),
                "precision_pstr": float(p.event_precision),
                "recall_arc": float(a.event_recall),
                "recall_pstr": float(p.event_recall),
                "f1_arc": float(a.event_f1),
                "f1_pstr": float(p.event_f1),
                "delta_precision": float(p.event_precision - a.event_precision),
                "delta_recall": float(p.event_recall - a.event_recall),
                "delta_f1": float(p.event_f1 - a.event_f1),
            }
        )
    return pd.DataFrame(rows)


def source_video_deltas(pair: pd.DataFrame, delta_column: str) -> pd.Series:
    # Seeds are repeated stochastic trials, not independent videos. Domains from
    # the same source video are averaged before any inferential resampling.
    domain_seed_mean = pair.groupby(
        ["dataset", "video_id", "domain", "seed"], as_index=False
    )[delta_column].mean()
    domain_mean = domain_seed_mean.groupby(
        ["dataset", "video_id", "domain"], as_index=False
    )[delta_column].mean()
    return domain_mean.groupby(["dataset", "video_id"])[delta_column].mean()


def bootstrap_ci(values: np.ndarray, seed: int, resamples: int = 10000) -> tuple[float, float]:
    if len(values) == 0:
        return math.nan, math.nan
    rng = np.random.default_rng(seed)
    draws = values[rng.integers(0, len(values), size=(resamples, len(values)))].mean(axis=1)
    return float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))


def permutation_p(values: np.ndarray) -> float:
    if len(values) == 0:
        return math.nan
    observed = abs(float(np.mean(values)))
    signs = np.asarray(list(itertools.product([-1.0, 1.0], repeat=len(values))))
    null = np.abs((signs * values).mean(axis=1))
    return float(np.mean(null >= observed - 1e-15))


def holm_adjust(pvalues: pd.Series) -> pd.Series:
    values = pvalues.astype(float).to_numpy()
    order = np.argsort(values)
    adjusted = np.empty(len(values), dtype=float)
    running = 0.0
    m = len(values)
    for rank, index in enumerate(order):
        running = max(running, (m - rank) * values[index])
        adjusted[index] = min(1.0, running)
    return pd.Series(adjusted, index=pvalues.index)


def pair_summary(per_run: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    specs = [
        ("native_arc_vs_native_pstr", "native_arc", "native_pstr"),
        ("arc_shared_k3_vs_pstr_shared_k3", "arc_shared_k3", "pstr_shared_k3"),
        ("native_arc_vs_arc_shared_k3", "native_arc", "arc_shared_k3"),
        ("native_pstr_vs_pstr_shared_k3", "native_pstr", "pstr_shared_k3"),
    ]
    required_pairs = []
    summary_rows = []
    for comparison, left_method, right_method in specs:
        pair = paired_rows(per_run, comparison, left_method, right_method)
        if comparison in {
            "native_arc_vs_native_pstr", "arc_shared_k3_vs_pstr_shared_k3"
        }:
            required_pairs.append(pair)
        for budget in BUDGETS:
            budget_pair = pair[pair.budget == budget]
            for metric, delta in [
                ("event_precision", "delta_precision"),
                ("event_recall", "delta_recall"),
                ("event_f1", "delta_f1"),
            ]:
                # A source video can contribute multiple disjoint domains. Keep
                # all domain-level pairs in paired_deltas.csv, but give each
                # source-video/seed pair one descriptive vote here.
                values = (
                    budget_pair.groupby(["dataset", "video_id", "seed"])[delta]
                    .mean()
                    .to_numpy(float)
                )
                independent = source_video_deltas(budget_pair, delta).to_numpy(float)
                ci_low, ci_high = bootstrap_ci(
                    independent, 20260713 + 101 * BUDGETS.index(budget) + len(summary_rows)
                )
                summary_rows.append(
                    {
                        "summary_type": "paired_comparison",
                        "comparison": comparison,
                        "left_method": left_method,
                        "right_method": right_method,
                        "budget": budget,
                        "metric": metric,
                        "paired_mean_difference": float(np.mean(values)),
                        "paired_median_difference": float(np.median(values)),
                        "bootstrap_ci_low": ci_low,
                        "bootstrap_ci_high": ci_high,
                        "permutation_p_raw": permutation_p(independent),
                        "right_win_proportion_video_seed": float(np.mean(values > 1e-15)),
                        "left_win_proportion_video_seed": float(np.mean(values < -1e-15)),
                        "ties": int(np.sum(np.isclose(values, 0.0, atol=1e-15))),
                        "num_video_seed_pairs": len(values),
                        "num_independent_source_videos": len(independent),
                        "resampling_unit": "source_video",
                        "statistical_power_insufficient": len(independent) < 5,
                    }
                )
    summary = pd.DataFrame(summary_rows)
    summary["permutation_p_holm"] = math.nan
    for _, indices in summary.groupby(["comparison", "metric"]).groups.items():
        summary.loc[indices, "permutation_p_holm"] = holm_adjust(
            summary.loc[indices, "permutation_p_raw"]
        )
    return pd.concat(required_pairs, ignore_index=True), summary


def method_summary(per_run: pd.DataFrame) -> pd.DataFrame:
    columns = ["exact_oracle_calls", *METRICS]
    grouped = per_run.groupby(
        ["dataset", "domain", "video_id", "method", "method_variant", "budget"],
        dropna=False,
    )[columns].agg(["mean", "std", "min", "max"]).reset_index()
    grouped.columns = [
        "_".join(str(part) for part in col if part).rstrip("_")
        if isinstance(col, tuple)
        else col
        for col in grouped.columns
    ]
    grouped.insert(0, "summary_type", "method")
    return grouped


def auc_table(per_run: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (dataset, domain, method), group in per_run.groupby(["dataset", "domain", "method"]):
        curve = group.groupby("budget")[PRIMARY_METRICS].mean().reindex(BUDGETS)
        if curve.isna().any().any():
            raise RuntimeError(f"incomplete AUC curve {domain}/{method}")
        budgets = np.asarray(BUDGETS, dtype=float)
        denom = budgets[-1] - budgets[0]
        rows.append(
            {
                "method": method,
                "dataset": dataset,
                "domain": domain,
                "precision_auc": float(np.trapezoid(curve.event_precision, budgets) / denom),
                "recall_auc": float(np.trapezoid(curve.event_recall, budgets) / denom),
                "f1_auc": float(np.trapezoid(curve.event_f1, budgets) / denom),
                "budget_grid": "|".join(map(str, BUDGETS)),
                "num_runs": len(group),
            }
        )
    return pd.DataFrame(rows).sort_values(["dataset", "domain", "method"])


def macro_curve(per_run: pd.DataFrame) -> pd.DataFrame:
    # Average seeds within domain, then domains within source video, then videos.
    per_domain = per_run.groupby(
        ["dataset", "video_id", "domain", "method", "budget"], as_index=False
    )[PRIMARY_METRICS].mean()
    per_video = per_domain.groupby(
        ["dataset", "video_id", "method", "budget"], as_index=False
    )[PRIMARY_METRICS].mean()
    return per_video.groupby(["method", "budget"], as_index=False)[PRIMARY_METRICS].mean()


def macro_auc(per_run: pd.DataFrame) -> pd.DataFrame:
    curve = macro_curve(per_run)
    rows = []
    x = np.asarray(BUDGETS, dtype=float)
    for method, group in curve.groupby("method"):
        group = group.set_index("budget").reindex(BUDGETS)
        rows.append(
            {
                "method": method,
                "precision_auc": float(np.trapezoid(group.event_precision, x) / 95.0),
                "recall_auc": float(np.trapezoid(group.event_recall, x) / 95.0),
                "f1_auc": float(np.trapezoid(group.event_f1, x) / 95.0),
            }
        )
    return pd.DataFrame(rows).set_index("method")


def verify(
    per_run: pd.DataFrame,
    domains: list[DomainData],
    manifest: dict,
    evaluator_hash: str,
    root: Path,
) -> dict:
    checks = []

    def record(name: str, passed: bool, details: object) -> None:
        checks.append({"check": name, "passed": bool(passed), "details": details})
        if not passed:
            raise RuntimeError(f"verification failed: {name}: {details}")

    required = {"native_arc", "native_pstr", "arc_shared_k3", "pstr_shared_k3"}
    expected_per_method = len(domains) * len(SEEDS) * len(BUDGETS)
    counts = per_run.groupby("method").size().to_dict()
    record(
        "method_and_budget_run_counts",
        set(counts) == required and all(counts[m] == expected_per_method for m in required),
        counts,
    )
    record(
        "budget_upper_bound",
        bool((per_run.exact_oracle_calls.astype(int) <= per_run.budget.astype(int)).all()),
        {"max_excess": int((per_run.exact_oracle_calls - per_run.budget).max())},
    )
    pstr = per_run[per_run.method.isin(["native_pstr", "pstr_shared_k3"])]
    record(
        "pstr_exact_budget",
        bool((pstr.exact_oracle_calls.astype(int) == pstr.budget.astype(int)).all()),
        {"rows": len(pstr)},
    )
    duplicate_failures = []
    missing_files = []
    for row in per_run.itertuples(index=False):
        for attr in ["selection_trace_path", "prediction_path", "oracle_log_path"]:
            path = REPO / getattr(row, attr)
            if not path.exists():
                missing_files.append(str(path))
        trace = pd.read_csv(REPO / row.selection_trace_path)
        if trace.unit_id.astype(int).duplicated().any():
            duplicate_failures.append(row.selection_trace_path)
    record("file_integrity", not missing_files, missing_files)
    record("duplicate_query_check", not duplicate_failures, duplicate_failures)

    expected_materializer = {
        "native_arc": "arc_native_candidate_clips",
        "native_pstr": "pstr_native_minimal_materializer",
        "arc_shared_k3": "k3_bridge_safe",
        "pstr_shared_k3": "k3_bridge_safe",
    }
    bad_materializers = per_run[
        per_run.apply(lambda r: r.materializer != expected_materializer[r.method], axis=1)
    ]
    record(
        "native_shared_materializer_separation",
        bad_materializers.empty,
        bad_materializers[["method", "materializer"]].to_dict("records"),
    )
    record(
        "evaluator_hash",
        bool((per_run.evaluator_hash.astype(str) == evaluator_hash).all()),
        evaluator_hash,
    )

    trace_mismatches = []
    for domain in [d.domain for d in domains]:
        for seed in SEEDS:
            for budget in BUDGETS:
                subset = per_run[
                    (per_run.domain == domain) & (per_run.seed == seed) & (per_run.budget == budget)
                ].set_index("method")
                for left, right in [
                    ("native_arc", "arc_shared_k3"),
                    ("native_pstr", "pstr_shared_k3"),
                ]:
                    a = sha256_file(REPO / subset.loc[left, "selection_trace_path"])
                    b = sha256_file(REPO / subset.loc[right, "selection_trace_path"])
                    if a != b:
                        trace_mismatches.append([domain, seed, budget, left, right])
    record("native_shared_identical_selection_trace", not trace_mismatches, trace_mismatches)

    domain_map = {data.domain: data for data in domains}
    metric_failures = []
    for row in per_run.itertuples(index=False):
        data = domain_map[row.domain]
        predicted = pd.read_csv(REPO / row.prediction_path)
        meta = method_meta(data, row.method, row.method_variant, row.seed, row.budget)
        _, recomputed = BENCH.evaluate_events(predicted, data.reference, meta, evaluator_hash)
        values = dict(zip(recomputed.metric_name.astype(str), recomputed.metric_value.astype(float)))
        for metric in METRICS:
            expected = float(getattr(row, metric))
            actual = float(values[metric])
            equal = (math.isnan(expected) and math.isnan(actual)) or math.isclose(
                expected, actual, rel_tol=1e-12, abs_tol=1e-12
            )
            if not equal:
                metric_failures.append([row.domain, row.method, row.seed, row.budget, metric])
    record("prediction_metric_recomputation", not metric_failures, metric_failures[:20])

    summary_failures = []
    try:
        observed_auc = pd.read_csv(root / "auc_summary.csv")
        pd.testing.assert_frame_equal(
            observed_auc.reset_index(drop=True),
            auc_table(per_run).reset_index(drop=True),
            check_dtype=False,
            rtol=1e-12,
            atol=1e-12,
        )
        _, recomputed_pair_stats = pair_summary(per_run)
        recomputed_summary = pd.concat(
            [method_summary(per_run), recomputed_pair_stats], ignore_index=True, sort=False
        )
        observed_summary = pd.read_csv(root / "per_budget_summary.csv")
        pd.testing.assert_frame_equal(
            observed_summary.reset_index(drop=True),
            recomputed_summary.reset_index(drop=True),
            check_dtype=False,
            rtol=1e-12,
            atol=1e-12,
        )
    except (AssertionError, FileNotFoundError) as exc:
        summary_failures.append(str(exc))
    record("summary_and_auc_recomputation", not summary_failures, summary_failures)

    pstr_failures = []
    for data in domains:
        for budget in BUDGETS:
            sealed = load_sealed_pstr(data, budget, root)
            rows = per_run[
                (per_run.domain == data.domain)
                & (per_run.method == "native_pstr")
                & (per_run.budget == budget)
            ]
            for path in rows.selection_trace_path:
                observed = pd.read_csv(REPO / path).sort_values("call_idx").unit_id.astype(int).tolist()
                if observed != sealed:
                    pstr_failures.append([data.domain, budget, path])
    record("pstr_proxy_only_seal_replay", not pstr_failures, pstr_failures)

    input_hash_failures = []
    for spec in manifest["datasets"]:
        for item in spec["frozen_files"].values():
            if sha256_file(REPO / item["path"]) != item["sha256"]:
                input_hash_failures.append(item["path"])
    record("frozen_input_hashes", not input_hash_failures, input_hash_failures)

    # The ARC code receives labels only through OraclePosterior/OracleBinary;
    # the emitted trace is the tracker's complete first-access order. PSTR is
    # replayed from a sealer that rejects label/reference columns.
    record(
        "no_future_oracle_label_selection",
        not pstr_failures and not duplicate_failures,
        {
            "arc": "audited lazy __getitem__ oracle; trace equals all first accesses",
            "pstr": "proxy-only sealed selections reproduced exactly",
            "prospective_status": False,
        },
    )
    return {
        "status": "PASS" if all(check["passed"] for check in checks) else "FAIL",
        "verified_utc": utc_now(),
        "checks": checks,
        "k3_does_not_affect_arc_query_trace": True,
        "statistical_power_insufficient": len({d.video_id for d in domains}) < 5,
    }


def fmt(value: float) -> str:
    return f"{value:.3f}"


def build_readme(
    per_run: pd.DataFrame,
    pair_stats: pd.DataFrame,
    manifest: dict,
    verification: dict,
) -> str:
    curve = macro_curve(per_run)
    auc = macro_auc(per_run)

    def budget_table(left: str, right: str) -> str:
        lines = [
            "| B | left P/R/F1 | right P/R/F1 | F1 winner |",
            "|---:|---:|---:|:---|",
        ]
        for budget in BUDGETS:
            l = curve[(curve.method == left) & (curve.budget == budget)].iloc[0]
            r = curve[(curve.method == right) & (curve.budget == budget)].iloc[0]
            winner = right if r.event_f1 > l.event_f1 else left if l.event_f1 > r.event_f1 else "tie"
            lines.append(
                f"| {budget} | {fmt(l.event_precision)}/{fmt(l.event_recall)}/{fmt(l.event_f1)} "
                f"| {fmt(r.event_precision)}/{fmt(r.event_recall)}/{fmt(r.event_f1)} | {winner} |"
            )
        return "\n".join(lines)

    auc_lines = [
        "| Method | Precision AUC | Recall AUC | F1 AUC |",
        "|:---|---:|---:|---:|",
    ]
    for method in ["native_arc", "native_pstr", "arc_shared_k3", "pstr_shared_k3"]:
        row = auc.loc[method]
        auc_lines.append(
            f"| {method} | {fmt(row.precision_auc)} | {fmt(row.recall_auc)} | {fmt(row.f1_auc)} |"
        )
    arc_delta = auc.loc["arc_shared_k3"] - auc.loc["native_arc"]
    pstr_delta = auc.loc["pstr_shared_k3"] - auc.loc["native_pstr"]
    native_recall_stats = pair_stats[
        (pair_stats.comparison == "native_arc_vs_native_pstr")
        & (pair_stats.metric == "event_recall")
    ]
    min_holm = float(native_recall_stats.permutation_p_holm.min())

    return f"""# Native ARC vs Native PSTR

## Conclusion

**INCONCLUSIVE.** This replay cannot support `PSTR_SUPERIOR` or `ARC_SUPERIOR`.
Only two independent source videos are represented, all target labels were open
before PSTR was proposed, and native PSTR required a newly specified minimal
materializer. Descriptive differences are therefore mechanism evidence, not a
strict winner claim.

## Systems compared

- `native_arc` runs ARC's native refinement loop with progressive sampling,
  label propagation, candidate-clip boundaries, stopping rule, and exposed
  native candidate confidence. ARC's native sequential Jensen-Shannon
  clustering is used at threshold 0.001 on the available two-class public-proxy
  posterior. Original ARC CDF features were unavailable, so this is an explicit
  adaptation rather than a literal reproduction of the paper datasets.
- `native_pstr` uses frozen PSTR-5:4 selection and
  `pstr_native_minimal_materializer`: every queried-positive unit becomes one
  exact unit-boundary event, with no merging or bridging. PSTR had no existing
  independent native clip materializer; the variant is not presented as
  `pstr_native`.
- `arc_shared_k3` rematerializes the exact native ARC query trace through
  terminal `k3_bridge_safe`.
- `pstr_shared_k3` rematerializes the exact PSTR trace through the same K3.

`native_arc` and `arc_shared_k3` have byte-identical selection traces for every
run. **K3 does not affect ARC query trace.** No proxy-order exact fill is used in
this experiment. Historical BSEC shared-K3 ARC controls did append proxy-ordered
units when ARC stopped short; that behavior is not used here because it would
confound the materializer ablation with extra queries. ARC may therefore use
fewer than B calls; PSTR uses exactly B.

Shared K3 deliberately discards ARC's native candidate-clip boundaries and
confidence; it can materialize only queried-positive anchors. This is especially
consequential on `realcartest_0_1570`: native ARC averages 0.6 calls, returns
seven candidate clips and 1468 seconds at every budget, while `arc_shared_k3`
has no queried-positive anchor and returns no event. Thus the shared comparison
is a selector/query-trace control, not an approximation of native ARC output.

## Frozen and development-derived choices

Budgets are `[5,10,20,50,80,100]`; ARC seeds are `[0,1,2,3,4]`.
ARC threshold 0.4, clustering threshold 0.001, confidence 0.9, unit-scale
`tau=1`, IoU confidence threshold 0.5, and all native refinement switches were
frozen in `manifest.json`. PSTR overhead 0.25 came from the recorded five-domain
leave-one-domain-out development replay. Every included domain was already open,
so the complete study is marked exploratory/post-hoc. No parameter was selected
from the newly generated metrics in this directory.

## Metric definitions

The evaluator performs overlap-any event matching with one-to-one Hungarian
assignment; cardinality is optimized before temporal IoU. Precision is matched
predictions divided by predictions. Recall is matched references divided by
references. F1 is their harmonic mean. `tiou_03` and `tiou_05` divide the number
of matched pairs meeting the threshold by the reference-event count. Selected
positive units are never treated as event recall.

The tables below are source-video macro averages: seeds are averaged within a
domain, the two realcartest domains are averaged within their source video, and
the two source videos then receive equal weight.

## Native full-system comparison

{budget_table("native_arc", "native_pstr")}

The F1-winner column is descriptive, not an overall ranking. At B=5, 10, 20,
and 50, native PSTR has higher precision but lower recall than native ARC, so
the systems are Pareto-incomparable. Native PSTR is higher on both precision
and recall at B=80 and 100. Across the full grid, PSTR has higher precision and
F1 AUC but lower recall AUC; this is a precision/recall tradeoff, not strict
PSTR superiority.

## Shared-K3 selector control

{budget_table("arc_shared_k3", "pstr_shared_k3")}

PSTR is descriptively no lower on both precision and recall at all six shared-K3
budgets. This does not establish selector superiority because the replay is
post-hoc, has two independent videos, and ARC's native stopping policy often
uses fewer oracle calls than PSTR under the same upper-bound budget.

## Normalized AUC on the identical budget grid

{chr(10).join(auc_lines)}

K3 minus native AUC effects for ARC are P={arc_delta.precision_auc:+.3f},
R={arc_delta.recall_auc:+.3f}, F1={arc_delta.f1_auc:+.3f}. For PSTR they are
P={pstr_delta.precision_auc:+.3f}, R={pstr_delta.recall_auc:+.3f},
F1={pstr_delta.f1_auc:+.3f}. These quantify terminal materialization effects;
they do not imply causal generalization beyond the two videos.

## Statistical interpretation

Paired rows are saved for every domain/video/seed/budget. Bootstrap and
permutation inference first averages stochastic seeds, then averages domains
from the same source video, and resamples the source video. There are only two
independent source videos, so every budget is flagged
`statistical_power_insufficient`. Holm correction is applied across the six
budgets within each comparison and metric. The smallest Holm-adjusted p-value
for the native recall comparisons is {min_holm:.3f}; no significance claim is
made.

## Evidence, competing explanation, and revision trigger

The strongest supported conclusion is that native output logic materially
changes both systems' precision/recall profiles, so shared-K3 selector results
cannot answer the full-system question. A major competing explanation is
source-specific proxy/time regularity combined with post-hoc PSTR development.
The key uncertainty is prospective cross-video behavior with human references.
The next high-value action is the already frozen external protocol: at least five
independently sourced videos, proxy-only sealing before labels, and human
adjudication. This `INCONCLUSIVE` conclusion should be revised only if that
independent native, paired experiment satisfies the preregistered AUC and
precision-noninferiority rules.

## Verification

`verification.json` reports `{verification['status']}` for file completeness,
run counts, budget limits, duplicate queries, materializer separation,
evaluator hash, metric and summary recomputation from predictions, input hashes,
trace identity, and proxy-only PSTR seal replay.
"""


def artifact_manifest(root: Path) -> pd.DataFrame:
    rows = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "artifact_manifest.csv":
            rows.append(
                {
                    "path": str(path.relative_to(REPO)),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    root = args.output.resolve()
    if root.exists() and any(root.iterdir()):
        if not args.overwrite:
            raise SystemExit(f"refusing to overwrite nonempty output: {root}")
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    domains = load_domains()
    frozen_paths = persist_frozen_inputs(domains, root)
    manifest = make_manifest(domains, frozen_paths, root)
    write_json(root / "manifest.json", manifest)
    seal_pstr(domains, frozen_paths, root)

    evaluator_hash = sha256_file(BENCHMARK_LIB)
    per_run = execute(domains, root, evaluator_hash)
    per_run = per_run.sort_values(["dataset", "domain", "method", "seed", "budget"])
    per_run.to_csv(root / "per_run_metrics.csv", index=False)

    paired, pair_stats = pair_summary(per_run)
    paired.to_csv(root / "paired_deltas.csv", index=False)
    pd.concat([method_summary(per_run), pair_stats], ignore_index=True, sort=False).to_csv(
        root / "per_budget_summary.csv", index=False
    )
    auc_table(per_run).to_csv(root / "auc_summary.csv", index=False)

    verification = verify(per_run, domains, manifest, evaluator_hash, root)
    (root / "README.md").write_text(
        build_readme(per_run, pair_stats, manifest, verification), encoding="utf-8"
    )
    required_root_files = [
        "manifest.json",
        "per_run_metrics.csv",
        "per_budget_summary.csv",
        "paired_deltas.csv",
        "auc_summary.csv",
        "README.md",
    ]
    missing_required = [name for name in required_root_files if not (root / name).is_file()]
    verification["checks"].append(
        {
            "check": "required_root_deliverables",
            "passed": not missing_required,
            "details": missing_required,
        }
    )
    if missing_required:
        raise RuntimeError(f"missing required deliverables: {missing_required}")
    write_json(root / "verification.json", verification)
    artifact_manifest(root).to_csv(root / "artifact_manifest.csv", index=False)
    print(
        json.dumps(
            {
                "status": "INCONCLUSIVE",
                "per_run_rows": len(per_run),
                "verification": verification["status"],
                "output": str(root),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
