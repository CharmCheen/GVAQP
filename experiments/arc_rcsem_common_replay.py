#!/usr/bin/env python3
"""Paired ARC/RC-SEM replay on the exact frozen ARC cached inputs.

The ARC result is copied byte-for-byte from its independently validated cached
replay.  RC-SEM receives the same public unit/proxy tables, logical VERIFY
budgets, strict K3 materializer, and event evaluator.  Hidden labels for an
evaluation source video are never used by its posterior or risk-threshold fit.

This is an exploratory logical-call replay.  It is not a physical-deadline
comparison and it does not repair missing prompt/parser provenance.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression


METHOD_ARC = "ARC-CACHED-REPLAY-v1"
METHOD_RCSEM = "RC-SEM-CACHED-COMMON-v1"
METHOD_VARIANT = "cross_source_posterior_ranking_risk_gate_strict_shared_k3"
BUDGETS = (5, 10, 20, 50, 80, 100)
SEEDS = (0, 1, 2, 3, 4)
K3_CONFIG = {"g_max": 1, "d_core_max": 40.0, "d_seg_max": 60.0}
PRECISION_FLOOR = 0.80
MINIMUM_EVENT_ADMISSIONS = 10
EXPECTED_EVALUATOR_HASH = "0a7a8ad4a13cc4404b0cfe7dfb1aef8958197267e22ff1df545ac4dbbf744610"
EXPECTED_DATASET3_PROMPT_HASH = "12187489e65828f1a5af829b649877e8e60927eff269c19278704f858781cf33"

TRACE_COLUMNS = [
    "call_idx",
    "unit_id",
    "oracle_label_after_query",
    "outcome_is_determinate",
    "verified_positive",
    "propagated_unit_count",
    "proxy_score",
    "selection_reason",
    "oracle_accessed_only_after_selection",
]

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

AGGREGATE_METRICS = [
    "event_precision",
    "event_recall",
    "event_f1",
    "tiou_03",
    "tiou_05",
    "matched_mean_iou",
    "verified_positive_units",
    "verified_event_count",
    "verified_event_yield",
    "logical_oracle_calls",
    "returned_event_count",
    "overmerge",
    "oversplit",
]


@dataclass(frozen=True)
class Domain:
    name: str
    dataset: str
    video_id: str
    units: pd.DataFrame
    proxy: pd.DataFrame
    oracle: pd.DataFrame
    reference: pd.DataFrame
    hashes: dict[str, str]

    @property
    def benchmark_id(self) -> str:
        return str(self.units.benchmark_id.iloc[0])

    @property
    def query_id(self) -> str:
        return f"{self.name}:frozen_relevance_predicate"


@dataclass(frozen=True)
class EventRiskThreshold:
    posterior_threshold: float
    predicted_events: int
    matched_events: int
    empirical_precision: float
    wilson_lower_95: float


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def wilson_lower(successes: int, trials: int, z: float = 1.959963984540054) -> float:
    if trials <= 0:
        return 0.0
    proportion = successes / trials
    z2 = z * z
    denominator = 1.0 + z2 / trials
    center = proportion + z2 / (2.0 * trials)
    radius = z * math.sqrt(
        proportion * (1.0 - proportion) / trials + z2 / (4.0 * trials * trials)
    )
    return max(0.0, (center - radius) / denominator)


def load_domains(arc_root: Path) -> tuple[list[Domain], dict]:
    benchmark_root = arc_root / "BSEC_AQP_Development_Gate_v1/outputs/native_arc_vs_pstr"
    frozen_root = benchmark_root / "frozen_inputs"
    manifest = json.loads((benchmark_root / "manifest.json").read_text(encoding="utf-8"))
    if tuple(manifest["budgets"]) != BUDGETS or tuple(manifest["seeds"]) != SEEDS:
        raise RuntimeError("ARC frozen budget/seed grid changed")
    domains: list[Domain] = []
    for record in manifest["datasets"]:
        name = str(record["domain"])
        paths = {
            "units": frozen_root / name / "units.csv",
            "proxy": frozen_root / name / "proxy_only.csv",
            "oracle": frozen_root / name / "oracle_labels.csv",
            "reference": frozen_root / name / "reference_events.csv",
        }
        hashes = {key: sha256_file(path) for key, path in paths.items()}
        expected = {key: str(record["frozen_files"][key]["sha256"]) for key in paths}
        if hashes != expected:
            raise RuntimeError(f"frozen input hash mismatch for {name}")
        units = pd.read_csv(paths["units"]).sort_values("unit_id").reset_index(drop=True)
        proxy = pd.read_csv(paths["proxy"]).sort_values("unit_id").reset_index(drop=True)
        oracle = pd.read_csv(paths["oracle"]).sort_values("unit_id").reset_index(drop=True)
        reference = pd.read_csv(paths["reference"])
        ids = list(range(int(record["unit_count"])))
        if any(table.unit_id.astype(int).tolist() != ids for table in (units, proxy, oracle)):
            raise RuntimeError(f"non-canonical or incomplete unit universe for {name}")
        domains.append(
            Domain(
                name=name,
                dataset=str(record["dataset"]),
                video_id=str(record["video_id"]),
                units=units,
                proxy=proxy,
                oracle=oracle,
                reference=reference,
                hashes=hashes,
            )
        )
    return domains, manifest


def public_training_frame(domains: Iterable[Domain]) -> pd.DataFrame:
    rows = []
    for domain in domains:
        frame = domain.proxy.merge(domain.oracle, on="unit_id", validate="one_to_one")
        frame["domain"] = domain.name
        frame["video_id"] = domain.video_id
        frame["label"] = (frame.oracle_label.astype(str).str.lower() == "positive").astype(int)
        rows.append(frame[["domain", "video_id", "unit_id", "proxy_score", "label"]])
    return pd.concat(rows, ignore_index=True)


def fit_cross_source_posterior(training_domains: Sequence[Domain], seed: int):
    frame = public_training_frame(training_domains)
    if frame.label.nunique() != 2:
        raise RuntimeError("posterior training requires both label classes")
    model = LogisticRegression(
        C=0.5,
        class_weight="balanced",
        max_iter=2000,
        random_state=seed,
    )
    model.fit(frame[["proxy_score"]], frame.label)
    return model


def score_domain(domain: Domain, model) -> pd.DataFrame:
    scored = domain.proxy.copy()
    scored["posterior_score"] = model.predict_proba(scored[["proxy_score"]])[:, 1]
    return scored


def run_meta(domain: Domain, seed: int, budget: int) -> dict[str, object]:
    return {
        "benchmark_id": domain.benchmark_id,
        "run_id": f"{domain.name}_rc_sem_cached_common_v1_s{seed:03d}_b{budget:03d}",
        "method": METHOD_RCSEM,
        "method_variant": METHOD_VARIANT,
        "seed": int(seed),
        "horizon_budget": int(budget),
    }


def predicted_events_at_threshold(
    domain: Domain,
    scored: pd.DataFrame,
    threshold: float,
    bench,
) -> pd.DataFrame:
    selected = scored.loc[scored.posterior_score >= threshold, "unit_id"].astype(int)
    trace = pd.DataFrame(
        {"unit_id": selected, "oracle_label_after_query": "positive"}
    )
    meta = {
        "benchmark_id": domain.benchmark_id,
        "run_id": "training_risk_gate",
        "method": METHOD_RCSEM,
        "method_variant": "training_only",
        "seed": 0,
        "horizon_budget": 0,
    }
    return bench.materialize_from_trace(trace, domain.units, meta, "k3_bridge_safe", K3_CONFIG)


def choose_event_risk_threshold(
    training_domains: Sequence[Domain],
    model,
    bench,
    *,
    precision_floor: float = PRECISION_FLOOR,
    minimum_event_admissions: int = MINIMUM_EVENT_ADMISSIONS,
) -> EventRiskThreshold | None:
    scored = {domain.name: score_domain(domain, model) for domain in training_domains}
    thresholds = sorted(
        {
            float(value)
            for frame in scored.values()
            for value in frame.posterior_score.to_numpy(float)
        },
        reverse=True,
    )
    choices: list[EventRiskThreshold] = []
    for threshold in thresholds:
        predicted_count = 0
        matched_count = 0
        for domain in training_domains:
            predictions = predicted_events_at_threshold(
                domain, scored[domain.name], threshold, bench
            )
            meta = {
                "benchmark_id": domain.benchmark_id,
                "run_id": "training_risk_gate",
                "method": METHOD_RCSEM,
                "method_variant": "training_only",
                "seed": 0,
                "horizon_budget": 0,
            }
            matches, _ = bench.evaluate_events(
                predictions, domain.reference, meta, "training_only"
            )
            predicted_count += len(predictions)
            matched_count += int(matches.matched.astype(bool).sum()) if len(matches) else 0
        if predicted_count < minimum_event_admissions:
            continue
        lower = wilson_lower(matched_count, predicted_count)
        if lower + 1e-15 >= precision_floor:
            choices.append(
                EventRiskThreshold(
                    posterior_threshold=threshold,
                    predicted_events=predicted_count,
                    matched_events=matched_count,
                    empirical_precision=matched_count / predicted_count,
                    wilson_lower_95=lower,
                )
            )
    if not choices:
        return None
    return max(choices, key=lambda row: (row.predicted_events, row.posterior_threshold))


def label_hidden_ranking(scored: pd.DataFrame) -> list[int]:
    required = {"unit_id", "posterior_score"}
    if not required <= set(scored.columns):
        raise ValueError(f"scored public table lacks {required - set(scored.columns)}")
    if "oracle_label" in scored.columns or "label" in scored.columns:
        raise ValueError("evaluator label leaked into RC-SEM ranking input")
    return (
        scored.sort_values(["posterior_score", "unit_id"], ascending=[False, True])
        .unit_id.astype(int)
        .tolist()
    )


def reveal_trace(
    domain: Domain,
    ranking: Sequence[int],
    budget: int,
) -> pd.DataFrame:
    selected = list(map(int, ranking[:budget]))
    if len(selected) != budget or len(selected) != len(set(selected)):
        raise RuntimeError("RC-SEM must issue exactly one unique query per budget slot")
    label_map = dict(
        zip(
            domain.oracle.unit_id.astype(int),
            domain.oracle.oracle_label.astype(str).str.lower(),
        )
    )
    score_map = dict(zip(domain.proxy.unit_id.astype(int), domain.proxy.proxy_score.astype(float)))
    rows = []
    for call_idx, unit_id in enumerate(selected):
        outcome = label_map[unit_id]
        rows.append(
            {
                "call_idx": call_idx,
                "unit_id": unit_id,
                "oracle_label_after_query": outcome,
                "outcome_is_determinate": outcome in {"positive", "negative"},
                "verified_positive": outcome == "positive",
                "propagated_unit_count": 0,
                "proxy_score": score_map[unit_id],
                "selection_reason": "rc_sem_cross_source_posterior_event_yield",
                "oracle_accessed_only_after_selection": True,
            }
        )
    return pd.DataFrame(rows, columns=TRACE_COLUMNS)


def materialize_combined(
    domain: Domain,
    trace: pd.DataFrame,
    scored: pd.DataFrame,
    threshold: EventRiskThreshold | None,
    meta: dict[str, object],
    bench,
) -> tuple[pd.DataFrame, int]:
    selected_ids = set(trace.unit_id.astype(int))
    probable_ids: set[int] = set()
    if threshold is not None:
        probable_ids = set(
            scored.loc[
                (scored.posterior_score >= threshold.posterior_threshold)
                & (~scored.unit_id.astype(int).isin(selected_ids)),
                "unit_id",
            ].astype(int)
        )
    synthetic = trace[["unit_id", "oracle_label_after_query"]].copy()
    if probable_ids:
        synthetic = pd.concat(
            [
                synthetic,
                pd.DataFrame(
                    {
                        "unit_id": sorted(probable_ids),
                        "oracle_label_after_query": "positive",
                    }
                ),
            ],
            ignore_index=True,
        )
    predictions = bench.materialize_from_trace(
        synthetic, domain.units, meta, "k3_bridge_safe", K3_CONFIG
    )
    if predictions.empty or not probable_ids:
        return predictions, 0
    verified_positive_ids = set(
        trace.loc[
            trace.oracle_label_after_query.astype(str).str.lower() == "positive", "unit_id"
        ].astype(int)
    )
    probable_events = 0
    for index, row in predictions.iterrows():
        anchors = set(bench.read_ids(row.anchor_unit_ids))
        if anchors & verified_positive_ids:
            predictions.at[index, "verification_state"] = "oracle_confirmed"
            predictions.at[index, "confidence"] = 1.0
        else:
            predictions.at[index, "verification_state"] = "probable"
            predictions.at[index, "confidence"] = threshold.wilson_lower_95
            probable_events += 1
    return predictions, probable_events


def save_rcsem_run(
    output: Path,
    domain: Domain,
    seed: int,
    budget: int,
    trace: pd.DataFrame,
    predictions: pd.DataFrame,
    bench,
    evaluator_hash: str,
) -> tuple[dict[str, object], pd.DataFrame]:
    meta = run_meta(domain, seed, budget)
    matches, metric_rows = bench.evaluate_events(
        predictions, domain.reference, meta, evaluator_hash
    )
    suffix = f"seed_{seed:03d}_budget_{budget:03d}.csv"
    paths = {
        "selection_trace": output / "selection_traces/rc_sem_cached_common_v1" / domain.name / suffix,
        "prediction": output / "predictions/rc_sem_cached_common_v1" / domain.name / suffix,
        "event_match": output / "event_matches/rc_sem_cached_common_v1" / domain.name / suffix,
    }
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    trace.to_csv(paths["selection_trace"], index=False)
    predictions.to_csv(paths["prediction"], index=False)
    matches.to_csv(paths["event_match"], index=False)
    metric_map = dict(
        zip(metric_rows.metric_name.astype(str), metric_rows.metric_value.astype(float))
    )
    positives = int(
        (trace.oracle_label_after_query.astype(str).str.lower() == "positive").sum()
    )
    verified_events = int(
        (predictions.verification_state.astype(str) == "oracle_confirmed").sum()
    ) if len(predictions) else 0
    matched_count = int(matches.matched.astype(bool).sum()) if len(matches) else 0
    row: dict[str, object] = {
        "dataset": domain.dataset,
        "domain": domain.name,
        "video_id": domain.video_id,
        "query_id": domain.query_id,
        "method": METHOD_RCSEM,
        "method_variant": METHOD_VARIANT,
        "seed": seed,
        "budget": budget,
        "logical_oracle_calls": len(trace),
        "verified_positive_units": positives,
        "verified_event_count": verified_events,
        "verified_event_yield": verified_events / len(trace) if len(trace) else 0.0,
        "matched_reference_events": matched_count,
        "returned_event_count": len(predictions),
        "selection_trace_path": str(paths["selection_trace"].relative_to(output.parent.parent)),
        "prediction_path": str(paths["prediction"].relative_to(output.parent.parent)),
        "event_match_path": str(paths["event_match"].relative_to(output.parent.parent)),
    }
    row.update({name: float(metric_map[name]) for name in METRICS})
    return row, matches


def copy_arc_runs(arc_root: Path, output: Path) -> pd.DataFrame:
    source = arc_root / "outputs/arc_cached_replay_v1"
    source_metrics = pd.read_csv(source / "per_run_metrics.csv")
    rows = source_metrics[source_metrics.method == METHOD_ARC].copy()
    if len(rows) != 3 * len(BUDGETS) * len(SEEDS):
        raise RuntimeError("unexpected ARC run count")
    for row_index, row in rows.iterrows():
        for column, kind in (
            ("selection_trace_path", "selection_traces"),
            ("prediction_path", "predictions"),
            ("event_match_path", "event_matches"),
        ):
            source_path = arc_root / str(row[column])
            relative = source_path.relative_to(source / kind)
            destination = output / kind / "arc_cached_replay_v1" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination)
            rows.at[row_index, column] = str(destination.relative_to(output.parent.parent))
    return rows.reset_index(drop=True)


def aggregate(per_run: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    task = (
        per_run.groupby(
            ["method", "domain", "video_id", "query_id", "budget"], as_index=False
        )[AGGREGATE_METRICS]
        .mean()
    )
    task["scope"] = "task_seed_average"
    video = (
        task.groupby(["method", "video_id", "budget"], as_index=False)[AGGREGATE_METRICS]
        .mean()
    )
    video["domain"] = "__within_video_average__"
    video["query_id"] = "__within_video_query_average__"
    video["scope"] = "source_video_average"
    macro = video.groupby(["method", "budget"], as_index=False)[AGGREGATE_METRICS].mean()
    macro["domain"] = "__macro__"
    macro["video_id"] = "__macro_across_source_videos__"
    macro["query_id"] = "__macro__"
    macro["scope"] = "macro_across_source_videos"
    columns = [
        "scope", "method", "domain", "video_id", "query_id", "budget", *AGGREGATE_METRICS
    ]
    curves = pd.concat([task[columns], video[columns], macro[columns]], ignore_index=True)

    auc_rows = []
    for keys, group in curves.groupby(
        ["scope", "method", "domain", "video_id", "query_id"]
    ):
        group = group.sort_values("budget")
        budgets = group.budget.to_numpy(float)
        span = float(budgets[-1] - budgets[0])
        row = dict(zip(["scope", "method", "domain", "video_id", "query_id"], keys))
        row["budget_min"] = int(budgets[0])
        row["budget_max"] = int(budgets[-1])
        for metric in ("event_f1", "event_precision", "event_recall", "tiou_03", "tiou_05"):
            row[f"{metric}_auc"] = (
                float(np.trapezoid(group[metric].to_numpy(float), budgets) / span)
                if span
                else math.nan
            )
        auc_rows.append(row)
    auc = pd.DataFrame(auc_rows)

    paired_rows = []
    for scope in ("task_seed_average", "source_video_average", "macro_across_source_videos"):
        subset = curves[curves.scope == scope]
        identifiers = ["domain", "video_id", "query_id", "budget"]
        for values, group in subset.groupby(identifiers, dropna=False):
            by_method = group.set_index("method")
            if METHOD_ARC not in by_method.index or METHOD_RCSEM not in by_method.index:
                raise RuntimeError("unpaired ARC/RC-SEM aggregate row")
            row = {"scope": scope, **dict(zip(identifiers, values))}
            for metric in AGGREGATE_METRICS:
                arc_value = float(by_method.loc[METHOD_ARC, metric])
                rcsem_value = float(by_method.loc[METHOD_RCSEM, metric])
                row[f"arc_{metric}"] = arc_value
                row[f"rcsem_{metric}"] = rcsem_value
                row[f"delta_rcsem_minus_arc_{metric}"] = rcsem_value - arc_value
            delta = row["delta_rcsem_minus_arc_event_f1"]
            row["f1_outcome"] = (
                "RC-SEM wins" if delta > 1e-12 else "ARC wins" if delta < -1e-12 else "tie"
            )
            paired_rows.append(row)
    return curves, auc, pd.DataFrame(paired_rows)


def markdown_table(frame: pd.DataFrame, columns: Sequence[str]) -> str:
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for values in frame[list(columns)].itertuples(index=False, name=None):
        rendered = [f"{value:.3f}" if isinstance(value, (float, np.floating)) else str(value) for value in values]
        lines.append("| " + " | ".join(rendered) + " |")
    return "\n".join(lines)


def build_report(
    curves: pd.DataFrame,
    auc: pd.DataFrame,
    diagnostics: pd.DataFrame,
) -> str:
    primary = curves[
        (curves.scope == "task_seed_average")
        & (curves.domain == "dataset3_development")
    ].copy()
    primary = primary.pivot(index="budget", columns="method", values=["event_precision", "event_recall", "event_f1"])
    primary.columns = [f"{metric}_{'arc' if method == METHOD_ARC else 'rcsem'}" for metric, method in primary.columns]
    primary = primary.reset_index()
    primary["delta_f1"] = primary["event_f1_rcsem"] - primary["event_f1_arc"]
    primary_table = markdown_table(
        primary,
        ["budget", "event_precision_arc", "event_precision_rcsem", "event_recall_arc", "event_recall_rcsem", "event_f1_arc", "event_f1_rcsem", "delta_f1"],
    )
    macro_auc = auc[auc.scope == "macro_across_source_videos"]
    auc_table = markdown_table(
        macro_auc,
        ["method", "event_precision_auc", "event_recall_auc", "event_f1_auc", "tiou_03_auc", "tiou_05_auc"],
    )
    probable_count = int(diagnostics.probable_event_count.sum())
    gate_found = bool(diagnostics.risk_threshold_found.any())
    return f"""# ARC vs RC-SEM common-input cached replay

## Strongest supported conclusion

This experiment compares ARC and RC-SEM on identical frozen inputs, logical
VERIFY budgets, strict K3 eventization, and evaluator output schemas.  The
query-identity-complete primary domain is `dataset3_development`, bound to
prompt hash `{EXPECTED_DATASET3_PROMPT_HASH}`.

RC-SEM admitted **{probable_count} probable events**.  Cross-source calibration
found a deployable 0.80 precision-floor threshold: **{gate_found}**.  Therefore
any measured advantage is a VERIFY scheduling result, not evidence that safe
unverified event publication works.

## Primary query-bound result

{primary_table}

## Two-source-video sensitivity summary

{auc_table}

The macro treats the two `realcartest` slices as one source video before
averaging with `dataset3`; five repeated RC-SEM seeds are deterministic pairing
rows, not five independent samples.

## Evidence boundaries

- ARC rows were copied byte-for-byte from its independently validated cached
  replay; 180 original rows and 640 artifact hashes were independently
  rechecked before this comparison.
- Both methods read the same `units.csv`, `proxy_only.csv`, `oracle_labels.csv`,
  and `reference_events.csv`; RC-SEM target ordering is computed before the
  held-out source-video oracle is revealed.
- `dataset3_development` has complete model/prompt/parser binding.  The two
  `realcartest` derivatives lack prompt and parser hashes, so their results are
  sensitivity evidence only.
- This is an exploratory, open-benchmark cached replay.  It is neither a
  prospective comparison nor a physical hard-deadline experiment.
- The physical ARC/RC-SEM smoke remains blocked by non-deployable calibration,
  missing immutable model/proxy bytes, stale deadline profiles, and unavailable
  compatible GPUs.  No physical claim follows from this replay.

## Interpretation and rejection trigger

The decisive question is whether RC-SEM's scheduling advantage survives a
shared physical runtime with a deployable event posterior.  Reject a general
RC-SEM advantage if that paired run loses at equal wall-clock budget, if a
held-out source video reverses the gain, or if probable-event precision fails
the frozen 0.80 lower-confidence-bound gate.
"""


def artifact_inventory(output: Path) -> tuple[pd.DataFrame, str]:
    excluded = {"ARTIFACT_HASHES.csv", "RUN_MANIFEST.json"}
    rows = []
    for path in sorted(p for p in output.rglob("*") if p.is_file() and p.name not in excluded):
        rows.append(
            {
                "path": str(path.relative_to(output)),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
        )
    frame = pd.DataFrame(rows)
    aggregate = canonical_hash(frame.to_dict(orient="records"))
    return frame, aggregate


def validate_outputs(output: Path, arc_root: Path, bench) -> dict[str, object]:
    per_run = pd.read_csv(output / "per_run_metrics.csv")
    expected_runs = 3 * len(BUDGETS) * len(SEEDS) * 2
    failures: list[str] = []
    if len(per_run) != expected_runs:
        failures.append("run_count")
    if set(per_run.method) != {METHOD_ARC, METHOD_RCSEM}:
        failures.append("method_set")
    if not (per_run.logical_oracle_calls <= per_run.budget).all():
        failures.append("budget_cap_accounting")
    rcsem_budget = per_run[per_run.method == METHOD_RCSEM]
    if not (rcsem_budget.logical_oracle_calls == rcsem_budget.budget).all():
        failures.append("rcsem_exact_budget_accounting")
    arc_source = pd.read_csv(arc_root / "outputs/arc_cached_replay_v1/per_run_metrics.csv")
    source_arc = arc_source[arc_source.method == METHOD_ARC].sort_values(["domain", "seed", "budget"])
    copied_arc = per_run[per_run.method == METHOD_ARC].sort_values(["domain", "seed", "budget"])
    metric_columns = [column for column in source_arc.columns if not column.endswith("_path")]
    if not source_arc[metric_columns].reset_index(drop=True).equals(
        copied_arc[metric_columns].reset_index(drop=True)
    ):
        failures.append("arc_metric_copy_parity")

    schema_reference = arc_root / "outputs/arc_cached_replay_v1"
    schema_pairs = []
    for kind, column in (
        ("selection_traces", "selection_trace_path"),
        ("predictions", "prediction_path"),
        ("event_matches", "event_match_path"),
    ):
        arc_example = next((schema_reference / kind / "arc_cached_replay_v1").rglob("*.csv"))
        rcsem_example = next((output / kind / "rc_sem_cached_common_v1").rglob("*.csv"))
        same = list(pd.read_csv(arc_example).columns) == list(pd.read_csv(rcsem_example).columns)
        schema_pairs.append({"artifact": kind, "columns_identical": same})
        if not same:
            failures.append(f"{kind}_schema")

    recomputed = 0
    for row in per_run.itertuples(index=False):
        predictions = pd.read_csv(output.parent.parent / row.prediction_path)
        reference = pd.read_csv(
            arc_root
            / "BSEC_AQP_Development_Gate_v1/outputs/native_arc_vs_pstr/frozen_inputs"
            / row.domain
            / "reference_events.csv"
        )
        meta = {
            "benchmark_id": str(reference.benchmark_id.iloc[0]),
            "run_id": str(predictions.run_id.iloc[0]) if len(predictions) else (
                f"{row.domain}_rc_sem_cached_common_v1_s{int(row.seed):03d}_b{int(row.budget):03d}"
                if row.method == METHOD_RCSEM else
                f"{row.domain}_arc_cached_replay_v1_s{int(row.seed):03d}_b{int(row.budget):03d}"
            ),
            "method": row.method,
            "method_variant": row.method_variant,
            "seed": int(row.seed),
            "horizon_budget": int(row.budget),
        }
        _, metrics = bench.evaluate_events(predictions, reference, meta, "recheck")
        values = dict(zip(metrics.metric_name, metrics.metric_value))
        for metric in METRICS:
            if not math.isclose(float(getattr(row, metric)), float(values[metric]), rel_tol=0.0, abs_tol=1e-12):
                failures.append(f"metric:{row.method}:{row.domain}:{row.seed}:{row.budget}:{metric}")
        trace = pd.read_csv(output.parent.parent / row.selection_trace_path)
        if trace.unit_id.duplicated().any():
            failures.append(f"duplicate:{row.method}:{row.domain}:{row.seed}:{row.budget}")
        recomputed += 1
    diagnostics = pd.read_csv(output / "rcsem_per_run_diagnostics.csv")
    if int(diagnostics.probable_event_count.sum()) != 0:
        failures.append("unexpected_probable_admission")
    if diagnostics.risk_threshold_found.astype(bool).any():
        failures.append("unexpected_safe_threshold")
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "expected_runs": expected_runs,
        "completed_runs": len(per_run),
        "metrics_recomputed": recomputed,
        "same_input_schema": True,
        "output_schema_checks": schema_pairs,
        "all_calls_within_budget_cap": bool(
            (per_run.logical_oracle_calls <= per_run.budget).all()
        ),
        "rcsem_exact_budget_accounting": bool(
            (rcsem_budget.logical_oracle_calls == rcsem_budget.budget).all()
        ),
        "zero_duplicate_queries": not any(item.startswith("duplicate:") for item in failures),
        "zero_probable_events_after_failed_gate": int(diagnostics.probable_event_count.sum()) == 0,
        "deterministic_rcsem_seed_rows": bool(
            per_run[per_run.method == METHOD_RCSEM]
            .groupby(["domain", "budget"])[["event_precision", "event_recall", "event_f1"]]
            .nunique()
            .le(1)
            .all()
            .all()
        ),
    }


def execute(arc_root: Path, output: Path) -> None:
    if output.exists():
        raise RuntimeError(f"refusing to overwrite existing output: {output}")
    benchmark_lib = arc_root / (
        "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/"
        "clean_baseline_benchmark_v2_strict/scripts/benchmark_lib.py"
    )
    evaluator_hash = sha256_file(benchmark_lib)
    if evaluator_hash != EXPECTED_EVALUATOR_HASH:
        raise RuntimeError("shared evaluator hash changed")
    bench = load_module("arc_rcsem_common_benchmark", benchmark_lib)
    domains, frozen_manifest = load_domains(arc_root)

    output.mkdir(parents=True)
    arc_rows = copy_arc_runs(arc_root, output)
    rcsem_rows: list[dict[str, object]] = []
    diagnostic_rows: list[dict[str, object]] = []
    calibration_rows: list[dict[str, object]] = []

    # The single-feature logistic fit is deterministic; random_state does not
    # affect its solver.  Cache once per held-out source video so repeated seed
    # rows remain pairing rows without needlessly repeating the event-level
    # threshold enumeration.
    calibration_cache: dict[str, tuple[object, EventRiskThreshold | None, list[Domain]]] = {}
    for heldout_video in sorted({domain.video_id for domain in domains}):
        training_domains = [row for row in domains if row.video_id != heldout_video]
        if not training_domains:
            raise RuntimeError(f"no cross-source training data for {heldout_video}")
        model = fit_cross_source_posterior(training_domains, SEEDS[0])
        threshold = choose_event_risk_threshold(training_domains, model, bench)
        calibration_cache[heldout_video] = (model, threshold, training_domains)

    for heldout in domains:
        model, threshold, training_domains = calibration_cache[heldout.video_id]
        for seed in SEEDS:
            scored = score_domain(heldout, model)
            ranking = label_hidden_ranking(scored[["unit_id", "proxy_score", "posterior_score"]])
            calibration_rows.append(
                {
                    "heldout_domain": heldout.name,
                    "heldout_video_id": heldout.video_id,
                    "training_domains": "|".join(row.name for row in training_domains),
                    "training_video_ids": "|".join(sorted({row.video_id for row in training_domains})),
                    "seed": seed,
                    "logistic_intercept": float(model.intercept_[0]),
                    "logistic_proxy_coefficient": float(model.coef_[0, 0]),
                    "risk_threshold_found": threshold is not None,
                    **(
                        {
                            "risk_posterior_threshold": threshold.posterior_threshold,
                            "risk_training_predicted_events": threshold.predicted_events,
                            "risk_training_matched_events": threshold.matched_events,
                            "risk_training_empirical_precision": threshold.empirical_precision,
                            "risk_training_wilson_lower_95": threshold.wilson_lower_95,
                        }
                        if threshold is not None
                        else {
                            "risk_posterior_threshold": math.nan,
                            "risk_training_predicted_events": 0,
                            "risk_training_matched_events": 0,
                            "risk_training_empirical_precision": math.nan,
                            "risk_training_wilson_lower_95": math.nan,
                        }
                    ),
                }
            )
            for budget in BUDGETS:
                trace = reveal_trace(heldout, ranking, budget)
                meta = run_meta(heldout, seed, budget)
                predictions, probable_count = materialize_combined(
                    heldout, trace, scored, threshold, meta, bench
                )
                row, _ = save_rcsem_run(
                    output, heldout, seed, budget, trace, predictions, bench, evaluator_hash
                )
                rcsem_rows.append(row)
                diagnostic_rows.append(
                    {
                        "domain": heldout.name,
                        "video_id": heldout.video_id,
                        "seed": seed,
                        "budget": budget,
                        "training_domains": "|".join(row.name for row in training_domains),
                        "risk_threshold_found": threshold is not None,
                        "probable_event_count": probable_count,
                        "verified_event_count": row["verified_event_count"],
                        "returned_event_count": row["returned_event_count"],
                    }
                )

    per_run = pd.concat([arc_rows, pd.DataFrame(rcsem_rows)], ignore_index=True)
    per_run = per_run.sort_values(["domain", "method", "seed", "budget"]).reset_index(drop=True)
    per_run.to_csv(output / "per_run_metrics.csv", index=False)
    diagnostics = pd.DataFrame(diagnostic_rows)
    diagnostics.to_csv(output / "rcsem_per_run_diagnostics.csv", index=False)
    pd.DataFrame(calibration_rows).to_csv(output / "cross_source_calibration.csv", index=False)
    curves, auc, paired = aggregate(per_run)
    curves.to_csv(output / "macro_curve.csv", index=False)
    auc.to_csv(output / "macro_auc.csv", index=False)
    paired.to_csv(output / "paired_comparison.csv", index=False)
    report_dir = output / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "ARC_RCSEM_COMMON_REPLAY_REPORT.md").write_text(
        build_report(curves, auc, diagnostics), encoding="utf-8"
    )

    provenance = {
        "classification": "exploratory_cached_logical_call_replay_not_physical",
        "arc_root": str(arc_root),
        "arc_source_output": str(arc_root / "outputs/arc_cached_replay_v1"),
        "arc_source_reported_whole_tree_hash": "05d63af1f7daced4979191214c3bf0e237ae02f083cbc1523ac1069456cd42d2",
        "frozen_manifest_hash": sha256_file(
            arc_root / "BSEC_AQP_Development_Gate_v1/outputs/native_arc_vs_pstr/manifest.json"
        ),
        "evaluator_hash": evaluator_hash,
        "dataset3_prompt_hash": EXPECTED_DATASET3_PROMPT_HASH,
        "dataset3_prompt_parser_identity": "complete",
        "realcartest_prompt_parser_identity": "missing_in_frozen_derivative",
        "input_hashes": {domain.name: domain.hashes for domain in domains},
        "frozen_manifest_dataset_count": len(frozen_manifest["datasets"]),
    }
    write_json(output / "DATA_PROVENANCE.json", provenance)
    config = {
        "method": METHOD_RCSEM,
        "method_variant": METHOD_VARIANT,
        "budgets": list(BUDGETS),
        "seeds": list(SEEDS),
        "posterior": {
            "family": "single-feature class-balanced logistic regression",
            "feature": "proxy_score",
            "C": 0.5,
            "training_split": "exclude every domain from heldout source video",
        },
        "risk_gate": {
            "precision_floor": PRECISION_FLOOR,
            "confidence": "Wilson 95% lower bound",
            "minimum_event_admissions": MINIMUM_EVENT_ADMISSIONS,
            "unit": "strict-K3 predicted event",
            "failure_semantics": "publish zero probable events",
        },
        "k3": {"name": "k3_bridge_safe", **K3_CONFIG},
        "evaluator_hash": evaluator_hash,
    }
    config["config_hash"] = canonical_hash(config)
    write_json(output / "CONFIG.json", config)

    checks = validate_outputs(output, arc_root, bench)
    if checks["status"] != "PASS":
        write_json(output / "validation_checks.json", checks)
        raise RuntimeError(f"output validation failed: {checks['failures'][:5]}")
    write_json(output / "validation_checks.json", checks)
    artifacts, aggregate_hash = artifact_inventory(output)
    artifacts.to_csv(output / "ARTIFACT_HASHES.csv", index=False)
    manifest = {
        "schema_version": "ARC_RCSEM_COMMON_REPLAY_V1",
        "status": "PASS_WITH_DISCLOSED_LIMITATIONS",
        "methods": [METHOD_ARC, METHOD_RCSEM],
        "run_count": len(per_run),
        "artifact_count": len(artifacts),
        "artifact_inventory_aggregate_hash": aggregate_hash,
        "config_hash": config["config_hash"],
        "decision": "VERIFIED_SCHEDULING_UPLIFT_ONLY_NO_SPECULATIVE_EVIDENCE",
    }
    write_json(output / "RUN_MANIFEST.json", manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--arc-root",
        type=Path,
        default=Path("/root/charm/GVAQP-arc-phys-baseline"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/arc_rcsem_common_replay"),
    )
    args = parser.parse_args()
    execute(args.arc_root.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
