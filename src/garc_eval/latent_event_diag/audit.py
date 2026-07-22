from __future__ import annotations

import argparse
import hashlib
from collections import defaultdict
from pathlib import Path

import pandas as pd

from .materializers.k3_adapter import K3AdapterMaterializer


ROOT = Path(__file__).resolve().parents[3]
UNIT_CSV = ROOT / "outputs/real_video_protocol_pilot_v1/frame_scores_adapter_ready.csv"
COMPARISON_DIR = ROOT / "outputs/ours_vs_baselines_realcartest_v1"
STAGE06_DIR = ROOT / "outputs/stage_0_6_materializer_ablation"
STAGE07_DIR = ROOT / "outputs/stage_0_7_minimal_operator_compression"
PRECROSS_DIR = ROOT / "outputs/pre_cross_video_audit"
BUDGETS = (5, 10, 20, 50, 80, 100)


def _frame_hash(frame: pd.DataFrame) -> str:
    columns = [column for column in ["start_time", "end_time", "source_frame_ids"] if column in frame.columns]
    payload = frame[columns].sort_values(columns, kind="stable").to_csv(index=False) if columns else ""
    return hashlib.sha256(payload.encode()).hexdigest()


def _segment_path(stage_dir: Path, module, run, variant: str) -> Path:
    return stage_dir / "segments" / f"{module.safe_name(run.selector)}_B{run.budget}_s{run.seed}_{variant}.csv"


def _changed(left: Path, right: Path) -> int:
    if not left.exists() or not right.exists():
        return 0
    return int(_frame_hash(pd.read_csv(left)) != _frame_hash(pd.read_csv(right)))


def build_k3_path_audit(output_dir: Path) -> pd.DataFrame:
    stage07 = K3AdapterMaterializer()._load()
    stage06 = stage07.S6
    units = pd.read_csv(UNIT_CSV)
    units_by_id = stage07.unit_records(units)
    runs, _ = stage06.discover_runs(COMPARISON_DIR, set(BUDGETS))
    counts: dict[tuple[int, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    output_changes: dict[tuple[int, str], int] = defaultdict(int)
    for run in runs:
        oracle = pd.read_csv(run.oracle_log_path).sort_values("call_idx")
        positives = sorted(int(x) for x in oracle.loc[oracle.oracle_label.astype(int) == 1, "unit_id"])
        negatives = set(int(x) for x in oracle.loc[oracle.oracle_label.astype(int) == 0, "unit_id"])
        key = (run.budget, "positive_anchor_merge")
        counts[key]["eligible"] += max(0, len(positives) - 1)
        groups = [[positives[0]]] if positives else []
        for anchor in positives[1:]:
            prev = groups[-1][-1]
            proposed = stage07.contiguous_ids(groups[-1][0], anchor, units_by_id)
            gap = max(0, anchor - prev - 1)
            counts[(run.budget, "gap_limit")]["eligible"] += 1
            if gap > stage07.PARAMS.g_max:
                counts[(run.budget, "gap_limit")]["trigger"] += 1
                counts[(run.budget, "gap_limit")]["state"] += 1
                groups.append([anchor])
                continue
            counts[(run.budget, "core_duration_maximum")]["eligible"] += 1
            if stage07.ids_duration(proposed, units_by_id) > stage07.PARAMS.d_core_max:
                counts[(run.budget, "core_duration_maximum")]["trigger"] += 1
                counts[(run.budget, "core_duration_maximum")]["state"] += 1
                groups.append([anchor])
                continue
            counts[(run.budget, "queried_negative_barrier")]["eligible"] += 1
            if stage07.gap_has_negative(prev, anchor, negatives):
                counts[(run.budget, "queried_negative_barrier")]["trigger"] += 1
                counts[(run.budget, "queried_negative_barrier")]["state"] += 1
                groups.append([anchor])
                continue
            groups[-1].append(anchor)
            counts[key]["trigger"] += 1
            counts[key]["state"] += 1

        prefix_positives: list[int] = []
        prefix_negatives: set[int] = set()
        for row in oracle.to_dict("records"):
            before = len(stage07.build_groups(prefix_positives, prefix_negatives, units_by_id, stage07.KRULES["K3_gap_duration_negative_barrier"]))
            if int(row["oracle_label"]) == 1:
                counts[(run.budget, "intermediate_positive_bridge_merge")]["eligible"] += int(bool(prefix_positives))
                prefix_positives.append(int(row["unit_id"]))
                after = len(stage07.build_groups(prefix_positives, prefix_negatives, units_by_id, stage07.KRULES["K3_gap_duration_negative_barrier"]))
                if before > after:
                    counts[(run.budget, "intermediate_positive_bridge_merge")]["trigger"] += 1
                    counts[(run.budget, "intermediate_positive_bridge_merge")]["state"] += before - after
            else:
                prefix_negatives.add(int(row["unit_id"]))

        pairs = {
            "gap_limit": ("K0_naive_merge", "K1_gap_limited"),
            "core_duration_maximum": ("K1_gap_limited", "K2_gap_duration"),
            "queried_negative_barrier": ("K2_gap_duration", "K3_gap_duration_negative_barrier"),
            "boundary_expansion": ("K3_gap_duration_negative_barrier", "K4_gap_duration_negative_barrier_selected_expand"),
        }
        for rule, (left_variant, right_variant) in pairs.items():
            output_changes[(run.budget, rule)] += _changed(
                _segment_path(STAGE07_DIR, stage07, run, left_variant),
                _segment_path(STAGE07_DIR, stage07, run, right_variant),
            )
        output_changes[(run.budget, "positive_anchor_merge")] += int(bool(positives))
        for rule, (left_variant, right_variant) in {
            "proxy_valley_soft_barrier": ("C3_negative_hard_barrier", "C4_proxy_valley_soft_barrier"),
            "duplicate_suppression": ("C4_proxy_valley_soft_barrier", "C5_duplicate_suppression"),
        }.items():
            output_changes[(run.budget, rule)] += _changed(
                _segment_path(STAGE06_DIR, stage06, run, left_variant),
                _segment_path(STAGE06_DIR, stage06, run, right_variant),
            )

    trigger_artifact = pd.read_csv(PRECROSS_DIR / "trigger_counts_by_run.csv")
    for budget in BUDGETS:
        subset = trigger_artifact[trigger_artifact.budget == budget]
        k4 = subset[subset.materializer_variant == "K4_gap_duration_negative_barrier_selected_expand"]
        c6 = subset[subset.materializer_variant == "C6_full_EVENT_MATERIALIZE"]
        counts[(budget, "boundary_expansion")]["eligible"] = int(k4.selected_expansion_attempt_count.sum())
        counts[(budget, "boundary_expansion")]["trigger"] = int(k4.selected_expansion_applied_count.sum())
        counts[(budget, "boundary_expansion")]["state"] = int(k4.selected_expansion_applied_count.sum())
        counts[(budget, "segment_duration_maximum")]["eligible"] = int(k4.selected_expansion_attempt_count.sum() - k4.selected_expansion_rejected_by_barrier.sum())
        counts[(budget, "segment_duration_maximum")]["trigger"] = int(k4.selected_expansion_rejected_by_duration.sum())
        counts[(budget, "segment_duration_maximum")]["state"] = int(k4.selected_expansion_rejected_by_duration.sum())
        counts[(budget, "proxy_valley_soft_barrier")]["eligible"] = int(c6.merge_pair_candidates.sum())
        counts[(budget, "proxy_valley_soft_barrier")]["trigger"] = int(c6.blocked_by_proxy_valley.sum())
        # C3 and C4 outputs are the direct counterfactual. Raw proxy failures
        # overlap earlier blockers, so they are triggers but not state changes.
        counts[(budget, "proxy_valley_soft_barrier")]["state"] = output_changes[(budget, "proxy_valley_soft_barrier")]
        counts[(budget, "duplicate_suppression")]["eligible"] = int(c6.duplicate_candidate_pairs.sum())
        counts[(budget, "duplicate_suppression")]["trigger"] = int(c6.duplicate_suppressed_count.sum())
        counts[(budget, "duplicate_suppression")]["state"] = int(c6.duplicate_suppressed_count.sum())

    rows = []
    rule_meta = {
        "positive_anchor_merge": ("K3", "enabled", "successful adjacent-anchor joins"),
        "gap_limit": ("K3", "G_max=1 unit", "short-circuit path count"),
        "core_duration_maximum": ("K3", "D_core_max=40.0s", "eligible only after gap passes"),
        "queried_negative_barrier": ("K3", "all oracle_label==0", "ordinary binary negatives; no typed semantics"),
        "intermediate_positive_bridge_merge": ("K3", "enabled", "destructive merge means event count falls after a new positive"),
        "boundary_expansion": ("K4", "E=1 selected neighbor", "K3 has no expansion path"),
        "segment_duration_maximum": ("K4", "D_seg_max=60.0s", "unreachable in K3; checked only in K4 expansion"),
        "proxy_valley_soft_barrier": ("C6", "quantile=0.3", "not present in K3"),
        "duplicate_suppression": ("C6", "nms_iou=0.7", "not present in K3"),
        "conflict_resolution": ("K3", "absent", "no implementation branch"),
    }
    for budget in BUDGETS:
        output_changes[(budget, "intermediate_positive_bridge_merge")] = counts[
            (budget, "intermediate_positive_bridge_merge")
        ]["trigger"]
        for rule, (variant, config_value, note) in rule_meta.items():
            values = counts[(budget, rule)]
            rows.append(
                {
                    "dataset": "realcartest_pseudo_oracle_pilot",
                    "budget": budget,
                    "variant": variant,
                    "rule_name": rule,
                    "eligible_count": values["eligible"],
                    "trigger_count": values["trigger"],
                    "state_change_count": values["state"],
                    "final_output_change_count": output_changes[(budget, rule)],
                    "config_value": config_value,
                    "source_artifact": "outputs/ours_vs_baselines_realcartest_v1/*/oracle_log.csv; outputs/stage_0_6_materializer_ablation/segments; outputs/stage_0_7_minimal_operator_compression/segments",
                    "notes": note
                    + (
                        "; final_output_change_count is changed action-prefix outputs"
                        if rule == "intermediate_positive_bridge_merge"
                        else "; final_output_change_count is replay runs changed by adjacent variant (positive merge: nonempty outputs)"
                    ),
                }
            )
    frame = pd.DataFrame(rows)
    frame.to_csv(output_dir / "k3_path_audit.csv", index=False)
    return frame


def build_baseline_audit(output_dir: Path) -> pd.DataFrame:
    supg = pd.read_csv(PRECROSS_DIR / "supg_variant_path_audit.csv")
    rows = [
        {
            "component": "SUPG",
            "check": "all-selected vs confirmed-only queried IDs and anchors",
            "status": "VERIFIED",
            "evidence": f"{len(supg)} paired runs; queried/positive/negative Jaccard all exactly 1.0",
            "finding": "Native selected sets differ, but queried IDs and positive anchors are identical.",
            "risk": "K3 consumes anchors and negatives only, so selector differences collapse before output.",
        },
        {
            "component": "SUPG",
            "check": "EventRelation output equivalence",
            "status": "VERIFIED",
            "evidence": f"segment_outputs_identical={int(supg.segment_outputs_identical.sum())}/{len(supg)}; metrics_identical={int(supg.metrics_identical.sum())}/{len(supg)}",
            "finding": "Equivalence begins at the K3 input projection, not at native selected IDs.",
            "risk": "Shared K3 erases native all-selected coverage behavior.",
        },
        {
            "component": "ABae",
            "check": "online strata and pilot reuse",
            "status": "VERIFIED",
            "evidence": "refe_repos/adapter/abae_baseline/run.py:29-35,63-119",
            "finding": "Strata use proxy/time only; pilot labels allocate remaining budget; pilot samples are retained in final sampled/confirmed set.",
            "risk": "This is ABae-inspired aggregation allocation adapted to discovery, not a native event-discovery guarantee.",
        },
        {
            "component": "ABae",
            "check": "oracle-informed failure strata",
            "status": "VERIFIED",
            "evidence": "make_strata reads normalized proxy_score only",
            "finding": "No oracle-informed failure strata are constructed.",
            "risk": "None found in this adapter path.",
        },
        {
            "component": "MAP",
            "check": "component construction, allocation, tie break, seed",
            "status": "VERIFIED",
            "evidence": "scripts/stage1a_map_anchor_only.py:91-143,194-317",
            "finding": "Threshold is proxy q0.70; audit windows are 60s; split is 80/20 at B<=20 and 70/30 above; ties resolve by deterministic iteration/unit ID; seed is metadata-only.",
            "risk": "Five seed labels would not represent stochastic repeats for MAP.",
        },
        {
            "component": "MAP",
            "check": "B=100 overcoverage lineage",
            "status": "VERIFIED",
            "evidence": "outputs/stage_1b_map_anchor_barrier/action_traces/map_anchor_barrier_B100_s0_trace.csv; segments/map_anchor_only_B100_s0_K3.csv",
            "finding": "Every segment carries source_frame_ids and every action carries call_idx/action_type/unit_id/outcome.",
            "risk": "K3 treats all 71 MAP binary negatives as barriers; Stage 1B labels PLACE_BARRIER but K3 cannot distinguish its semantics.",
        },
        {
            "component": "ARC",
            "check": "native output vs K3-adapted output",
            "status": "VERIFIED",
            "evidence": "refe_repos/adapter/arc_baseline/run.py:134-188; scripts/stage0_7_minimal_operator_compression.py:198-229",
            "finding": "Native ARC emits cand_clips; K3 adapter discards those boundaries and rematerializes only queried positives/negatives.",
            "risk": "Adaptation changes ARC's native coverage/boundary advantage.",
        },
        {
            "component": "ARC",
            "check": "clip label treated as event identity",
            "status": "LIKELY",
            "evidence": "K3 uses binary oracle_label as anchors; no event identity field exists in oracle_log",
            "finding": "No explicit identity leakage was found, but the adapter cannot represent two events in one positive unit.",
            "risk": "Unit-level binary evidence is insufficient for latent identity/multiplicity.",
        },
        {
            "component": "uniform/random/top-proxy/component-first",
            "check": "shared real-data artifacts",
            "status": "BLOCKED_BY_MISSING_ARTIFACT",
            "evidence": "No matching per-budget realcartest oracle_log/segments set in the audited comparison directory.",
            "finding": "MAP component-first is available, but no common-artifact uniform/random/top-proxy comparison was located.",
            "risk": "Cannot claim shared event_merge/event_eval or absence of hypothesis-construction leakage.",
        },
    ]
    frame = pd.DataFrame(rows)
    frame.to_csv(output_dir / "baseline_equivalence_audit.csv", index=False)
    return frame


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    build_k3_path_audit(args.output_dir)
    build_baseline_audit(args.output_dir)


if __name__ == "__main__":
    main()
