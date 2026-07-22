#!/usr/bin/env python3
"""Finalize the bounded two-video research loop after adversarial review."""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/psvr_two_video_loop"
DEV = OUT / "dev_benchmark_v1"
PILOT = OUT / "proxy_finalization/neutral_psvr"
FINAL_PROXY = OUT / "final_proxy"
EXPOSE = OUT / "h_expose2"
ABLATION = OUT / "h_expose2_ablation"
TABLES = OUT / "tables"
PLOTS = OUT / "plots"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def durable_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def resolved_expose() -> tuple[dict[str, Any], Path, str]:
    decision = json.loads((EXPOSE / "DECISION.json").read_text())
    source = EXPOSE
    decision_label = "initial"
    if decision.get("H_EXPOSE2_DECISION") == "REVISE":
        revision = json.loads((EXPOSE / "REVISION_DECISION.json").read_text())
        source = EXPOSE / f"revision_{revision['revision_method']}"
        decision = json.loads((source / "DECISION.json").read_text())
        decision_label = revision["revision_id"]
    return decision, source, decision_label


def gpu_breakdown() -> dict[str, float]:
    reference_gpu = sum(
        float(json.loads(path.read_text()).get("gpu_seconds", 0.0))
        for path in (
            DEV / "raw_oracle/V1"
        ).glob("center10_anchor_*.json")
    )
    deadline_gpu = sum(
        float(
            json.loads(path.read_text())["oracle_result"]["stage_seconds"][
                "oracle_inference"
            ]
        )
        for path in (OUT / "deadlines/raw_profile").glob("*/sample_*.json")
        if not path.name.endswith("_oracle.json")
        and not path.name.endswith("_snapshot.json")
    )
    deadline_gpu += sum(
        float(
            json.loads(path.read_text()).get(
                "oracle_inference_seconds", 0.0
            )
        )
        for path in (OUT / "deadlines/raw_profile/failed_attempts").glob(
            "*_failure.json"
        )
    )
    proxy_profile_gpu = 0.0
    for path in (OUT / "proxy_finalization/physical_cost").glob(
        "*_PROFILE_SAMPLES.csv"
    ):
        proxy_profile_gpu += float(
            pd.read_csv(path)["detector_gpu_seconds"].astype(float).sum()
        )
    proxy_extraction_gpu = sum(
        float(json.loads(path.read_text()).get("detector_gpu_seconds", 0.0))
        for path in (OUT / "proxy_finalization/raw").glob(
            "*/*/FULL_VIDEO_COST.json"
        )
    )
    matrices = {}
    for name, path in {
        "proxy_pilot": PILOT / "tables/RUN_METRICS.csv",
        "h_expose2": EXPOSE / "tables/RUN_METRICS.csv",
        "h_expose2_ablation": ABLATION / "tables/RUN_METRICS.csv",
    }.items():
        matrices[name] = (
            float(pd.read_csv(path)["total_GPU_seconds"].astype(float).sum())
            if path.exists()
            else 0.0
        )
    for path in EXPOSE.glob("revision_*/tables/RUN_METRICS.csv"):
        matrices[path.parents[1].name] = float(
            pd.read_csv(path)["total_GPU_seconds"].astype(float).sum()
        )
    result = {
        "V1_exhaustive_reference_GPU_seconds": reference_gpu,
        "deadline_profile_GPU_seconds": deadline_gpu,
        "proxy_standalone_profile_GPU_seconds": proxy_profile_gpu,
        "proxy_full_extraction_GPU_seconds": proxy_extraction_gpu,
        **{f"{key}_GPU_seconds": value for key, value in matrices.items()},
    }
    result["TOTAL_GPU_SECONDS"] = float(sum(result.values()))
    return result


def main() -> None:
    required = [
        DEV / "FINAL_BENCHMARK_DECISION.json",
        PILOT / "SELECTION_DECISION.json",
        FINAL_PROXY / "FINAL_PROXY_CONFIG.json",
        OUT / "proxy_regime/PROXY_REGIME_REVALIDATION.json",
        EXPOSE / "DECISION.json",
        OUT / "ADVERSARIAL_REVIEW.md",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise RuntimeError(f"Cannot finalize; missing required artifacts: {missing}")
    benchmark = json.loads((DEV / "FINAL_BENCHMARK_DECISION.json").read_text())
    proxy = json.loads((PILOT / "SELECTION_DECISION.json").read_text())
    final_proxy = json.loads((FINAL_PROXY / "FINAL_PROXY_CONFIG.json").read_text())
    regime = json.loads(
        (OUT / "proxy_regime/PROXY_REGIME_REVALIDATION.json").read_text()
    )
    expose, expose_source, expose_label = resolved_expose()
    if benchmark.get("TWO_VIDEO_DEV_BENCHMARK") != "PASS":
        raise RuntimeError("Two-video benchmark is not PASS")
    if regime.get("PROXY_REGIME_REVALIDATION") not in {"PASS", "WEAK"}:
        raise RuntimeError("Final proxy physical regime is not usable")

    expose_status = expose["H_EXPOSE2_DECISION"]
    if expose_status == "ACCEPT_TWO_VIDEO_SIGNAL":
        if not (ABLATION / "DECISION.json").exists():
            raise RuntimeError("Accepted H-EXPOSE2 requires the preregistered ablation")
        ablation = json.loads((ABLATION / "DECISION.json").read_text())
        ablation_status = ablation["H-EXPOSE2_ABLATION"]
        core_signal = (
            "PRESENT" if ablation_status == "PASS" else "ABSENT"
        )
    elif expose_status == "REJECT":
        ablation_status = "NOT_RUN_HYPOTHESIS_REJECTED"
        core_signal = "ABSENT"
    else:
        raise RuntimeError(f"H-EXPOSE2 has no terminal decision: {expose_status}")

    metrics_path = expose_source / "tables/RUN_METRICS.csv"
    metrics = pd.read_csv(metrics_path)
    method_macro = metrics.groupby("method").agg(
        MACRO_ANYTIME_AUC=("AnytimeAUC_F1", "mean"),
        MACRO_F1=("F1_at_deadline", "mean"),
        MACRO_PRECISION=("precision", "mean"),
        MACRO_RECALL=("recall", "mean"),
        MACRO_TTFC=("TTFC_censored", "mean"),
        TOTAL_GPU_SECONDS=("total_GPU_seconds", "sum"),
    )
    if expose_status == "ACCEPT_TWO_VIDEO_SIGNAL":
        current_best = expose["target_method"]
    else:
        current_best = str(
            method_macro.sort_values(
                ["MACRO_ANYTIME_AUC", "MACRO_F1", "MACRO_TTFC"],
                ascending=[False, False, True],
            ).index[0]
        )
    selected_macro = method_macro.loc[current_best]
    high = metrics[metrics.deadline_name == "T_high"]
    total_unique = (
        float(
            high[high.method == current_best]
            .groupby("task_id")
            .unique_confirmed_events.mean()
            .sum()
        )
        if not high.empty
        else float(
            metrics[metrics.method == current_best]
            .groupby("task_id")
            .unique_confirmed_events.mean()
            .sum()
        )
    )
    gpu = gpu_breakdown()
    evidence_level = (
        "E4_TWO_VIDEO_DEVELOPMENT_SIGNAL"
        if core_signal == "PRESENT"
        else "E4_TWO_VIDEO_DEVELOPMENT_NEGATIVE_OR_NONMECHANISTIC"
    )
    audited = {
        "TWO_VIDEO_DEV_BENCHMARK": benchmark["TWO_VIDEO_DEV_BENCHMARK"],
        "SELECTED_PROXY_FAMILY": final_proxy["selected_proxy_family"],
        "SELECTED_PROXY_CONFIG": final_proxy["selected_proxy_config"],
        "PROXY_REGIME_REVALIDATION": regime["PROXY_REGIME_REVALIDATION"],
        "H_EXPOSE2_REVISION": (
            "R3_FIXED_10_SECOND_TEMPORAL_NMS_COMPLETE"
            if expose_label == "R3"
            else expose_label
        ),
        "H_EXPOSE2_DECISION": expose_status,
        "H_EXPOSE2_DECISION_SOURCE": expose_label,
        "H_EXPOSE2_ABLATION": ablation_status,
        "TWO_VIDEO_CORE_SIGNAL": core_signal,
        "MACRO_ANYTIME_AUC": float(selected_macro.MACRO_ANYTIME_AUC),
        "MACRO_F1": float(selected_macro.MACRO_F1),
        "TOTAL_UNIQUE_CONFIRMED_EVENTS": total_unique,
        "MACRO_TTFC": float(selected_macro.MACRO_TTFC),
        "TOTAL_GPU_SECONDS": gpu["TOTAL_GPU_SECONDS"],
        "GPU_BREAKDOWN": gpu,
        "DEV_SOURCE_VIDEOS": 2,
        "DEV_QUERIES": 2,
        "DEV_VIDEO_QUERIES": 4,
        "EVIDENCE_LEVEL": evidence_level,
        "HELD_OUT_OPENED": False,
        "CURRENT_BEST_PSVR_METHOD": current_best,
        "PSVR_METHOD_USABILITY": "NOT_YET",
        "PAPER_READY": False,
        "AUTONOMOUS_RESEARCH_STATUS": "PAUSED_INPUT_REQUIRED",
        "NEXT_EXACT_COMMAND": "NONE_INPUT_REQUIRED__PROVIDE_THIRD_INDEPENDENT_SOURCE_VIDEO",
    }
    audited["decision_hash"] = canonical_hash(audited)
    durable_json(OUT / "AUDITED_DECISION.json", audited)

    TABLES.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(parents=True, exist_ok=True)
    method_macro.reset_index().to_csv(
        TABLES / "FINAL_METHOD_MACRO_METRICS.csv", index=False
    )
    shutil.copy2(
        PILOT / "tables/MACRO_METRICS.csv",
        TABLES / "PROXY_PILOT_MACRO_METRICS.csv",
    )
    shutil.copy2(
        metrics_path,
        TABLES / "FINAL_H_EXPOSE2_RUN_METRICS.csv",
    )
    try:
        import matplotlib.pyplot as plt

        plot = method_macro.reset_index()
        figure, axis = plt.subplots(figsize=(7, 4))
        axis.bar(plot["method"], plot["MACRO_ANYTIME_AUC"])
        axis.set_ylabel("Macro AnytimeAUC F1")
        axis.set_title("Two-video physical PSVR")
        axis.tick_params(axis="x", rotation=20)
        figure.tight_layout()
        figure.savefig(PLOTS / "FINAL_METHOD_ANYTIME_AUC.png", dpi=160)
        plt.close(figure)
    except Exception as exc:
        durable_json(PLOTS / "PLOT_FAILURE.json", {
            "error": f"{type(exc).__name__}: {exc}"
        })

    report = f"""# PSVR Two-Video Autonomous Loop

`TWO_VIDEO_DEV_BENCHMARK = {audited['TWO_VIDEO_DEV_BENCHMARK']}`

`SELECTED_PROXY_FAMILY = {audited['SELECTED_PROXY_FAMILY']}`

`SELECTED_PROXY_CONFIG = {audited['SELECTED_PROXY_CONFIG']}`

`PROXY_REGIME_REVALIDATION = {audited['PROXY_REGIME_REVALIDATION']}`

`H_EXPOSE2_REVISION = {audited['H_EXPOSE2_REVISION']}`

`H_EXPOSE2_DECISION = {audited['H_EXPOSE2_DECISION']}`

`H_EXPOSE2_ABLATION = {audited['H_EXPOSE2_ABLATION']}`

`TWO_VIDEO_CORE_SIGNAL = {audited['TWO_VIDEO_CORE_SIGNAL']}`

`MACRO_ANYTIME_AUC = {audited['MACRO_ANYTIME_AUC']:.9f}`

`MACRO_F1 = {audited['MACRO_F1']:.9f}`

`TOTAL_UNIQUE_CONFIRMED_EVENTS = {audited['TOTAL_UNIQUE_CONFIRMED_EVENTS']:.6f}`

`MACRO_TTFC = {audited['MACRO_TTFC']:.6f}`

`TOTAL_GPU_SECONDS = {audited['TOTAL_GPU_SECONDS']:.6f}`

`DEV_SOURCE_VIDEOS = 2`

`DEV_QUERIES = 2`

`DEV_VIDEO_QUERIES = 4`

`EVIDENCE_LEVEL = {audited['EVIDENCE_LEVEL']}`

`HELD_OUT_OPENED = false`

`CURRENT_BEST_PSVR_METHOD = {audited['CURRENT_BEST_PSVR_METHOD']}`

`PSVR_METHOD_USABILITY = NOT_YET`

`AUTONOMOUS_RESEARCH_STATUS = PAUSED_INPUT_REQUIRED`

`NEXT_EXACT_COMMAND = NONE_INPUT_REQUIRED__PROVIDE_THIRD_INDEPENDENT_SOURCE_VIDEO`

## Evidence boundary

This is development evidence from two independent source videos and four
video-query tasks. It does not satisfy the three-video usability gate, does
not open held-out data, and does not support a paper-ready claim.
"""
    (OUT / "FINAL_REPORT.md").write_text(report, encoding="utf-8")
    (OUT / "FINAL_SYNTHESIS.md").write_text(
        "# Final synthesis\n\n"
        + (
            "The preregistered cross-video mechanism signal survived its key-component "
            "ablation within the two-video development boundary."
            if core_signal == "PRESENT"
            else "The two-video loop did not establish an ablation-supported core mechanism."
        )
        + " Candidate exposure has now completed its original design and only allowed "
        "revision on two videos.\n\nThe next discriminating step requires a third "
        "independent source video; further adaptive search on the same two videos is "
        "not authorized. Held-out remains unopened.\n",
        encoding="utf-8",
    )
    commands = """# Exact commands

```bash
python scripts/audit_psvr_two_video_inputs.py
python scripts/freeze_psvr_two_video_queries.py
python scripts/preregister_psvr_two_video_proxy.py
python scripts/build_psvr_two_video_references.py prepare
python scripts/build_psvr_two_video_references.py infer
python scripts/build_psvr_two_video_references.py finalize
python scripts/build_psvr_two_video_references.py verify
python scripts/run_psvr_two_video_proxy.py freeze-implementation
python scripts/freeze_psvr_two_video_deadlines.py profile
python scripts/freeze_psvr_two_video_deadlines.py freeze
python scripts/run_psvr_two_video_proxy.py smoke --family Y8 --video V0 --unit 0
python scripts/run_psvr_two_video_proxy.py smoke --family YP640 --video V0 --unit 0
python scripts/run_psvr_two_video_proxy.py smoke --family YP320 --video V0 --unit 0
python scripts/run_psvr_two_video_proxy.py profile --family Y8
python scripts/run_psvr_two_video_proxy.py profile --family YP640
python scripts/run_psvr_two_video_proxy.py profile --family YP320
python scripts/run_psvr_two_video_proxy.py extract --family Y8 --video V0
python scripts/run_psvr_two_video_proxy.py extract --family Y8 --video V1
python scripts/run_psvr_two_video_proxy.py extract --family YP640 --video V0
python scripts/run_psvr_two_video_proxy.py extract --family YP640 --video V1
python scripts/run_psvr_two_video_proxy.py extract --family YP320 --video V0
python scripts/run_psvr_two_video_proxy.py extract --family YP320 --video V1
python scripts/run_psvr_two_video_proxy.py evaluate
python scripts/run_psvr_two_video_physical.py freeze-pilot-candidates
python scripts/run_psvr_two_video_physical.py proxy-pilot-smoke
python scripts/run_psvr_two_video_physical.py proxy-pilot-smoke-gate
python scripts/run_psvr_two_video_physical.py proxy-pilot
python scripts/evaluate_psvr_two_video_physical.py proxy-pilot
python scripts/evaluate_psvr_two_video_physical.py select-proxy
python scripts/run_psvr_two_video_physical.py preregister-expose
python scripts/run_psvr_two_video_physical.py expose-smoke
python scripts/run_psvr_two_video_physical.py expose-smoke-gate
python scripts/run_psvr_two_video_physical.py expose-formal
python scripts/evaluate_psvr_two_video_physical.py expose
"""
    initial_expose = json.loads((EXPOSE / "DECISION.json").read_text())
    if initial_expose.get("H_EXPOSE2_DECISION") == "REVISE":
        revision = json.loads((EXPOSE / "REVISION_DECISION.json").read_text())
        commands += (
            "python scripts/run_psvr_two_video_physical.py expose-revision "
            f"--revision-method {revision['revision_method']}\n"
            "python scripts/evaluate_psvr_two_video_physical.py expose-revision "
            f"--revision-method {revision['revision_method']}\n"
        )
    if expose_status == "ACCEPT_TWO_VIDEO_SIGNAL":
        commands += (
            "python scripts/run_psvr_two_video_physical.py preregister-ablation\n"
            "python scripts/run_psvr_two_video_physical.py ablation\n"
            "python scripts/evaluate_psvr_two_video_physical.py ablation\n"
        )
    commands += (
        "python scripts/finalize_psvr_two_video_loop.py\n"
        "```\n"
    )
    (OUT / "EXACT_COMMANDS.md").write_text(commands, encoding="utf-8")
    changed = """# Changed files

## Research implementation

- `scripts/audit_psvr_two_video_inputs.py`
- `scripts/freeze_psvr_two_video_queries.py`
- `scripts/build_psvr_two_video_references.py`
- `scripts/preregister_psvr_two_video_proxy.py`
- `scripts/run_psvr_two_video_proxy.py`
- `scripts/freeze_psvr_two_video_deadlines.py`
- `scripts/run_psvr_two_video_physical.py`
- `scripts/evaluate_psvr_two_video_physical.py`
- `scripts/finalize_psvr_two_video_loop.py`
- `src/garc_eval/psvr_runtime/two_video_physical_oracle.py`
- `src/garc_eval/psvr_runtime/__init__.py`
- `src/garc_eval/psvr_exposure/__init__.py`
- `src/garc_eval/psvr_exposure/policy_service.py`
- `tests/psvr_runtime/test_two_video_physical_oracle.py`
- `tests/psvr_runtime/test_exposure_policy.py`

## Generated evidence

All new experimental evidence is under `outputs/psvr_two_video_loop/`.
Existing Stage 1–5 and earlier proxy assets were not overwritten.
"""
    (OUT / "CHANGED_FILES.md").write_text(changed, encoding="utf-8")
    completion = {
        "required_final_fields_present": all(
            key in audited
            for key in (
                "TWO_VIDEO_DEV_BENCHMARK",
                "SELECTED_PROXY_FAMILY",
                "SELECTED_PROXY_CONFIG",
                "PROXY_REGIME_REVALIDATION",
                "H_EXPOSE2_REVISION",
                "H_EXPOSE2_DECISION",
                "H_EXPOSE2_ABLATION",
                "TWO_VIDEO_CORE_SIGNAL",
                "MACRO_ANYTIME_AUC",
                "MACRO_F1",
                "TOTAL_UNIQUE_CONFIRMED_EVENTS",
                "MACRO_TTFC",
                "TOTAL_GPU_SECONDS",
            )
        ),
        "two_videos": benchmark["DEV_SOURCE_VIDEOS"] == 2,
        "two_queries": benchmark["DEV_QUERIES"] == 2,
        "four_tasks": benchmark["DEV_VIDEO_QUERIES"] == 4,
        "benchmark_pass": benchmark["TWO_VIDEO_DEV_BENCHMARK"] == "PASS",
        "proxy_unique": proxy["SELECTED_PROXY_CONFIG"]
        == final_proxy["selected_proxy_config"],
        "heldout_opened": False,
        "heldout_remains_closed": True,
        "usability_claim_withheld": True,
        "paper_ready_claim_withheld": True,
        "revision_completion_gate_pass": json.loads(
            (expose_source / "REVISION_COMPLETION_GATE.json").read_text()
        ).get("REVISION_COMPLETION_GATE") == "PASS",
        "revision_matrix_72_valid": (
            json.loads((expose_source / "RESUME_AUDIT.json").read_text()).get("valid_cells")
            == 72
        ),
        "revision_decision_reject": expose_status == "REJECT",
        "two_video_core_signal_absent": core_signal == "ABSENT",
        "ablation_not_run_hypothesis_rejected": (
            ablation_status == "NOT_RUN_HYPOTHESIS_REJECTED"
            and not (ABLATION / "raw").exists()
        ),
        "reference_reporting_levels_present": all(
            (expose_source / "tables" / name).is_file()
            for name in (
                "RUN_METRICS.csv",
                "TASK_DEADLINE_AGGREGATE.csv",
                "TASK_AGGREGATE.csv",
                "DEADLINE_AGGREGATE.csv",
                "METHOD_AGGREGATE.csv",
                "MACRO_METRICS.csv",
            )
        ),
        "persistent_state_files_present": all(
            path.is_file()
            for path in (
                ROOT / "docs/PSVR_HYPOTHESIS_REGISTRY.md",
                ROOT / "docs/PSVR_DECISION_LEDGER.md",
                ROOT / "docs/PSVR_FAILURE_CATALOG.md",
                ROOT / "outputs/psvr_autonomous_research/RESEARCH_STATE.json",
                ROOT / "outputs/psvr_autonomous_research/CURRENT_BEST_METHOD.md",
                ROOT / "outputs/psvr_autonomous_research/CLAIMS_LEDGER.md",
                OUT / "FINAL_SYNTHESIS.md",
                OUT / "FINAL_REPORT.md",
                OUT / "ADVERSARIAL_REVIEW.md",
                OUT / "AUDITED_DECISION.json",
            )
        ),
        "adversarial_review_sha256": sha256_file(
            OUT / "ADVERSARIAL_REVIEW.md"
        ),
        "audited_decision_sha256": sha256_file(OUT / "AUDITED_DECISION.json"),
    }
    completion["complete"] = all(
        value is True
        for key, value in completion.items()
        if key not in {
            "adversarial_review_sha256",
            "audited_decision_sha256",
            "heldout_opened",
        }
    )
    durable_json(OUT / "COMPLETION_AUDIT.json", completion)
    research_state = json.loads(
        (OUT / "state/RESEARCH_STATE.json").read_text()
    )
    research_state.update({
        "status": "PAUSED_INPUT_REQUIRED",
        "terminal_two_video_decision": audited,
        "next_highest_value_action": (
            "Obtain a third independent source video, retain Q1/Q2, and run six-task "
            "generalization validation without opening held-out."
        ),
    })
    durable_json(OUT / "state/RESEARCH_STATE.json", research_state)
    print(json.dumps(audited, indent=2))


if __name__ == "__main__":
    main()
