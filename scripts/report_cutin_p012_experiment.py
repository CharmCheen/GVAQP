#!/usr/bin/env python3
"""Render validity-constrained P0/P1/P2 reports from frozen artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from cutin_p012_common import OUT, sha256_file, utc_now, write_json


def load(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def main() -> None:
    reports = OUT / "reports"
    c = load(OUT / "metrics/candidate_metrics.json")
    e = load(OUT / "metrics/event_metrics.json")
    b = load(OUT / "metrics/paired_bootstrap.json")
    r = load(OUT / "runtime_profile.json")
    support = load(OUT / "oracle_support_audit.json")
    labels = load(OUT / "label_audit.json")
    events = load(OUT / "reference_event_audit.json")
    split = load(OUT / "split_leakage_audit.json")

    p0, p1, p2 = (c["methods"][f"{name}-LIGHTGBM"] for name in ["P0", "P1", "P2"])
    raw = c["methods"]["B-RAW-YOLO"]
    p10 = b["comparisons"]["P1-LIGHTGBM_minus_P0-LIGHTGBM"]
    p21 = b["comparisons"]["P2-LIGHTGBM_minus_P1-LIGHTGBM"]
    p1_cost = r["feature_cost_per_candidate"]["P1"] - r["feature_cost_per_candidate"]["P0"]
    p2_cost = r["feature_cost_per_candidate"]["P2"] - r["feature_cost_per_candidate"]["P1"]

    write(reports / "DATA_AND_LABEL_AUDIT.md", f"""
# Data and label audit

The frozen Stage-A Q1 universe has {support['total_candidate_count']} candidates,
{support['valid_labeled_candidate_count']} valid durable labels
({support['positive_count']} positive, {support['negative_count']} negative), and
{support['invalid_count']} retained invalid/abstaining rows. No invalid row was
converted to negative, no new Oracle call was made, and label conflicts are
{labels['conflicts']}. All five frozen outer folds contain both classes; no
session component crosses folds. Each outer training set also has its three
development-fold assignments frozen in `split_manifest.csv`.

The apparent Stage-A K3 groups are not reference truth: their implementation
constructs them directly from the same projected positive candidate labels.
They are therefore disqualified, leaving no independent EventRelation or
frozen candidate-event match rule. Event evaluation is blocked.

The requested target-vehicle cut-in label is also absent. Existing Q1 is the
broader `OTHER_VEHICLE_ENTERS_EGO_PATH` projection `cyclist|vehicle`; results
below are exploratory for that Q1 only and do not establish target-vehicle
cut-in.

DATA_AUDIT = PASS_FOR_EXISTING_STAGE_A_Q1_ONLY  
TARGET_VEHICLE_CUTIN_DATA_VALIDITY = NOT_ESTABLISHED  
LABEL_AUDIT = PASS_WITH_QUERY_SCOPE_LIMITATION  
EVENT_AUDIT = {events['status']}  
POLICY_SUPPORT_COMPLETE = false
""")

    random = c["baselines"]["B-RANDOM"]
    shuffled = c["baselines"]["B-SHUFFLED"]
    write(reports / "P0_RESULT.md", f"""
# P0 result — detection aggregates

Using the required existing frozen Stage-A `q1_score`, B-RAW-YOLO grouped OOF
AUPRC is {raw['auprc']:.6f}. P0-LightGBM reaches {p0['auprc']:.6f}
(delta {p0['auprc'] - raw['auprc']:+.6f}); P0-Logistic reaches
{c['methods']['P0-LOGISTIC']['auprc']:.6f}. Random (100 seeds) and
training-fold shuffled-label (20 seeds) mean AUPRC are
{random['auprc_mean']:.6f} and {shuffled['auprc_mean']:.6f}. Their full
candidate-metric distributions, including AUROC, Brier, ECE and available
P@K/R@K, are stored in `candidate_metrics.json`.

This is limited evidence that detection aggregates contain exploratory signal
for the existing broad Q1. It is not a target-vehicle cut-in or event-level
result.

P0_SIGNAL = LIMITED_EXPLORATORY_BROAD_Q1_SIGNAL
""")

    write(reports / "P1_RESULT.md", f"""
# P1 result — ByteTrack trajectories

P1-LightGBM AUPRC is {p1['auprc']:.6f}; its paired change from P0 is
{p10['aggregate_delta']:+.6f}, with 10,000-group bootstrap 95% interval
[{p10['ci95'][0]:+.6f}, {p10['ci95'][1]:+.6f}]. The signed-margin group win
rate is {p10['group_win_rate_signed_margin']:.1%}, leave-best-group-out delta
is {p10['leave_best_group_out_delta']:+.6f}, and the predeclared
single-group-stability flag is {str(p10['not_single_group_driven']).lower()}.
ByteTrack adds {p1_cost:.6f} seconds per candidate on average.

The selection gate cannot pass because stability fails and independent event
recall AUC is `{e['status']}`.

P1_DECISION = REJECT_OR_REVISE
""")

    write(reports / "P2_RESULT.md", f"""
# P2 result — full partial-affine camera normalization

After the controlled implementation repair, current track centres are mapped
back through the complete estimated partial-affine transform (translation,
rotation and scale) before compensated trajectory summaries are computed.
P2-LightGBM AUPRC is {p2['auprc']:.6f}; its paired change from P1 is
{p21['aggregate_delta']:+.6f}, with 95% interval
[{p21['ci95'][0]:+.6f}, {p21['ci95'][1]:+.6f}]. High-motion negative FPR is
{p1['high_global_motion_negative_fpr']['fpr']} for P1 versus
{p2['high_global_motion_negative_fpr']['fpr']} for P2. Camera normalization
adds {p2_cost:.6f} seconds per candidate.

P2 cannot be selected because its contracted event criterion is blocked;
candidate and high-motion criteria also determine whether the terminal action
is STOP.

P2_DECISION = STOP
""")

    write(reports / "ARC_COMPARISON.md", f"""
# ARC comparison

The existing strong ARC-refinement result is an offline replay on
`realcartest_2000_3200` (120 units, 20 VLM-defined events), with reported
event-F1 0.532452/0.676479/0.879258 at budgets 20/50/100. It does not share
the Stage-A candidate universe, Oracle ledger, event reference, SCAN order, or
deadline trace. An ARC component-replacement comparison is therefore blocked.

The local replay first restricts ranking to the 86 valid labeled candidates;
it is therefore a support-restricted counterfactual, not actual-policy top-K.
It charges video decode, feature
extraction, classifier inference, and durable CONFIRM generation. Separate
materialization/commit cost is unavailable, so its wall time is explicitly a
lower bound. It makes no unique-event or event-recall claim.

ARC_FULL = EXISTING_STRONG_OFFLINE_RESULT_OTHER_UNIVERSE_NOT_COMPARABLE  
ARC_COMPONENT_REPLACEMENT = BLOCKED_ASSET_MISMATCH  
SYSTEM_LEVEL_CLAIM = NOT_ESTABLISHED
""")

    write(reports / "MECHANISM_ANALYSIS.md", f"""
# Mechanism analysis

P0's candidate gain over the frozen score is {p0['auprc'] - raw['auprc']:+.6f}
AUPRC. P1 changes the primary score by {p10['aggregate_delta']:+.6f}, but its
group stability condition fails. P2 changes P1 by
{p21['aggregate_delta']:+.6f}; its corrected affine compensation is now
implementation-faithful, but the unavailable independent events prevent the
candidate-to-event mechanism from being tested.

The main failure mode is reference scope, not merely model capacity: the
available labels cover a broader cyclist-or-vehicle path-entry query, and the
only event groups reuse those same labels. Candidate ranking can be analyzed;
event recovery, duplicate suppression benefit, deadline utility, and ARC
causality remain not established.
""")

    final = f"""
# Final decision

The complete corrected experiment supports only a limited candidate-ranking
claim for existing broad Stage-A Q1. The required target-vehicle cut-in claim
is not established. No independent event truth exists, policy label coverage
is incomplete, and the available strong ARC result is from a different
universe. P1 fails its cross-group/event selection gate; P2 also fails the
selection gate after full partial-affine repair. No learned proxy is promoted.

DATA_VALIDITY = PASS_FOR_EXISTING_STAGE_A_Q1_ONLY  
TARGET_VEHICLE_CUTIN_VALIDITY = NOT_ESTABLISHED  
LABEL_VALIDITY = PASS_WITH_QUERY_SCOPE_LIMITATION  
EVENT_MAPPING_VALIDITY = BLOCKED_MISSING_FROZEN_MATCH_RULE  
ORACLE_SUPPORT_STATUS = LABELED_SUPPORT_REPLAY  
SPLIT_VALIDITY = PASS  
ARC_BASELINE_STATUS = BLOCKED_ASSET_MISMATCH

P0_SIGNAL = LIMITED_EXPLORATORY_BROAD_Q1_SIGNAL  
P1_DECISION = REJECT_OR_REVISE  
P2_DECISION = STOP  
SELECTED_PROXY = NONE

CANDIDATE_LEVEL_CLAIM = LIMITED_EXISTING_STAGE_A_Q1_SIGNAL_ESTABLISHED  
EVENT_LEVEL_CLAIM = NOT_ESTABLISHED  
SYSTEM_LEVEL_CLAIM = NOT_ESTABLISHED  
CROSS_SOURCE_CLAIM = NOT_ESTABLISHED

RUNTIME_TRADEOFF = P1_ADDS_{p1_cost:.6f}_SEC_PER_CANDIDATE_P2_ADDS_{p2_cost:.6f}  
MAIN_FAILURE_MODE = QUERY_SCOPE_AND_MISSING_INDEPENDENT_EVENT_REFERENCE  
MECHANISM_FINDING = TRAJECTORY_SIGNAL_NOT_CROSS_GROUP_STABLE_EVENT_TRANSLATION_UNTESTABLE  
NEXT_ALLOWED_STAGE = PROXY FAILURE ANALYSIS  
CONTROLLER_LEARNING = STILL_PROHIBITED

PRIMARY_NUMERIC_RESULT = P1_LIGHTGBM_MINUS_P0_LIGHTGBM_AUPRC_{p10['aggregate_delta']:+.6f}_CI95_[{p10['ci95'][0]:+.6f},{p10['ci95'][1]:+.6f}]  
ARC_COMPARISON_RESULT = BLOCKED_ASSET_MISMATCH_CANDIDATE_ONLY_COST_REPLAY
"""
    write(reports / "FINAL_DECISION.md", final)
    write_json(OUT / "report_manifest.json", {
        "created_at_utc": utc_now(),
        "reports": {path.name: sha256_file(path) for path in sorted(reports.glob("*.md"))},
        "decision": "NO_PROXY_PROMOTED",
    })
    print(final)


if __name__ == "__main__":
    main()
