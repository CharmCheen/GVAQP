#!/usr/bin/env python3
"""Evaluate frozen PNIR on fitting datasets and its disjoint confirmatory interval."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd


PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parent
PROTOCOL = PACKAGE / "config" / "frozen_continuation_v2.json"
EXPECTED_PROTOCOL_SHA256 = "f62800ece1edee2751afa646efe8d8d344dd8a04de3b1392c9845d0aa15e1daa"
BASE_RUNNER = PACKAGE / "scripts" / "run_frozen_gate.py"
ARC_ADAPTER = REPO / "refe_repos" / "adapter" / "arc_baseline" / "run.py"


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_base_runner():
    spec = importlib.util.spec_from_file_location("bsec_frozen_gate", BASE_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {BASE_RUNNER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


G = load_base_runner()
from benchmark_lib import canonicalize_native_segments, evaluate_events  # noqa: E402


def interleave_rankings(
    peak_ranking: list[int], nms_ranking: list[int], peak_quota: int = 1, nms_quota: int = 3
) -> list[int]:
    output: list[int] = []
    selected: set[int] = set()
    peak_index = 0
    nms_index = 0

    def emit(source: list[int], index: int, quota: int) -> int:
        emitted = 0
        while emitted < quota and index < len(source):
            unit_id = source[index]
            index += 1
            if unit_id in selected:
                continue
            output.append(unit_id)
            selected.add(unit_id)
            emitted += 1
        return index

    while len(output) < len(peak_ranking):
        before = len(output)
        peak_index = emit(peak_ranking, peak_index, peak_quota)
        nms_index = emit(nms_ranking, nms_index, nms_quota)
        if len(output) == before:
            raise RuntimeError("PNIR merge stalled")
    if sorted(output) != list(range(len(peak_ranking))):
        raise RuntimeError("PNIR merge is not a permutation")
    return output


def method_rankings(data: dict) -> dict[str, list[int]]:
    clip = G.stable_order(data["scores"])
    qtpc = G.qtpc_ranking(data["scores"], radius=8)[0]
    nms = G.temporal_nms_ranking(data["scores"], radius=10)
    pnir = interleave_rankings(qtpc, nms, 1, 3)
    return {"clip_topk": clip, "qtpc_h8": qtpc, "temporal_nms_h10": nms, "pnir_1_3": pnir}


def reference_from_grid(grid: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, event in events.iterrows():
        source = grid.loc[grid.event_id.astype(str) == str(event.event_id), "bin_idx"].astype(int)
        rows.append(
            {
                "benchmark_id": "confirm_realcartest_0_1570",
                "video_id": "realcartest",
                "reference_event_id": str(event.event_id),
                "start_time": float(event.t_start),
                "core_start_time": float(event.t_start),
                "core_end_time": float(event.t_end),
                "end_time": float(event.t_end),
                "canonical_anchor_time": float(event.t_start),
                "source_unit_ids": "|".join(map(str, source.tolist())),
                "event_type": str(event.event_type),
                "reference_type": "VLM_DEFINED_PSEUDO_ORACLE",
                "reference_version": "late_aqp_frozen_cross_segment_v1",
                "adjudication_status": "not_human_adjudicated",
            }
        )
    return pd.DataFrame(rows)


def load_confirmatory(config: dict, output: Path) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    spec = config["confirmatory"]
    grid_path = REPO / spec["units_and_oracle"]
    reference_path = REPO / spec["reference"]
    if sha256_file(grid_path) != spec["units_and_oracle_sha256"]:
        raise RuntimeError("confirmatory grid changed after freeze")
    if sha256_file(reference_path) != spec["reference_sha256"]:
        raise RuntimeError("confirmatory reference changed after freeze")
    grid = pd.read_csv(grid_path)
    events = pd.read_csv(reference_path)
    if grid.bin_idx.astype(int).tolist() != list(range(157)) or len(events) != 20:
        raise RuntimeError("confirmatory population mismatch")
    units = pd.DataFrame(
        {
            "benchmark_id": "confirm_realcartest_0_1570",
            "video_id": "realcartest",
            "unit_id": grid.bin_idx.astype(int),
            "frame_idx": grid.bin_idx.astype(int),
            "start_time": grid.t_start.astype(float),
            "end_time": grid.t_end.astype(float),
        }
    )
    labels = {
        int(row.bin_idx): ("positive" if bool(row.is_positive) else "negative")
        for _, row in grid.iterrows()
    }
    reference = reference_from_grid(grid, events)
    inference = output / "clip_inference"
    complete = json.loads((inference / "INFERENCE_COMPLETE.json").read_text(encoding="utf-8"))
    if complete["frozen_protocol_sha256"] != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("confirmatory ranking used another protocol")
    scores = pd.read_csv(inference / "clip_scores.csv").sort_values("unit_id").score.to_numpy(float)
    if len(scores) != len(units):
        raise RuntimeError("confirmatory score coverage mismatch")
    data = {
        "name": "confirmatory",
        "benchmark_id": "confirm_realcartest_0_1570",
        "units": units,
        "reference": reference,
        "labels": labels,
        "scores": scores,
        "proxy_scores": grid.prior_score_max.to_numpy(float),
    }
    return data, grid, events


def write_adapter_inputs(grid: pd.DataFrame, events: pd.DataFrame, output: Path) -> tuple[Path, Path]:
    input_dir = output / "adapter_inputs"
    input_dir.mkdir(parents=True, exist_ok=True)
    frame_path = input_dir / "frame_scores_adapter_ready.csv"
    reference_path = input_dir / "reference_segments_adapter_ready.csv"
    frame = pd.DataFrame(
        {
            "video_id": "realcartest",
            "frame_idx": grid.bin_idx.astype(int),
            "timestamp": grid.t_start.astype(float),
            "proxy_score": grid.prior_score_max.astype(float).clip(0.0, 1.0),
            "oracle_label": grid.is_positive.astype(int),
            "start_frame": (grid.t_start.astype(float) * 10).round().astype(int),
            "end_frame": (grid.t_end.astype(float) * 10).round().astype(int) - 1,
            "start_time": grid.t_start.astype(float),
            "end_time": grid.t_end.astype(float),
        }
    )
    reference = pd.DataFrame(
        {
            "video_id": "realcartest",
            "segment_id": np.arange(len(events), dtype=int),
            "start_frame": (events.t_start.astype(float) * 10).round().astype(int),
            "end_frame": (events.t_end.astype(float) * 10).round().astype(int) - 1,
            "start_time": events.t_start.astype(float),
            "end_time": events.t_end.astype(float),
            "event_type": events.event_type.astype(str),
            "source_event_id": events.event_id.astype(str),
        }
    )
    frame.to_csv(frame_path, index=False)
    reference.to_csv(reference_path, index=False)
    return frame_path, reference_path


def run_arc_adapter(
    frame_path: Path, reference_path: Path, budgets: list[int], output: Path
) -> dict[tuple[int, int], Path]:
    run_root = output / "arc_adapter_runs"
    run_root.mkdir(parents=True, exist_ok=True)
    paths = {}
    for seed in range(5):
        for budget in budgets:
            run_id = f"arc_refinement_th0.4_s{seed:03d}_b{budget}"
            run_dir = run_root / run_id
            command = [
                sys.executable,
                str(ARC_ADAPTER),
                "--input",
                str(frame_path),
                "--output-dir",
                str(run_dir),
                "--reference-segments",
                str(reference_path),
                "--budget",
                str(budget),
                "--seed",
                str(seed),
                "--run-id",
                run_id,
                "--variant",
                "refinement",
                "--threshold",
                "0.4",
                "--cluster-mode",
                "each_frame",
            ]
            completed = subprocess.run(command, cwd=REPO, text=True, capture_output=True)
            if completed.returncode != 0:
                raise RuntimeError(
                    f"ARC adapter failed: {' '.join(command)}\n"
                    f"stdout={completed.stdout}\nstderr={completed.stderr}"
                )
            paths[(seed, budget)] = run_dir
    return paths


def evaluate_static_curve(
    data: dict, method: str, ranking: list[int], budgets: list[int], evaluator_hash: str
) -> list[dict]:
    rows = []
    for budget in budgets:
        row, _, _, _ = G.evaluate_selection(
            data, method, "frozen_continuation_v2", 0, budget, ranking[:budget], evaluator_hash
        )
        rows.append(row)
    return rows


def evaluate_arc_curves(
    data: dict,
    arc_paths: dict[tuple[int, int], Path],
    budgets: list[int],
    evaluator_hash: str,
) -> tuple[list[dict], list[dict]]:
    shared_rows = []
    native_rows = []
    proxy_order = G.stable_order(data["proxy_scores"])
    for (seed, budget), run_dir in sorted(arc_paths.items()):
        oracle_log = pd.read_csv(run_dir / "oracle_log.csv")
        ranking = oracle_log.sort_values("call_idx").unit_id.astype(int).tolist()
        seen = set(ranking)
        ranking.extend(unit_id for unit_id in proxy_order if unit_id not in seen)
        ranking = ranking[:budget]
        row, _, _, _ = G.evaluate_selection(
            data,
            "arc_shared_k3",
            "threshold_0.4_exact_fill",
            seed,
            budget,
            ranking,
            evaluator_hash,
        )
        shared_rows.append(row)

        trace = pd.DataFrame(
            {
                "unit_id": oracle_log.unit_id.astype(int),
                "oracle_label_after_query": [
                    data["labels"][int(unit_id)] for unit_id in oracle_log.unit_id
                ],
            }
        )
        meta = {
            "benchmark_id": data["benchmark_id"],
            "run_id": f"confirm_arc_native_s{seed:03d}_b{budget}",
            "method": "arc_native_descriptive",
            "method_variant": "threshold_0.4_native",
            "seed": seed,
            "horizon_budget": budget,
        }
        native_source = pd.read_csv(run_dir / "segments.csv")
        predicted = canonicalize_native_segments(
            native_source,
            trace,
            data["units"],
            meta,
            "arc_native_adapter",
            {"threshold": 0.4, "cluster_mode": "each_frame"},
        )
        _, metrics = evaluate_events(predicted, data["reference"], meta, evaluator_hash)
        metric_map = dict(zip(metrics.metric_name, metrics.metric_value))
        native_rows.append(
            {
                "dataset": data["name"],
                "method": "arc_native_descriptive",
                "method_variant": "threshold_0.4_native",
                "seed": seed,
                "budget": budget,
                "exact_oracle_calls": len(oracle_log),
                **{key: float(value) for key, value in metric_map.items()},
            }
        )
    return shared_rows, native_rows


def add_random_and_oracle(
    data: dict, budgets: list[int], evaluator_hash: str
) -> list[dict]:
    rows = []
    for seed in range(100):
        ranking = (
            np.random.default_rng(20260713 + seed)
            .permutation(len(data["scores"]))
            .astype(int)
            .tolist()
        )
        for budget in budgets:
            row, _, _, _ = G.evaluate_selection(
                data, "random", "uniform_nested", seed, budget, ranking[:budget], evaluator_hash
            )
            rows.append(row)
    oracle = G.oracle_ranking(data)
    rows.extend(evaluate_static_curve(data, "oracle_ceiling", oracle, budgets, evaluator_hash))
    return rows


def curve_auc(rows: pd.DataFrame, budgets: list[int]) -> tuple[pd.DataFrame, pd.DataFrame]:
    return G.summarize(rows, budgets)


def fitting_replay(config: dict, budgets: list[int], evaluator_hash: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    datasets = [G.load_development(json.loads(G.FROZEN.read_text())), G.load_heldout(json.loads(G.FROZEN.read_text()))]
    rows = []
    for data in datasets:
        for method, ranking in method_rankings(data).items():
            rows.extend(evaluate_static_curve(data, method, ranking, budgets, evaluator_hash))
    per_run = pd.DataFrame(rows)
    summary, auc = curve_auc(per_run, budgets)
    return summary, auc


def manifest(root: Path) -> pd.DataFrame:
    rows = []
    for path in sorted(root.rglob("*")):
        if (
            path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix != ".pyc"
            and path.name not in {
            "OUTPUT_MANIFEST.csv",
            "CONTINUATION_OUTPUT_MANIFEST.csv",
            "FINAL_OUTPUT_MANIFEST.csv",
            }
        ):
            rows.append(
                {
                    "path": str(path.relative_to(PACKAGE)),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=PACKAGE / "outputs" / "confirmatory"
    )
    args = parser.parse_args()
    if sha256_file(PROTOCOL) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("continuation protocol changed after freeze")
    config = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    budgets = [int(value) for value in config["budgets"]]
    evaluator_hash = sha256_file(G.STRICT / "scripts" / "benchmark_lib.py")
    data, grid, events = load_confirmatory(config, args.output)
    frame_path, reference_path = write_adapter_inputs(grid, events, args.output)
    arc_paths = run_arc_adapter(frame_path, reference_path, budgets, args.output)

    rows = []
    for method, ranking in method_rankings(data).items():
        rows.extend(evaluate_static_curve(data, method, ranking, budgets, evaluator_hash))
    shared_arc, native_arc = evaluate_arc_curves(data, arc_paths, budgets, evaluator_hash)
    rows.extend(shared_arc)
    rows.extend(native_arc)
    rows.extend(add_random_and_oracle(data, budgets, evaluator_hash))
    per_run = pd.DataFrame(rows)
    summary, auc = curve_auc(per_run, budgets)
    per_run.to_csv(args.output / "per_budget_runs.csv", index=False)
    summary.to_csv(args.output / "per_budget_summary.csv", index=False)
    auc.to_csv(args.output / "event_f1_auc.csv", index=False)

    fitting_summary, fitting_auc = fitting_replay(config, budgets, evaluator_hash)
    fitting_summary.to_csv(args.output / "fitting_replay_summary.csv", index=False)
    fitting_auc.to_csv(args.output / "fitting_replay_auc.csv", index=False)

    def auc_value(method: str) -> float:
        row = auc[auc.method == method]
        if len(row) != 1:
            raise RuntimeError(f"missing confirmatory AUC for {method}")
        return float(row.event_f1_auc.iloc[0])

    pnir_auc = auc_value("pnir_1_3")
    clip_auc = auc_value("clip_topk")
    nms_auc = auc_value("temporal_nms_h10")
    arc_auc = auc_value("arc_shared_k3")
    pnir_curve = summary[summary.method == "pnir_1_3"].set_index("budget").event_f1_mean
    arc_curve = summary[summary.method == "arc_shared_k3"].set_index("budget").event_f1_mean
    budget_wins = int((pnir_curve > arc_curve).sum())
    primary = pnir_auc > clip_auc and pnir_auc > arc_auc
    contribution = pnir_auc > nms_auc
    budget_consistency = budget_wins >= 4
    primary_methods = per_run[
        per_run.method.isin(
            ["pnir_1_3", "clip_topk", "qtpc_h8", "temporal_nms_h10", "arc_shared_k3"]
        )
    ]
    fairness = bool(
        np.allclose(
            primary_methods.exact_oracle_calls.to_numpy(float),
            primary_methods.budget.to_numpy(float),
        )
    )
    passed = primary and contribution and budget_consistency and fairness
    decision = {
        "frozen_protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "confirmatory_interval": "realcartest_0_1570",
        "pnir_event_f1_auc": pnir_auc,
        "clip_event_f1_auc": clip_auc,
        "temporal_nms_event_f1_auc": nms_auc,
        "arc_shared_k3_event_f1_auc": arc_auc,
        "pnir_budget_wins_over_arc_shared_k3": budget_wins,
        "primary_pass": primary,
        "independent_contribution_pass": contribution,
        "budget_consistency_pass": budget_consistency,
        "exact_call_fairness_pass": fairness,
        "decision": "CONFIRMED_GO" if passed else "NO_GO_CONTINUE_SEARCH",
        "physical_exact_oracle_vlm_calls": 0,
        "claim_limit": config["claim_limit"],
    }
    (args.output / "CONTINUATION_GATE_DECISION.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest(PACKAGE).to_csv(PACKAGE / "CONTINUATION_OUTPUT_MANIFEST.csv", index=False)
    print(json.dumps(decision, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
