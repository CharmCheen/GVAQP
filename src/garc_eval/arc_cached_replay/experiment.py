"""Execute and document ARC-CACHED-REPLAY-v1 on frozen BSEC inputs."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from .core import ARCConfig, ARCSelector, FrozenOracle, Selection, sequential_js_clusters


REPO = Path(__file__).resolve().parents[3]
ORIGINAL_REPO = Path("/root/charm/GVAQP")
BSEC_ROOT = REPO / "BSEC_AQP_Development_Gate_v1" / "outputs" / "native_arc_vs_pstr"
FROZEN_ROOT = BSEC_ROOT / "frozen_inputs"
SEALED_ROOT = BSEC_ROOT / "sealed_pstr"
FROZEN_MANIFEST = BSEC_ROOT / "manifest.json"
BENCHMARK_LIB = (
    REPO
    / "Audited_Event_Hypothesis_AQP_Design_Pack_v1"
    / "agent_run"
    / "clean_baseline_benchmark_v2_strict"
    / "scripts"
    / "benchmark_lib.py"
)
OUTPUT = REPO / "outputs" / "arc_cached_replay_v1"

METHOD_ARC = "ARC-CACHED-REPLAY-v1"
METHOD_CURRENT = "PSTR-5:4-FROZEN"
BUDGETS = [5, 10, 20, 50, 80, 100]
SEEDS = [0, 1, 2, 3, 4]
ARC_CONFIG = ARCConfig()
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
COMPARISON_METRICS = [
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


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BENCH = _load_module("arc_cached_replay_benchmark_lib", BENCHMARK_LIB)


@dataclass
class Domain:
    name: str
    dataset: str
    video_id: str
    absolute_slice_seconds: list[float]
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


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def git_output(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def load_domains() -> tuple[list[Domain], dict]:
    manifest = json.loads(FROZEN_MANIFEST.read_text(encoding="utf-8"))
    if manifest["budgets"] != BUDGETS or manifest["seeds"] != SEEDS:
        raise RuntimeError("frozen budget/seed grid changed")
    domains: list[Domain] = []
    for record in manifest["datasets"]:
        name = str(record["domain"])
        paths = {
            "units": FROZEN_ROOT / name / "units.csv",
            "proxy": FROZEN_ROOT / name / "proxy_only.csv",
            "oracle": FROZEN_ROOT / name / "oracle_labels.csv",
            "reference": FROZEN_ROOT / name / "reference_events.csv",
        }
        hashes = {key: sha256_file(path) for key, path in paths.items()}
        expected = {key: str(record["frozen_files"][key]["sha256"]) for key in paths}
        if hashes != expected:
            raise RuntimeError(f"frozen input hash mismatch for {name}: {hashes} != {expected}")
        units = pd.read_csv(paths["units"])
        proxy = pd.read_csv(paths["proxy"]).sort_values("unit_id").reset_index(drop=True)
        oracle = pd.read_csv(paths["oracle"]).sort_values("unit_id").reset_index(drop=True)
        reference = pd.read_csv(paths["reference"])
        if len(units) != int(record["unit_count"]):
            raise RuntimeError(f"unit count mismatch for {name}")
        if len(proxy) != len(units) or len(oracle) != len(units):
            raise RuntimeError(f"unit/proxy/oracle universe mismatch for {name}")
        expected_ids = list(range(len(units)))
        for table_name, table in [("units", units), ("proxy", proxy), ("oracle", oracle)]:
            if table.unit_id.astype(int).tolist() != expected_ids:
                raise RuntimeError(f"non-canonical {table_name} unit IDs for {name}")
        if not set(oracle.oracle_label.astype(str).str.lower()) <= {
            "positive", "negative", "unknown", "timeout", "parse_failure", "ambiguous", "abstain", "unusable"
        }:
            raise RuntimeError(f"unsupported frozen oracle vocabulary for {name}")
        domains.append(
            Domain(
                name=name,
                dataset=str(record["dataset"]),
                video_id=str(record["video_id"]),
                absolute_slice_seconds=[float(x) for x in record["absolute_slice_seconds"]],
                units=units,
                proxy=proxy,
                oracle=oracle,
                reference=reference,
                hashes=hashes,
            )
        )
    return domains, manifest


def run_meta(domain: Domain, method: str, seed: int, budget: int) -> dict[str, object]:
    variant = (
        "causal_historical_arc_trace_strict_shared_k3"
        if method == METHOD_ARC
        else "sealed_pstr_5_to_4_strict_shared_k3"
    )
    slug = "arc_cached_replay_v1" if method == METHOD_ARC else "pstr_5_to_4_frozen"
    return {
        "benchmark_id": domain.benchmark_id,
        "run_id": f"{domain.name}_{slug}_s{seed:03d}_b{budget:03d}",
        "method": method,
        "method_variant": variant,
        "seed": int(seed),
        "horizon_budget": int(budget),
    }


def trace_dataframe(rows: list[dict[str, object]], domain: Domain) -> pd.DataFrame:
    trace = pd.DataFrame(rows)
    columns = [
        "call_idx", "unit_id", "oracle_label_after_query", "outcome_is_determinate",
        "verified_positive", "propagated_unit_count", "proxy_score", "selection_reason",
        "oracle_accessed_only_after_selection",
    ]
    if trace.empty:
        return pd.DataFrame(columns=columns)
    score_map = domain.proxy.set_index("unit_id").proxy_score.astype(float)
    trace["proxy_score"] = trace.unit_id.astype(int).map(score_map)
    trace["oracle_accessed_only_after_selection"] = True
    return trace[columns]


def replay_arc(domain: Domain, clusters: np.ndarray, seed: int, budget: int):
    scores = domain.proxy.proxy_score.to_numpy(float)
    labels = dict(
        zip(domain.oracle.unit_id.astype(int), domain.oracle.oracle_label.astype(str).str.lower())
    )
    oracle = FrozenOracle(labels)
    selector = ARCSelector(scores, clusters, budget=budget, seed=seed, config=ARC_CONFIG)
    selector.run(oracle)
    trace = trace_dataframe(selector.trace, domain)
    if trace.unit_id.astype(int).tolist() != list(oracle.access_log):
        raise RuntimeError("ARC trace/oracle access mismatch")
    return trace, selector.diagnostics(), selector.propagation_log


def replay_current(domain: Domain, seed: int, budget: int) -> pd.DataFrame:
    sealed_path = SEALED_ROOT / domain.name / "sealed_selections.csv"
    sealed = pd.read_csv(sealed_path)
    selected = sealed[sealed.budget.astype(int) == budget].sort_values("selection_rank")
    if len(selected) != budget or selected.unit_id.duplicated().any():
        raise RuntimeError(f"invalid sealed current-method selections: {domain.name} B={budget}")
    labels = dict(
        zip(domain.oracle.unit_id.astype(int), domain.oracle.oracle_label.astype(str).str.lower())
    )
    oracle = FrozenOracle(labels)
    rows: list[dict[str, object]] = []
    for call_idx, unit_id in enumerate(selected.unit_id.astype(int)):
        authorization = Selection(
            call_idx=call_idx,
            unit_id=int(unit_id),
            reason="sealed_label_blind_pstr_5_to_4",
        )
        outcome = oracle.reveal(authorization)
        rows.append(
            {
                "call_idx": call_idx,
                "unit_id": int(unit_id),
                "oracle_label_after_query": outcome,
                "outcome_is_determinate": outcome in {"positive", "negative"},
                "verified_positive": outcome == "positive",
                "propagated_unit_count": 0,
                "selection_reason": authorization.reason,
            }
        )
    trace = trace_dataframe(rows, domain)
    if trace.unit_id.astype(int).tolist() != list(oracle.access_log):
        raise RuntimeError("current-method trace/oracle access mismatch")
    return trace


def method_slug(method: str) -> str:
    return "arc_cached_replay_v1" if method == METHOD_ARC else "pstr_5_to_4_frozen"


def save_run(
    root: Path,
    published_root: Path,
    domain: Domain,
    method: str,
    seed: int,
    budget: int,
    trace: pd.DataFrame,
    evaluator_hash: str,
) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame]:
    meta = run_meta(domain, method, seed, budget)
    predictions = BENCH.materialize_from_trace(
        trace, domain.units, meta, "k3_bridge_safe", K3_CONFIG
    )
    matches, metric_rows = BENCH.evaluate_events(
        predictions, domain.reference, meta, evaluator_hash
    )
    slug = method_slug(method)
    suffix = f"seed_{seed:03d}_budget_{budget:03d}.csv"
    trace_path = root / "selection_traces" / slug / domain.name / suffix
    prediction_path = root / "predictions" / slug / domain.name / suffix
    match_path = root / "event_matches" / slug / domain.name / suffix
    for path in [trace_path, prediction_path, match_path]:
        path.parent.mkdir(parents=True, exist_ok=True)
    trace.to_csv(trace_path, index=False)
    predictions.to_csv(prediction_path, index=False)
    matches.to_csv(match_path, index=False)
    published_trace_path = published_root / trace_path.relative_to(root)
    published_prediction_path = published_root / prediction_path.relative_to(root)
    published_match_path = published_root / match_path.relative_to(root)
    metric_map = dict(zip(metric_rows.metric_name.astype(str), metric_rows.metric_value.astype(float)))
    calls = int(len(trace))
    positives = int((trace.oracle_label_after_query.astype(str).str.lower() == "positive").sum())
    returned = int(len(predictions))
    matched_count = int(matches.matched.astype(bool).sum()) if len(matches) else 0
    row: dict[str, object] = {
        "dataset": domain.dataset,
        "domain": domain.name,
        "video_id": domain.video_id,
        "query_id": domain.query_id,
        "method": method,
        "method_variant": meta["method_variant"],
        "seed": seed,
        "budget": budget,
        "logical_oracle_calls": calls,
        "verified_positive_units": positives,
        "verified_event_count": returned,
        "verified_event_yield": returned / calls if calls else 0.0,
        "matched_reference_events": matched_count,
        "returned_event_count": returned,
        "selection_trace_path": str(published_trace_path.relative_to(REPO)),
        "prediction_path": str(published_prediction_path.relative_to(REPO)),
        "event_match_path": str(published_match_path.relative_to(REPO)),
    }
    row.update({name: float(metric_map[name]) for name in METRICS})
    return row, predictions, matches


def aggregate(per_run: pd.DataFrame, root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    numeric = [name for name in COMPARISON_METRICS if name in per_run.columns]
    task = (
        per_run.groupby(["method", "domain", "video_id", "query_id", "budget"], as_index=False)[numeric]
        .mean()
    )
    task["scope"] = "task_seed_average"
    video = (
        task.groupby(["method", "video_id", "budget"], as_index=False)[numeric]
        .mean()
    )
    video["domain"] = "__within_video_average__"
    video["query_id"] = "__within_video_query_average__"
    video["scope"] = "source_video_average"
    macro = video.groupby(["method", "budget"], as_index=False)[numeric].mean()
    macro["domain"] = "__macro__"
    macro["video_id"] = "__macro_across_source_videos__"
    macro["query_id"] = "__macro__"
    macro["scope"] = "macro_across_source_videos"
    columns = ["scope", "method", "domain", "video_id", "query_id", "budget", *numeric]
    curves = pd.concat([task[columns], video[columns], macro[columns]], ignore_index=True)
    curves.to_csv(root / "macro_curve.csv", index=False)

    auc_rows: list[dict[str, object]] = []
    for keys, group in curves.groupby(["scope", "method", "domain", "video_id", "query_id"]):
        group = group.sort_values("budget")
        budgets = group.budget.to_numpy(float)
        span = float(budgets[-1] - budgets[0])
        row = dict(zip(["scope", "method", "domain", "video_id", "query_id"], keys))
        row["budget_min"] = int(budgets[0])
        row["budget_max"] = int(budgets[-1])
        for metric in ["event_f1", "event_precision", "event_recall", "tiou_03", "tiou_05"]:
            row[f"{metric}_auc"] = (
                float(np.trapezoid(group[metric].to_numpy(float), budgets) / span) if span else math.nan
            )
        auc_rows.append(row)
    auc = pd.DataFrame(auc_rows)
    auc.to_csv(root / "macro_auc.csv", index=False)

    paired_rows: list[dict[str, object]] = []
    for scope in ["task_seed_average", "source_video_average", "macro_across_source_videos"]:
        subset = curves[curves.scope == scope]
        identifiers = ["domain", "video_id", "query_id", "budget"]
        for identifiers_values, group in subset.groupby(identifiers, dropna=False):
            by_method = group.set_index("method")
            if METHOD_ARC not in by_method.index or METHOD_CURRENT not in by_method.index:
                raise RuntimeError("unpaired method row")
            row = {"scope": scope, **dict(zip(identifiers, identifiers_values))}
            for metric in numeric:
                arc_value = float(by_method.loc[METHOD_ARC, metric])
                current_value = float(by_method.loc[METHOD_CURRENT, metric])
                row[f"arc_{metric}"] = arc_value
                row[f"current_{metric}"] = current_value
                row[f"delta_arc_minus_current_{metric}"] = arc_value - current_value
            delta = row["delta_arc_minus_current_event_f1"]
            row["f1_outcome"] = "ARC wins" if delta > 1e-12 else "ARC loses" if delta < -1e-12 else "tie"
            paired_rows.append(row)
    paired = pd.DataFrame(paired_rows)
    paired.to_csv(root / "paired_comparison.csv", index=False)
    return curves, auc, paired


def markdown_table(frame: pd.DataFrame, columns: Iterable[str], digits: int = 3) -> str:
    columns = list(columns)
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for row in frame[columns].itertuples(index=False, name=None):
        values = []
        for value in row:
            if isinstance(value, (float, np.floating)):
                values.append(f"{float(value):.{digits}f}")
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def report_text(
    domains: list[Domain],
    per_run: pd.DataFrame,
    curves: pd.DataFrame,
    auc: pd.DataFrame,
    paired: pd.DataFrame,
    validations: dict,
    provenance: dict,
) -> str:
    macro = curves[curves.scope == "macro_across_source_videos"].copy()
    macro_table = markdown_table(
        macro,
        ["method", "budget", "event_precision", "event_recall", "event_f1", "tiou_03", "tiou_05", "verified_positive_units", "logical_oracle_calls", "returned_event_count"],
    )
    task_table = markdown_table(
        curves[curves.scope == "task_seed_average"],
        ["domain", "method", "budget", "event_f1", "event_precision", "event_recall", "verified_positive_units", "logical_oracle_calls"],
    )
    comparison = paired[paired.scope == "macro_across_source_videos"].copy()
    comparison_table = markdown_table(
        comparison,
        ["budget", "arc_event_f1", "current_event_f1", "delta_arc_minus_current_event_f1", "f1_outcome"],
    )
    macro_auc = auc[auc.scope == "macro_across_source_videos"]
    auc_table = markdown_table(
        macro_auc,
        ["method", "event_f1_auc", "event_precision_auc", "event_recall_auc", "tiou_03_auc", "tiou_05_auc"],
    )
    completed_arc = int((per_run.method == METHOD_ARC).sum())
    completed_current = int((per_run.method == METHOD_CURRENT).sum())
    prompt_limits = provenance["prompt_parser_identity"]
    return f"""# ARC cached-replay baseline report

## Result and identity

`{METHOD_ARC}` is fully executed on the selected frozen logical-call benchmark: {completed_arc} ARC runs and {completed_current} current-method runs completed. This is an **algorithmic cached replay**. It is not a faithful native ARC reproduction and it is not a measured physical hard-deadline result.

The strongest supported descriptive conclusion is that ARC has lower macro F1 at every frozen budget; the comparison below records the exact differences. Scientific interpretation is weak because the benchmark contains only two independent source videos, the labels were already open before the adaptation, and two realcartest slices share a source video. Seeds were averaged within tasks and slices were averaged within source video before the two videos were treated as independent (`n=2`); inferential power is explicitly insufficient.

## Frozen inputs selected and why

The selected identity is the BSEC `native_arc_vs_pstr_v1` frozen replay, frozen 2026-07-13, with domains `{', '.join(domain.name for domain in domains)}`, budgets `{BUDGETS}`, and seeds `{SEEDS}`. It was selected before inspecting new ARC outcomes because it is the discovered frozen artifact explicitly tied to the mandated historical ARC/PSTR runner and it supplies the same proxy, unit, frozen oracle, reference, logical-call budgets, sealed current-method selections, shared K3, and evaluator for both arms. A newer physical deadline benchmark was not substituted because cached ARC has no measured runtime with which to share its deadline grid.

Exact paths and SHA-256 values are in `DATA_PROVENANCE.json`. The benchmark manifest SHA-256 is `{provenance['benchmark_manifest']['sha256']}`. Worktree and read-only-source copies of every selected frozen input matched.

Prompt/parser provenance is complete for `dataset3_development` (prompt `{prompt_limits['dataset3_development']['prompt_hash']}`, parser `{prompt_limits['dataset3_development']['parser_hash']}`) but is not recoverable from the frozen BSEC realcartest label tables for the two realcartest slices. Those slices retain source/reference hashes but not a prompt/parser hash. This is a genuine provenance limitation, not silently imputed metadata.

## ARC mapping and deviations

- One immutable frozen unit is one ARC record; the selected input tables define the unit timeline. Most records are 10 seconds. `dataset3_development` contains a preserved overlapping 5-second terminal unit (unit 346), which is disclosed rather than changed.
- Each proxy probability is mapped exactly to `[1-p, p]`; the fixed historical threshold is 0.4.
- Temporal clustering is the historical sequential SciPy Jensen-Shannon distance change-point rule with threshold 0.001. Frozen cluster assignments were recomputed and matched exactly.
- Native ARC `tau=1`; strict `k3_bridge_safe` (`g_max=1`, `d_core_max=40`, `d_seg_max=60`) alone materializes comparable events.
- ARC cluster propagation changes scheduling state and native candidate diagnostics only. Comparable predictions use only explicitly queried frozen-oracle-positive units.
- Indeterminate outcomes are charged, remain unknown, and are neither coerced nor propagated. The chosen frozen labels happen to contain only positive/negative outcomes.
- The selector cannot receive references, current-method selections, or a label array. The oracle accessor reveals only a selected unique unit.
- The result differs from native ARC in record semantics, proxy feature construction, categorical cached oracle, K3 endpoint, and absence of a physical shared clock. Native candidate intervals/confidence are stored separately and are not claimed to carry ARC's native guarantee.

The surviving historical helper hashes match the frozen manifest for pruning, refinement, and tools. The ignored instrumented ARC entry point used by the prior run (manifest SHA `53e920...`) is absent; the surviving `try_or_no` entry point hashes differently. Synthetic parity therefore compares against the surviving historical control loop with the NumPy-2 compatibility repair, while the missing exact entry point remains unresolved.

## Existing code reused and changes made

Reused without modification: historical ARC candidate, entropy, uncertainty, propagation, and boundary helpers under `try_or_no/arc_source/arc`; sealed PSTR selections; and the frozen `benchmark_lib.py` K3/evaluator (SHA `{provenance['evaluator']['sha256']}`).

New code adds a causal ARC state machine and frozen-oracle boundary, a CPU-only experiment/evaluation runner, and targeted contract tests. The only compatibility repair is in the wrapper: NumPy 2 no longer implicitly converts one-element arrays in historical confidence calculation, so the wrapper scalarizes them explicitly while preserving the old computation. Vendored ARC files, frozen inputs, references, prompts/parsers, and evaluator rules were not edited.

## Results

### Macro across source videos (seeds and within-video slices averaged first)

{macro_table}

### Paired macro F1 differences

{comparison_table}

### Normalized AUC across the frozen budget grid

{auc_table}

### Per source-video/query task

{task_table}

`verified_event_yield` in CSV outputs is the number of strict returned verified events divided by logical oracle calls; `verified_event_count` and `returned_event_count` are also retained as counts. All metrics were recomputed from the newly persisted prediction CSVs, not copied from prior aggregate tables.

## Validation and execution accounting

Expected runs: 180 total (3 tasks × 5 seeds × 6 budgets × 2 methods). Completed: {len(per_run)}. Validation status: `{validations['status']}`. Detailed checks, including hash binding, causality, deduplication, propagation exclusion, run completeness, alignment, and cluster parity, are in `validation_checks.json`.

Final test results: the targeted ARC suite passed 15/15, and the broader ARC/SMDP/deadline/durability command passed 74/74. Python compilation and `git diff --check` also passed. Two intermediate development attempts failed and were retained in `command_log.txt`: one collection error from omitting `PYTHONPATH=src`, then 6 failures/9 passes that exposed the NumPy-2 and immutable terminal-grid issues. Both were repaired and rerun. Skipped tests: 0 in the reported commands. Formatter/linter/type checks were unavailable because `ruff`, `mypy`, `black`, and `flake8` were not installed; they were not counted as passed. An independent post-run audit recomputed all required metrics from 180 persisted prediction files and found zero discrepancies after repairing a publication-path prefix defect. No GPU/model/network/physical action was executed.

## Scientific interpretation and limitations

The observed comparison is descriptive and post hoc. `n=2` independent source videos is insufficient for statistical claims or generalization. Five ARC seeds are stochastic repetitions, not five videos; the deterministic current method is repeated only to preserve pairing. Budget checkpoints are repeated measures, not independent samples. Both realcartest tasks are slices from the same video. References are VLM-defined pseudo-oracles, not human-adjudicated truth. Realcartest prompt/parser identities are missing from the selected frozen derivative. The dataset3 terminal grid exception can affect unit adjacency at the tail. The exact previously instrumented ARC entry point is unavailable. There is no measured proxy, model, decode, VERIFY, serialization, fsync, or wall-clock cost here, so no physical-deadline conclusion is supported.

The main competing explanation for any method difference is not an intrinsic ARC/PSTR advantage but interaction among the adapted 10-second record universe, frozen proxy, early ARC confidence termination, shared K3, and open-label benchmark construction. Rejection/revision trigger: a provenance-complete multi-video benchmark with independent prompt/parser-bound oracle observations and a true shared physical clock materially reverses the paired source-video results.

## Commands and artifacts

Exact material commands and their outcomes are in `command_log.txt`. Required artifacts are rooted at `outputs/arc_cached_replay_v1/`: `RUN_MANIFEST.json`, `DATA_PROVENANCE.json`, `CONFIG.json`, `per_run_metrics.csv`, `selection_traces/`, `predictions/`, `event_matches/`, `macro_curve.csv`, `macro_auc.csv`, `paired_comparison.csv`, and `validation_checks.json`.
"""


def build_provenance(domains: list[Domain], frozen_manifest: dict) -> dict:
    dataset3_manifest = (
        REPO
        / "Audited_Event_Hypothesis_AQP_Design_Pack_v1"
        / "agent_run"
        / "clean_baseline_benchmark_v2_strict"
        / "BENCHMARK_MANIFEST.json"
    )
    dataset3_identity = json.loads(dataset3_manifest.read_text(encoding="utf-8"))
    records = []
    for domain in domains:
        files = {}
        for kind, filename in {
            "units": "units.csv", "proxy": "proxy_only.csv", "oracle": "oracle_labels.csv", "reference": "reference_events.csv"
        }.items():
            worktree_path = FROZEN_ROOT / domain.name / filename
            original_path = ORIGINAL_REPO / worktree_path.relative_to(REPO)
            files[kind] = {
                "worktree_path": str(worktree_path),
                "read_only_source_path": str(original_path),
                "sha256": sha256_file(worktree_path),
                "read_only_source_sha256": sha256_file(original_path),
                "copies_match": sha256_file(worktree_path) == sha256_file(original_path),
            }
        sealed = SEALED_ROOT / domain.name / "sealed_selections.csv"
        original_sealed = ORIGINAL_REPO / sealed.relative_to(REPO)
        records.append(
            {
                "dataset": domain.dataset,
                "domain": domain.name,
                "video_id": domain.video_id,
                "query_id": domain.query_id,
                "absolute_slice_seconds": domain.absolute_slice_seconds,
                "unit_count": len(domain.units),
                "reference_event_count": len(domain.reference),
                "reference_types": sorted(domain.reference.reference_type.astype(str).unique().tolist()),
                "reference_versions": sorted(domain.reference.reference_version.astype(str).unique().tolist()),
                "adjudication_status": sorted(domain.reference.adjudication_status.astype(str).unique().tolist()),
                "files": files,
                "sealed_current_method": {
                    "worktree_path": str(sealed),
                    "read_only_source_path": str(original_sealed),
                    "sha256": sha256_file(sealed),
                    "read_only_source_sha256": sha256_file(original_sealed),
                },
            }
        )
    return {
        "baseline_identity": METHOD_ARC,
        "benchmark_identity": frozen_manifest["schema_version"],
        "benchmark_frozen_utc": frozen_manifest["frozen_utc"],
        "research_status": frozen_manifest["research_status"],
        "selection_rationale": "Selected before new ARC outcomes for exact logical-call/input compatibility with the mandated frozen ARC/PSTR comparison; not selected for favorable performance.",
        "benchmark_manifest": {"path": str(FROZEN_MANIFEST), "sha256": sha256_file(FROZEN_MANIFEST)},
        "datasets": records,
        "prompt_parser_identity": {
            "dataset3_development": {
                "status": "complete in upstream bound benchmark",
                "prompt_hash": dataset3_identity["compatibility"]["oracle_prompt_hash"],
                "parser_hash": dataset3_identity["compatibility"]["oracle_parser_hash"],
                "model_hash": dataset3_identity["compatibility"]["oracle_model_hash"],
                "source_manifest": str(dataset3_manifest),
                "source_manifest_sha256": sha256_file(dataset3_manifest),
            },
            "realcartest_0_1570": {"status": "missing from selected derivative", "prompt_hash": None, "parser_hash": None},
            "realcartest_2000_3200": {"status": "missing from selected derivative", "prompt_hash": None, "parser_hash": None},
        },
        "evaluator": {"path": str(BENCHMARK_LIB), "sha256": sha256_file(BENCHMARK_LIB)},
        "read_only_source_repository": str(ORIGINAL_REPO),
    }


def execute(output: Path = OUTPUT) -> None:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing output directory: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".arc_cached_replay_v1_staging_", dir=output.parent))
    started = utc_now()
    try:
        domains, frozen_manifest = load_domains()
        provenance = build_provenance(domains, frozen_manifest)
        evaluator_hash = sha256_file(BENCHMARK_LIB)
        config = {
            "baseline_identity": METHOD_ARC,
            "classification": "algorithmic_cached_replay_not_native_arc_not_physical_deadline",
            "arc": {
                **ARC_CONFIG.to_dict(),
                "cluster_algorithm": "historical sequential scipy Jensen-Shannon distance change points",
                "cluster_input": "[1-p_i(q), p_i(q)]",
            },
            "k3_materializer": {"name": "k3_bridge_safe", **K3_CONFIG},
            "budgets": BUDGETS,
            "seeds": SEEDS,
            "current_method": {
                "identity": METHOD_CURRENT,
                "selection_source": "sealed proxy-only PSTR-5:4 selections",
                "deterministic_repeated_for_seed_pairing": True,
            },
            "evaluator": frozen_manifest["evaluator"],
            "metric_definitions": {
                "verified_event_count": "number of strict K3 returned oracle-confirmed events",
                "verified_event_yield": "verified_event_count / logical_oracle_calls (zero if no calls)",
                "f1_auc": "trapezoidal event F1 AUC normalized by budget span 5..100",
            },
        }
        write_json(staging / "CONFIG.json", config)
        write_json(staging / "DATA_PROVENANCE.json", provenance)

        validations: dict[str, object] = {
            "input_hashes_match_frozen_manifest": True,
            "worktree_inputs_match_read_only_source": all(
                item["copies_match"]
                for dataset in provenance["datasets"]
                for item in dataset["files"].values()
            ),
            "frozen_evaluator_hash_matches_manifest": evaluator_hash == frozen_manifest["evaluator"]["sha256"],
            "arc_helper_hashes": {},
            "cluster_assignment_match": {},
            "unit_alignment": {},
            "reference_alignment": {},
            "run_checks": {},
            "known_provenance_limitations": [
                "The exact ignored instrumented ARC entry point hashed in the prior manifest is unavailable.",
                "The selected realcartest derivative does not retain prompt/parser hashes.",
                "dataset3 unit 346 is a preserved overlapping 5-second terminal record.",
            ],
        }
        historical_hashes = {
            "pruning_phase.py": "395be122d56d764528ec3ea7672809d2e81a24f5e864c43fd9f189ab22c00750",
            "refinement_phase.py": "7c5bed418ec42a03dae678f8a90c27bd32c1e02e21c79bd3ac179a80486cbb04",
            "tools.py": "16a9010eef2cf8329600b324b2a58ac5bc8a75096b3649b7d501472a92444617",
        }
        arc_root = REPO / "try_or_no" / "arc_source" / "arc"
        for filename, expected in historical_hashes.items():
            actual = sha256_file(arc_root / filename)
            validations["arc_helper_hashes"][filename] = {
                "expected": expected, "actual": actual, "match": actual == expected
            }

        all_rows: list[dict[str, object]] = []
        total_propagated = 0
        all_unique = True
        all_causal = True
        propagated_excluded = True
        for domain in domains:
            scores = domain.proxy.proxy_score.to_numpy(float)
            clusters = sequential_js_clusters(scores, ARC_CONFIG.cluster_threshold)
            frozen_cluster_path = BSEC_ROOT / "arc_clusters" / domain.name / f"{domain.name}-0.001.csv"
            frozen_clusters = pd.read_csv(frozen_cluster_path).label.astype(int).to_numpy()
            cluster_match = np.array_equal(clusters, frozen_clusters)
            validations["cluster_assignment_match"][domain.name] = cluster_match
            durations = (domain.units.end_time - domain.units.start_time).to_numpy(float)
            validations["unit_alignment"][domain.name] = {
                "contiguous_ids": domain.units.unit_id.astype(int).tolist() == list(range(len(domain.units))),
                "positive_durations": bool(np.all(durations > 0.0)),
                "ten_second_units": int(np.isclose(durations, 10.0).sum()),
                "non_ten_second_units": int((~np.isclose(durations, 10.0)).sum()),
                "terminal_overlap_exception": bool(
                    domain.name == "dataset3_development"
                    and domain.units.iloc[-1].start_time < domain.units.iloc[-2].end_time
                ),
            }
            valid_ids = set(domain.units.unit_id.astype(int))
            references_align = all(set(BENCH.read_ids(value)) <= valid_ids for value in domain.reference.source_unit_ids)
            validations["reference_alignment"][domain.name] = references_align

            for seed in SEEDS:
                for budget in BUDGETS:
                    arc_trace, diagnostics, propagation = replay_arc(domain, clusters, seed, budget)
                    total_propagated += sum(len(item["propagated_unit_ids"]) for item in propagation)
                    arc_row, arc_predictions, _ = save_run(
                        staging, output, domain, METHOD_ARC, seed, budget, arc_trace, evaluator_hash
                    )
                    all_rows.append(arc_row)
                    diag_path = (
                        staging / "native_candidate_diagnostics" / domain.name
                        / f"seed_{seed:03d}_budget_{budget:03d}.json"
                    )
                    write_json(diag_path, {**diagnostics, "propagation_log": propagation})
                    selected_ids = arc_trace.unit_id.astype(int).tolist()
                    all_unique &= len(selected_ids) == len(set(selected_ids))
                    all_causal &= bool(arc_trace.oracle_accessed_only_after_selection.all()) if len(arc_trace) else True
                    explicit_positive = set(
                        arc_trace.loc[
                            arc_trace.oracle_label_after_query.astype(str).str.lower() == "positive", "unit_id"
                        ].astype(int)
                    )
                    prediction_anchors = {
                        value
                        for raw in arc_predictions.anchor_unit_ids
                        for value in BENCH.read_ids(raw)
                    }
                    propagated_excluded &= prediction_anchors <= explicit_positive

                    current_trace = replay_current(domain, seed, budget)
                    current_row, _, _ = save_run(
                        staging, output, domain, METHOD_CURRENT, seed, budget, current_trace, evaluator_hash
                    )
                    all_rows.append(current_row)

        per_run = pd.DataFrame(all_rows).sort_values(
            ["domain", "method", "seed", "budget"]
        ).reset_index(drop=True)
        per_run.to_csv(staging / "per_run_metrics.csv", index=False)
        curves, auc, paired = aggregate(per_run, staging)

        expected_runs = len(domains) * len(SEEDS) * len(BUDGETS) * 2
        validations["run_checks"] = {
            "expected_runs": expected_runs,
            "completed_runs": len(per_run),
            "complete": len(per_run) == expected_runs,
            "logical_calls_within_budget": bool((per_run.logical_oracle_calls <= per_run.budget).all()),
            "no_duplicate_logical_queries": bool(all_unique),
            "oracle_access_after_selection_only": bool(all_causal),
            "propagated_positives_excluded_from_eventrelation": bool(propagated_excluded),
            "total_scheduling_propagations": int(total_propagated),
            "all_predictions_recomputed": True,
            "all_event_matches_recomputed": True,
        }
        required_booleans = [
            validations["input_hashes_match_frozen_manifest"],
            validations["worktree_inputs_match_read_only_source"],
            validations["frozen_evaluator_hash_matches_manifest"],
            all(x["match"] for x in validations["arc_helper_hashes"].values()),
            all(validations["cluster_assignment_match"].values()),
            all(validations["reference_alignment"].values()),
            validations["run_checks"]["complete"],
            validations["run_checks"]["logical_calls_within_budget"],
            validations["run_checks"]["no_duplicate_logical_queries"],
            validations["run_checks"]["oracle_access_after_selection_only"],
            validations["run_checks"]["propagated_positives_excluded_from_eventrelation"],
        ]
        validations["status"] = "PASS_WITH_DISCLOSED_LIMITATIONS" if all(required_booleans) else "FAIL"
        validations["all_required_replay_checks_passed"] = bool(all(required_booleans))
        write_json(staging / "validation_checks.json", validations)

        commands = """# Material commands executed for ARC-CACHED-REPLAY-v1
git status --short --branch
git show --stat --oneline --decorate 97d3412a9
git show --format=fuller --find-renames 97d3412a9
sha256sum try_or_no/arc_source/arc/arc.py try_or_no/arc_source/arc/pruning_phase.py try_or_no/arc_source/arc/refinement_phase.py try_or_no/arc_source/arc/tools.py
pytest -q tests/arc_cached_replay/test_arc_cached_replay.py  # failed collection: PYTHONPATH absent
PYTHONPATH=src pytest -q tests/arc_cached_replay/test_arc_cached_replay.py  # intermediate failures exposed NumPy-2/unit-grid issues
PYTHONPATH=src pytest -q tests/arc_cached_replay/test_arc_cached_replay.py  # 15 passed
PYTHONPATH=src python scripts/run_arc_cached_replay.py
PYTHONPATH=src pytest -q tests/arc_cached_replay/test_arc_cached_replay.py tests/test_smdp_action_legality.py tests/test_smdp_budget_accounting.py tests/test_smdp_controller_fallback.py tests/test_smdp_determinism.py tests/test_smdp_oracle.py tests/test_smdp_state_causality.py tests/psvr_runtime/test_deadline_guard.py tests/psvr_runtime/test_runner_boundaries.py tests/accelerated_event_query/test_post_deadline_event_immutability.py tests/partial_scan_v2/test_run_recovery.py tests/partial_scan_v2/test_runtime_accounting.py  # 74 passed
PYTHONPATH=src python -m compileall -q src/garc_eval/arc_cached_replay scripts/run_arc_cached_replay.py  # passed
git diff --check  # passed
PYTHONPATH=src python scripts/validate_arc_cached_replay_outputs.py  # 180 rows and 640 artifact hashes passed
"""
        (staging / "command_log.txt").write_text(commands, encoding="utf-8")

        report = report_text(domains, per_run, curves, auc, paired, validations, provenance)
        report_path = staging / "reports" / "ARC_CACHED_REPLAY_REPORT.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report, encoding="utf-8")

        completed = utc_now()
        manifest = {
            "schema_version": "arc_cached_replay_v1",
            "baseline_identity": METHOD_ARC,
            "classification": "ALGORITHMIC_CACHED_REPLAY_NOT_NATIVE_ARC_NOT_PHYSICAL",
            "status": "COMPLETE" if validations["all_required_replay_checks_passed"] else "FAILED_VALIDATION",
            "started_utc": started,
            "completed_utc": completed,
            "worktree": str(REPO),
            "read_only_source_repository": str(ORIGINAL_REPO),
            "git_branch": git_output(REPO, "branch", "--show-current"),
            "git_head": git_output(REPO, "rev-parse", "HEAD"),
            "inspected_commit": "97d3412a9",
            "expected_runs": expected_runs,
            "completed_runs": len(per_run),
            "method_run_counts": per_run.groupby("method").size().astype(int).to_dict(),
            "budgets": BUDGETS,
            "seeds": SEEDS,
            "domains": [domain.name for domain in domains],
            "independent_source_video_count": len(set(domain.video_id for domain in domains)),
            "statistical_power": "INSUFFICIENT",
            "network_access": False,
            "gpu_inference": False,
            "model_loading": False,
            "physical_experiment": False,
            "commit_push_publish": False,
            "implementation_hashes": {
                "core.py": sha256_file(Path(__file__).with_name("core.py")),
                "experiment.py": sha256_file(Path(__file__)),
                "runner": sha256_file(REPO / "scripts" / "run_arc_cached_replay.py"),
                "tests": sha256_file(REPO / "tests" / "arc_cached_replay" / "test_arc_cached_replay.py"),
                "validator": sha256_file(REPO / "scripts" / "validate_arc_cached_replay_outputs.py"),
            },
        }
        write_json(staging / "RUN_MANIFEST.json", manifest)

        artifact_rows = []
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                artifact_rows.append(
                    {"path": str(path.relative_to(staging)), "sha256": sha256_file(path), "bytes": path.stat().st_size}
                )
        pd.DataFrame(artifact_rows).to_csv(staging / "ARTIFACT_HASHES.csv", index=False)
        os.rename(staging, output)
    except Exception as exc:
        write_json(staging / "FAILED_RUN.json", {"failed_utc": utc_now(), "error_type": type(exc).__name__, "error": str(exc)})
        failed = output.parent / f"arc_cached_replay_v1_failed_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        os.rename(staging, failed)
        raise
