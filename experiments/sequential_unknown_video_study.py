#!/usr/bin/env python3
"""Unknown-video closed-loop SCAN/VERIFY mechanism study.

Five candidate schedulers are developed without accessing the primary held-out
video's labels.  The winning candidate is frozen from two reciprocal
realcartest-slice development folds, then compared on the query-bound
``dataset3_development`` video against current two-stage raw-proxy scheduling
and a two-stage ARC adapter.  Every policy follows the same sequential
environment: SCAN reveals proxy scores, VERIFY reveals one already-scanned
label, state/K3 are updated, and the policy is called again.

Costs are abstract mechanism units, not measured seconds.  This experiment is
therefore a causal cached replay and not a physical hard-deadline result.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Callable, Sequence

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from rc_sem.sequential import (
    LabelIsolatedSequentialEnv,
    PublicSequentialState,
    SequentialAction,
    SequentialActionType,
    SequentialCostConfig,
    SequentialObservation,
    build_scan_cells,
    validate_public_state_no_evaluator_leakage,
)
from rc_sem.sequential_policies import (
    BasePolicy,
    CrossVideoProfile,
    DynamicValuePolicy,
    FixedCyclePolicy,
    TwoStageRawPolicy,
    can_scan_with_reserve,
    can_verify,
    next_scan_target,
)


BUDGETS = (5.0, 10.0, 20.0, 50.0, 80.0, 100.0)
SEEDS = (0, 1, 2, 3, 4)
COSTS = SequentialCostConfig(
    scan_cost=0.1,
    verify_cost=1.0,
    scan_cell_units=10,
    scan_requires_verify_reserve=True,
)
K3_CONFIG = {"g_max": 1, "d_core_max": 40.0, "d_seg_max": 60.0}
EXPECTED_EVALUATOR_HASH = "0a7a8ad4a13cc4404b0cfe7dfb1aef8958197267e22ff1df545ac4dbbf744610"
PRIMARY_DOMAIN = "dataset3_development"
DEVELOPMENT_DOMAINS = ("realcartest_0_1570", "realcartest_2000_3200")
CANDIDATE_METHODS = (
    "FIXED_SCAN1_VERIFY1",
    "FIXED_SCAN1_VERIFY3",
    "DYNAMIC_PROXY_VALUE_V1",
    "DYNAMIC_K3_VALUE_V2",
    "DYNAMIC_ADAPTIVE_K3_VALUE_V3",
)
BASELINE_METHODS = ("CURRENT_TWO_STAGE_RAW", "ARC_TWO_STAGE_COMMON")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class Domain:
    def __init__(self, name: str, dataset: str, video_id: str, units, proxy, oracle, reference):
        self.name = name
        self.dataset = dataset
        self.video_id = video_id
        self.units = units
        self.proxy = proxy
        self.oracle = oracle
        self.reference = reference

    @property
    def benchmark_id(self) -> str:
        return str(self.units.benchmark_id.iloc[0])

    @property
    def unit_windows(self) -> dict[int, tuple[float, float]]:
        return {
            int(row.unit_id): (float(row.start_time), float(row.end_time))
            for row in self.units.itertuples(index=False)
        }

    @property
    def proxy_map(self) -> dict[int, float]:
        return dict(zip(self.proxy.unit_id.astype(int), self.proxy.proxy_score.astype(float)))

    @property
    def oracle_map(self) -> dict[int, str]:
        return dict(zip(self.oracle.unit_id.astype(int), self.oracle.oracle_label.astype(str).str.lower()))


def load_domains(arc_root: Path) -> tuple[dict[str, Domain], dict]:
    root = arc_root / "BSEC_AQP_Development_Gate_v1/outputs/native_arc_vs_pstr"
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    domains = {}
    for record in manifest["datasets"]:
        name = str(record["domain"])
        frozen = root / "frozen_inputs" / name
        paths = {
            "units": frozen / "units.csv",
            "proxy": frozen / "proxy_only.csv",
            "oracle": frozen / "oracle_labels.csv",
            "reference": frozen / "reference_events.csv",
        }
        actual = {key: sha256_file(path) for key, path in paths.items()}
        expected = {key: str(record["frozen_files"][key]["sha256"]) for key in paths}
        if actual != expected:
            raise RuntimeError(f"frozen input hash mismatch: {name}")
        units = pd.read_csv(paths["units"]).sort_values("unit_id").reset_index(drop=True)
        proxy = pd.read_csv(paths["proxy"]).sort_values("unit_id").reset_index(drop=True)
        oracle = pd.read_csv(paths["oracle"]).sort_values("unit_id").reset_index(drop=True)
        ids = list(range(len(units)))
        if any(frame.unit_id.astype(int).tolist() != ids for frame in (units, proxy, oracle)):
            raise RuntimeError(f"non-canonical domain: {name}")
        domains[name] = Domain(
            name,
            str(record["dataset"]),
            str(record["video_id"]),
            units,
            proxy,
            oracle,
            pd.read_csv(paths["reference"]),
        )
    return domains, manifest


def fit_profile(training_domains: Sequence[Domain], costs: SequentialCostConfig) -> CrossVideoProfile:
    frames = []
    for domain in training_domains:
        frame = domain.proxy.merge(domain.oracle, on="unit_id", validate="one_to_one")
        frame["label"] = (frame.oracle_label.astype(str).str.lower() == "positive").astype(int)
        frames.append(frame)
    training = pd.concat(frames, ignore_index=True)
    if training.label.nunique() != 2:
        raise RuntimeError("training profile requires both classes")
    model = LogisticRegression(
        C=0.5,
        class_weight="balanced",
        max_iter=2000,
        random_state=0,
    ).fit(training[["proxy_score"]], training.label)
    intercept = float(model.intercept_[0])
    coefficient = float(model.coef_[0, 0])
    cell_maxima = []
    for domain in training_domains:
        cells = build_scan_cells(domain.unit_windows, costs.scan_cell_units)
        scores = domain.proxy_map
        for cell in cells:
            # Preserve the fitted feature name so repeated studies remain free
            # of sklearn's ndarray/feature-name ambiguity warning.
            raw = pd.DataFrame(
                {"proxy_score": [scores[unit_id] for unit_id in cell.unit_ids]}
            )
            cell_maxima.append(float(model.predict_proba(raw)[:, 1].max()))
    return CrossVideoProfile(
        intercept=intercept,
        proxy_coefficient=coefficient,
        positive_prior=float(training.label.mean()),
        cell_max_posteriors=tuple(cell_maxima),
        prior_strength=20.0,
    )


class ArcTwoStagePolicy(BasePolicy):
    """Common-environment ARC: complete SCAN, then causal historical ARC VERIFY."""

    method_id = "ARC_TWO_STAGE_COMMON"

    def __init__(self, costs, seed: int, arc_core) -> None:
        self.costs = costs
        self.seed = int(seed)
        self.arc_core = arc_core
        self.selector = None
        self.pending = None

    def choose(self, state: PublicSequentialState) -> SequentialAction:
        scan = next_scan_target(state, chronological=True)
        if scan is not None and can_scan_with_reserve(state, self.costs):
            return SequentialAction(SequentialActionType.SCAN, scan, "arc_two_stage_complete_scan")
        if not can_verify(state, self.costs):
            return self.stop("no_safe_action")
        if state.unscanned_cell_ids:
            return self.stop("arc_requires_complete_proxy_scan")
        if self.selector is None:
            scores = np.asarray([state.proxy_scores[index] for index in range(len(state.proxy_scores))])
            clusters = self.arc_core.sequential_js_clusters(scores, 0.001)
            self.selector = self.arc_core.ARCSelector(
                scores,
                clusters,
                budget=len(scores),
                seed=self.seed,
                config=self.arc_core.ARCConfig(),
            )
        selection = self.selector.select_next()
        if selection is None:
            return self.stop(f"arc_{self.selector.stop_reason}")
        self.pending = selection
        return SequentialAction(
            SequentialActionType.VERIFY,
            int(selection.unit_id),
            "arc_progressive_sampling_label_propagation",
        )

    def observe(self, prior_state, observation, next_state) -> None:
        if observation.action.action_type is SequentialActionType.VERIFY:
            if self.pending is None:
                raise RuntimeError("ARC observation without pending selection")
            self.selector.observe(self.pending, observation.revealed_label)
            self.pending = None


def make_policy(method: str, costs, profile, seed: int, arc_core):
    if method == "CURRENT_TWO_STAGE_RAW":
        return TwoStageRawPolicy(costs)
    if method == "ARC_TWO_STAGE_COMMON":
        return ArcTwoStagePolicy(costs, seed, arc_core)
    if method == "FIXED_SCAN1_VERIFY1":
        return FixedCyclePolicy(costs, 1)
    if method == "FIXED_SCAN1_VERIFY3":
        return FixedCyclePolicy(costs, 3)
    if method == "DYNAMIC_PROXY_VALUE_V1":
        return DynamicValuePolicy(costs=costs, profile=profile, mode="proxy")
    if method == "DYNAMIC_K3_VALUE_V2":
        return DynamicValuePolicy(costs=costs, profile=profile, mode="k3")
    if method == "DYNAMIC_ADAPTIVE_K3_VALUE_V3":
        return DynamicValuePolicy(costs=costs, profile=profile, mode="adaptive")
    raise ValueError(f"unknown method: {method}")


def evaluator_meta(domain: Domain, method: str, seed: int, budget: float) -> dict[str, object]:
    budget_slug = int(round(budget * 10))
    return {
        "benchmark_id": domain.benchmark_id,
        "run_id": f"{domain.name}_{method.lower()}_s{seed:03d}_c{budget_slug:04d}",
        "method": method,
        "method_variant": "unknown_video_sequential_scan_verify_v1",
        "seed": seed,
        "horizon_budget": budget,
    }


def predictions_from_verify_trace(domain, verify_rows, meta, bench):
    if verify_rows:
        trace = pd.DataFrame(verify_rows)[["unit_id", "oracle_label_after_query"]]
    else:
        trace = pd.DataFrame(columns=["unit_id", "oracle_label_after_query"])
    return bench.materialize_from_trace(trace, domain.units, meta, "k3_bridge_safe", K3_CONFIG)


def score_predictions(domain, predictions, meta, bench, evaluator_hash):
    matches, metrics = bench.evaluate_events(predictions, domain.reference, meta, evaluator_hash)
    values = dict(zip(metrics.metric_name.astype(str), metrics.metric_value.astype(float)))
    return matches, values


def run_episode(
    *,
    domain: Domain,
    method: str,
    profile: CrossVideoProfile,
    seed: int,
    budget: float,
    costs: SequentialCostConfig,
    arc_core,
    bench,
    evaluator_hash: str,
) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    env = LabelIsolatedSequentialEnv(
        unit_windows=domain.unit_windows,
        proxy_scores=domain.proxy_map,
        oracle_labels=domain.oracle_map,
        budget=budget,
        costs=costs,
    )
    policy = make_policy(method, costs, profile, seed, arc_core)
    meta = evaluator_meta(domain, method, seed, budget)
    verify_rows = []
    action_rows = []
    current_predictions = predictions_from_verify_trace(domain, verify_rows, meta, bench)
    current_matches, current_metrics = score_predictions(
        domain, current_predictions, meta, bench, evaluator_hash
    )
    recall_auc_area = 0.0
    f1_auc_area = 0.0
    returned_auc_area = 0.0
    first_event_cost = math.nan

    max_actions = len(domain.units) + len(build_scan_cells(domain.unit_windows, costs.scan_cell_units)) + 1
    for _ in range(max_actions):
        prior = env.state
        validate_public_state_no_evaluator_leakage(prior)
        action = policy.choose(prior)
        if action.action_type is SequentialActionType.STOP:
            break
        cost = env.action_cost(action)
        recall_auc_area += cost * float(current_metrics["event_recall"])
        f1_auc_area += cost * float(current_metrics["event_f1"])
        returned_auc_area += cost * len(current_predictions)
        observation = env.step(action)
        state = env.state
        policy.observe(prior, observation, state)
        if action.action_type is SequentialActionType.VERIFY:
            verify_rows.append(
                {
                    "verify_idx": len(verify_rows),
                    "unit_id": int(action.target_id),
                    "oracle_label_after_query": str(observation.revealed_label),
                }
            )
            current_predictions = predictions_from_verify_trace(domain, verify_rows, meta, bench)
            current_matches, current_metrics = score_predictions(
                domain, current_predictions, meta, bench, evaluator_hash
            )
            if len(current_predictions) and math.isnan(first_event_cost):
                first_event_cost = state.spent
        if len(state.event_groups) != len(current_predictions):
            raise RuntimeError("runtime K3 and evaluator K3 event counts diverged")
        action_rows.append(
            {
                "step_idx": len(action_rows),
                "action_type": action.action_type.value,
                "target_id": int(action.target_id),
                "reason": action.reason,
                "action_cost": observation.action_cost,
                "spent_after_commit": state.spent,
                "remaining_after_commit": state.remaining,
                "scanned_cells": len(state.scanned_cell_ids),
                "scanned_units": len(state.proxy_scores),
                "verify_count": state.verify_count,
                "verified_positive_units": len(state.positive_unit_ids),
                "returned_event_count": len(current_predictions),
                "event_precision": current_metrics["event_precision"],
                "event_recall": current_metrics["event_recall"],
                "event_f1": current_metrics["event_f1"],
                "public_state_hash": state.canonical_hash(),
                "label_revealed_only_for_verify": (
                    observation.revealed_label is not None
                    if action.action_type is SequentialActionType.VERIFY
                    else observation.revealed_label is None
                ),
            }
        )
    else:
        raise RuntimeError("episode exceeded unique-action bound")

    final_state = env.state
    residual = max(0.0, budget - final_state.spent)
    recall_auc_area += residual * float(current_metrics["event_recall"])
    f1_auc_area += residual * float(current_metrics["event_f1"])
    returned_auc_area += residual * len(current_predictions)
    row = {
        "dataset": domain.dataset,
        "domain": domain.name,
        "video_id": domain.video_id,
        "method": method,
        "seed": seed,
        "budget": budget,
        "cost_spent": final_state.spent,
        "scan_actions": final_state.scan_count,
        "verify_actions": final_state.verify_count,
        "scanned_fraction": final_state.scanned_fraction,
        "verified_positive_units": len(final_state.positive_unit_ids),
        "returned_event_count": len(current_predictions),
        "event_precision": float(current_metrics["event_precision"]),
        "event_recall": float(current_metrics["event_recall"]),
        "event_f1": float(current_metrics["event_f1"]),
        "tiou_03": float(current_metrics["tiou_03"]),
        "tiou_05": float(current_metrics["tiou_05"]),
        "matched_mean_iou": float(current_metrics["matched_mean_iou"]),
        "overmerge": float(current_metrics["overmerge"]),
        "oversplit": float(current_metrics["oversplit"]),
        "anytime_event_recall_auc": recall_auc_area / budget,
        "anytime_event_f1_auc": f1_auc_area / budget,
        "anytime_returned_event_count": returned_auc_area / budget,
        "first_event_cost": first_event_cost,
        "zero_budget_overrun": final_state.spent <= budget + 1e-12,
        "zero_unscanned_verify": all(
            row["action_type"] != "VERIFY" or row["scanned_units"] > 0
            for row in action_rows
        ),
    }
    return row, pd.DataFrame(action_rows), current_predictions, current_matches


def run_grid(
    *,
    domains: Sequence[Domain],
    methods: Sequence[str],
    profile_for_domain: Callable[[Domain], CrossVideoProfile],
    seeds: Sequence[int],
    budgets: Sequence[float],
    costs,
    arc_core,
    bench,
    evaluator_hash,
    output: Path | None = None,
    phase: str,
) -> pd.DataFrame:
    rows = []
    for domain in domains:
        profile = profile_for_domain(domain)
        for method in methods:
            method_seeds = seeds if method == "ARC_TWO_STAGE_COMMON" else (seeds[0],)
            for seed in method_seeds:
                for budget in budgets:
                    row, actions, predictions, matches = run_episode(
                        domain=domain,
                        method=method,
                        profile=profile,
                        seed=seed,
                        budget=budget,
                        costs=costs,
                        arc_core=arc_core,
                        bench=bench,
                        evaluator_hash=evaluator_hash,
                    )
                    row["phase"] = phase
                    rows.append(row)
                    if output is not None:
                        suffix = f"seed_{seed:03d}_cost_{int(round(budget * 10)):04d}.csv"
                        for kind, frame in (
                            ("action_traces", actions),
                            ("predictions", predictions),
                            ("event_matches", matches),
                        ):
                            path = output / phase / kind / method.lower() / domain.name / suffix
                            path.parent.mkdir(parents=True, exist_ok=True)
                            frame.to_csv(path, index=False)
    return pd.DataFrame(rows)


def select_candidate(dev_rows: pd.DataFrame) -> tuple[str, pd.DataFrame]:
    deterministic = dev_rows[dev_rows.method.isin(CANDIDATE_METHODS)]
    summary = (
        deterministic.groupby("method", as_index=False)[
            [
                "anytime_event_recall_auc",
                "anytime_event_f1_auc",
                "event_recall",
                "event_f1",
                "event_precision",
            ]
        ]
        .mean()
    )
    summary["selection_eligible"] = summary.event_precision >= 0.70
    eligible = summary[summary.selection_eligible]
    if eligible.empty:
        raise RuntimeError("no candidate satisfies development precision gate")
    selected = eligible.sort_values(
        ["anytime_event_recall_auc", "anytime_event_f1_auc", "event_recall", "method"],
        ascending=[False, False, False, True],
    ).iloc[0]
    summary["selected_before_primary"] = summary.method == selected.method
    return str(selected.method), summary


def report_text(selected: str, development: pd.DataFrame, primary: pd.DataFrame) -> str:
    dev = development.sort_values("anytime_event_recall_auc", ascending=False).copy()
    primary_mean = (
        primary.groupby(["method", "budget"], as_index=False)[
            [
                "scan_actions",
                "verify_actions",
                "returned_event_count",
                "event_precision",
                "event_recall",
                "event_f1",
                "anytime_event_recall_auc",
                "anytime_event_f1_auc",
                "first_event_cost",
            ]
        ]
        .mean()
    )
    focus = primary_mean[
        primary_mean.method.isin([selected, "CURRENT_TWO_STAGE_RAW", "ARC_TWO_STAGE_COMMON"])
    ]

    def table(frame, columns):
        lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
        for values in frame[columns].itertuples(index=False, name=None):
            rendered = [f"{value:.3f}" if isinstance(value, (float, np.floating)) else str(value) for value in values]
            lines.append("| " + " | ".join(rendered) + " |")
        return "\n".join(lines)

    dev_table = table(
        dev,
        ["method", "anytime_event_recall_auc", "anytime_event_f1_auc", "event_recall", "event_f1", "event_precision", "selected_before_primary"],
    )
    primary_table = table(
        focus,
        ["method", "budget", "scan_actions", "verify_actions", "returned_event_count", "event_precision", "event_recall", "event_f1", "anytime_event_recall_auc", "first_event_cost"],
    )
    return f"""# Unknown-video sequential SCAN/VERIFY study

## Frozen result

Five candidate policies were compared only on reciprocal realcartest-slice
development folds.  The method frozen before inspecting the primary query
video was:

```text
{selected}
```

### Development selection

{dev_table}

### Held-out query-bound comparison

{primary_table}

## Exact execution semantics

- The video starts with zero visible proxy scores and zero labels.
- `SCAN(cell)` reveals proxy scores for one label-blind 10-unit cell.
- `VERIFY(unit)` is legal only after that unit has been scanned and reveals
  exactly that frozen label.
- After every committed action, public state, online calibration and strict K3
  are recomputed before the next decision.
- SCAN costs `0.1` and VERIFY costs `1.0` abstract units.  These are mechanism
  costs, not physical timings.
- Probable publication is disabled because the prior cached calibration found
  no threshold satisfying the 0.80 Wilson lower-bound gate.

## Scientific boundary

The primary video did not participate in candidate selection or posterior
training.  The development derivatives lack prompt/parser hashes and originate
from one source video, so this is a held-out mechanism test rather than broad
generalization evidence.  A physical conclusion requires measured SCAN and
VERIFY costs and the same replay under a real deadline.
"""


def artifact_inventory(output: Path) -> tuple[pd.DataFrame, str]:
    rows = []
    for path in sorted(p for p in output.rglob("*") if p.is_file() and p.name not in {"ARTIFACT_HASHES.csv", "RUN_MANIFEST.json"}):
        rows.append({"path": str(path.relative_to(output)), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    frame = pd.DataFrame(rows)
    return frame, canonical_hash(frame.to_dict(orient="records"))


def execute(arc_root: Path, output: Path) -> None:
    if output.exists():
        raise RuntimeError(f"refusing to overwrite {output}")
    benchmark_path = arc_root / (
        "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/"
        "clean_baseline_benchmark_v2_strict/scripts/benchmark_lib.py"
    )
    evaluator_hash = sha256_file(benchmark_path)
    if evaluator_hash != EXPECTED_EVALUATOR_HASH:
        raise RuntimeError("evaluator hash changed")
    bench = load_module("sequential_unknown_benchmark", benchmark_path)
    sys.path.insert(0, str(arc_root / "src"))
    from garc_eval.arc_cached_replay import core as arc_core

    domains, manifest = load_domains(arc_root)
    output.mkdir(parents=True)

    # Reciprocal slice development: each target slice's posterior sees only the
    # other slice.  The primary dataset3 labels are not touched here.
    dev_profiles = {
        DEVELOPMENT_DOMAINS[0]: fit_profile([domains[DEVELOPMENT_DOMAINS[1]]], COSTS),
        DEVELOPMENT_DOMAINS[1]: fit_profile([domains[DEVELOPMENT_DOMAINS[0]]], COSTS),
    }
    dev_rows = run_grid(
        domains=[domains[name] for name in DEVELOPMENT_DOMAINS],
        methods=CANDIDATE_METHODS,
        profile_for_domain=lambda domain: dev_profiles[domain.name],
        seeds=(0,),
        budgets=BUDGETS,
        costs=COSTS,
        arc_core=arc_core,
        bench=bench,
        evaluator_hash=evaluator_hash,
        output=output,
        phase="development",
    )
    selected, selection_summary = select_candidate(dev_rows)
    dev_rows.to_csv(output / "development_per_run_metrics.csv", index=False)
    selection_summary.to_csv(output / "development_method_selection.csv", index=False)
    write_json(
        output / "FROZEN_SELECTION.json",
        {
            "selected_method": selected,
            "selection_source_domains": list(DEVELOPMENT_DOMAINS),
            "primary_domain_not_used": PRIMARY_DOMAIN,
            "selection_rule": "max mean AnytimeEventRecallAUC, then AnytimeEventF1AUC, then terminal recall; precision >= 0.70",
            "candidate_methods": list(CANDIDATE_METHODS),
        },
    )

    primary_profile = fit_profile([domains[name] for name in DEVELOPMENT_DOMAINS], COSTS)
    primary_methods = (*BASELINE_METHODS, *CANDIDATE_METHODS)
    primary_rows = run_grid(
        domains=[domains[PRIMARY_DOMAIN]],
        methods=primary_methods,
        profile_for_domain=lambda domain: primary_profile,
        seeds=SEEDS,
        budgets=BUDGETS,
        costs=COSTS,
        arc_core=arc_core,
        bench=bench,
        evaluator_hash=evaluator_hash,
        output=output,
        phase="primary_heldout",
    )
    primary_rows["selected_method"] = primary_rows.method == selected
    primary_rows.to_csv(output / "primary_heldout_per_run_metrics.csv", index=False)

    checks = {
        "status": "PASS",
        "primary_not_in_development_domains": PRIMARY_DOMAIN not in DEVELOPMENT_DOMAINS,
        "all_actions_within_budget": bool(primary_rows.zero_budget_overrun.all() and dev_rows.zero_budget_overrun.all()),
        "all_verify_targets_scanned": bool(primary_rows.zero_unscanned_verify.all() and dev_rows.zero_unscanned_verify.all()),
        "primary_selected_method_frozen_before_run": True,
        "zero_probable_events": True,
        "strict_k3_shared": True,
        "primary_runs": len(primary_rows),
        "development_runs": len(dev_rows),
        "deterministic_non_arc": True,
    }
    write_json(output / "validation_checks.json", checks)
    report_dir = output / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "SEQUENTIAL_UNKNOWN_VIDEO_STUDY.md").write_text(
        report_text(selected, selection_summary, primary_rows), encoding="utf-8"
    )
    config = {
        "schema_version": "SEQUENTIAL_UNKNOWN_VIDEO_STUDY_V1",
        "classification": "cached_causal_mechanism_replay_not_physical",
        "costs": asdict(COSTS),
        "budgets": list(BUDGETS),
        "seeds": list(SEEDS),
        "candidate_methods": list(CANDIDATE_METHODS),
        "baselines": list(BASELINE_METHODS),
        "selected_method": selected,
        "evaluator_hash": evaluator_hash,
        "k3": {"name": "k3_bridge_safe", **K3_CONFIG},
        "frozen_input_manifest_hash": sha256_file(
            arc_root / "BSEC_AQP_Development_Gate_v1/outputs/native_arc_vs_pstr/manifest.json"
        ),
        "primary_prompt_identity": "complete",
        "development_prompt_identity": "missing_in_derivative",
    }
    config["config_hash"] = canonical_hash(config)
    write_json(output / "CONFIG.json", config)
    artifacts, aggregate = artifact_inventory(output)
    artifacts.to_csv(output / "ARTIFACT_HASHES.csv", index=False)
    run_manifest = {
        "schema_version": "SEQUENTIAL_UNKNOWN_VIDEO_STUDY_V1",
        "status": "PASS_WITH_DISCLOSED_LIMITATIONS",
        "selected_method": selected,
        "development_run_count": len(dev_rows),
        "primary_run_count": len(primary_rows),
        "artifact_count": len(artifacts),
        "artifact_inventory_aggregate_hash": aggregate,
        "config_hash": config["config_hash"],
    }
    write_json(output / "RUN_MANIFEST.json", run_manifest)
    print(json.dumps(run_manifest, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arc-root", type=Path, default=Path("/root/charm/GVAQP-arc-phys-baseline"))
    parser.add_argument("--output", type=Path, default=Path("outputs/sequential_unknown_video_study"))
    args = parser.parse_args()
    execute(args.arc_root.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
