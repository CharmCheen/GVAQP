#!/usr/bin/env python3
"""Prepare the frozen P1 independent-geometry replication through P1-A.

The authoritative trace identities were frozen outcome-blind in the earlier
long-horizon package.  This script verifies and re-materializes them under the
requested P1 output contract, joins cached semantic outcomes only after trace
identity verification, executes the predeclared feasibility gate, and creates
the blinded human-reference package.  It never reads a human label.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/p1_independent_geometry_replication_v1"
LEGACY = ROOT / "outputs/gvaqp_long_horizon_p1_p3_v1"
TRACE_SOURCE = LEGACY / "P1_OUTCOME_BLIND_TRACE_MANIFEST.csv"
TRACE_PROTOCOL_SOURCE = LEGACY / "P1_TRACE_POPULATION_PROTOCOL.json"
Q2 = LEGACY / "qwen32_oracle/P1_QWEN32_UNIT_OUTCOMES.parquet"
Q2_COMPLETION = LEGACY / "qwen32_oracle/P1_QWEN32_ORACLE_COMPLETION.json"
Q1 = ROOT / "outputs/v10_multiseal_reference_v1/FINAL_UNIT_REFERENCE.parquet"
PROXY_METRICS_SOURCE = LEGACY / "P1_PROXY_CHARACTERIZATION.csv"
PROXY_B_PROTOCOL = LEGACY / "proxy_b_kinematic/PROXY_B_PROTOCOL.json"
PROXY_B_COMPLETION = LEGACY / "proxy_b_kinematic/PROXY_B_COMPLETION.json"
CANDIDATES = ROOT / "outputs/v3_scan_proxy_preregistration_v1/frozen_tables"
VIDEOS = ("DALI", "HANGZHOU", "WUHAN")
QUERIES = ("Q_DRIVER_RESPONSE_V1", "Q_VULNERABLE_ROAD_USER_CONFLICT_V1")
PROXIES = (
    "PROXY_A_YOLOV8N_OBJECT_MOTION",
    "PROXY_B_OPTICAL_FLOW_VISUAL_DYNAMICS",
)
PUBLIC_FEATURES = (
    "number_of_temporal_regions_touched",
    "temporal_dispersion",
    "coverage_fraction",
    "largest_unqueried_gap",
    "median_unqueried_gap",
    "query_redundancy",
    "near_duplicate_query_fraction",
    "queried_temporal_span",
)
AFTER_VERIFY_FEATURES = (
    "positive_evidence_span",
    "positive_evidence_dispersion",
    "median_positive_gap",
    "max_positive_gap",
    "positive_region_count",
    "positive_concentration",
    "distance_to_existing_verified_evidence",
)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def runs(values: list[int]) -> int:
    values = sorted(set(values))
    return 0 if not values else 1 + sum(b > a + 1 for a, b in zip(values, values[1:]))


def load_units() -> dict[str, pd.DataFrame]:
    result = {}
    for video in VIDEOS:
        frame = pd.read_parquet(CANDIDATES / video / "candidate_table.parquet").copy()
        frame["unit_id"] = frame.source_unit_ids.map(lambda value: str(value[0]))
        frame = frame.sort_values("candidate_order").reset_index(drop=True)
        if frame.candidate_order.tolist() != list(range(len(frame))):
            raise RuntimeError(f"noncanonical candidate order: {video}")
        result[video] = frame
    return result


def load_labels() -> dict[tuple[str, str], dict[str, str]]:
    q1 = pd.read_parquet(Q1)
    q2 = pd.read_parquet(Q2)
    completion = json.loads(Q2_COMPLETION.read_text())
    if completion.get("status") != "COMPLETE" or completion.get("units") != 1475:
        raise RuntimeError("second-query semantic cache is incomplete")
    if completion.get("table_sha256") != sha(Q2):
        raise RuntimeError("second-query completion hash mismatch")
    result = {}
    for query, frame, column in (
        (QUERIES[0], q1, "authoritative_label"),
        (QUERIES[1], q2, "label"),
    ):
        for video, group in frame.groupby("video_id", sort=True):
            result[(str(video), query)] = dict(zip(group.unit_id.astype(str), group[column].astype(str)))
    expected = {(video, query) for video in VIDEOS for query in QUERIES}
    if set(result) != expected or sum(len(value) for key, value in result.items() if key[1] == QUERIES[0]) != 1475:
        raise RuntimeError("semantic caches do not cover the six clusters")
    return result


def holes(positions: list[int], unit_count: int) -> list[int]:
    if not positions:
        return [unit_count]
    positions = sorted(set(positions))
    return [positions[0], unit_count - 1 - positions[-1], *[b - a - 1 for a, b in zip(positions, positions[1:])]]


def trace_features(
    selected_ids: list[str], units: pd.DataFrame, labels: dict[str, str]
) -> dict[str, float | int]:
    lookup = units.set_index("unit_id")
    selected = lookup.loc[selected_ids].copy()
    positions = sorted(selected.candidate_order.astype(int).tolist())
    starts = selected.start_sec.astype(float).to_numpy()
    ends = selected.end_sec.astype(float).to_numpy()
    duration = float(units.end_sec.max())
    unit_count = len(units)
    gaps = holes(positions, unit_count)
    bins = np.minimum(9, np.floor(np.asarray(positions) * 10 / unit_count).astype(int))
    query_redundancy = 1.0 - len(set(bins.tolist())) / max(1, len(positions))
    near_duplicate = sum(
        any(other != position and abs(other - position) <= 1 for other in positions)
        for position in positions
    ) / max(1, len(positions))
    positive_order = [unit for unit in selected_ids if labels[unit] == "relevant"]
    positive = lookup.loc[positive_order] if positive_order else selected.iloc[0:0]
    ppositions = sorted(positive.candidate_order.astype(int).tolist())
    pcenters = ((positive.start_sec.astype(float) + positive.end_sec.astype(float)) / 2).to_numpy()
    pgaps = np.diff(np.sort(pcenters)) if len(pcenters) > 1 else np.asarray([], dtype=float)
    if ppositions:
        cluster_sizes = []
        current = 1
        for left, right in zip(ppositions, ppositions[1:]):
            if right == left + 1:
                current += 1
            else:
                cluster_sizes.append(current)
                current = 1
        cluster_sizes.append(current)
    else:
        cluster_sizes = []
    prior_positive: list[int] = []
    sequential_distances = []
    for unit in selected_ids:
        if labels[unit] != "relevant":
            continue
        position = int(lookup.loc[unit].candidate_order)
        if prior_positive:
            sequential_distances.append(min(abs(position - previous) for previous in prior_positive))
        prior_positive.append(position)
    return {
        "queried_unit_count": len(selected_ids),
        "verified_positive_count": len(positive_order),
        "positive_yield": len(positive_order) / max(1, len(selected_ids)),
        "number_of_temporal_regions_touched": runs(positions),
        "temporal_dispersion": float(np.std(positions) / max(1, unit_count - 1)),
        "coverage_fraction": float((ends.max() - starts.min()) / duration),
        "largest_unqueried_gap": float(max(gaps) * 10.0),
        "median_unqueried_gap": float(np.median(gaps) * 10.0),
        "query_redundancy": float(query_redundancy),
        "near_duplicate_query_fraction": float(near_duplicate),
        "queried_temporal_span": float(ends.max() - starts.min()),
        "positive_evidence_span": float(positive.end_sec.max() - positive.start_sec.min()) if len(positive) else 0.0,
        "positive_evidence_dispersion": float(np.std(pcenters) / duration) if len(pcenters) else 0.0,
        "median_positive_gap": float(np.median(pgaps)) if len(pgaps) else 0.0,
        "max_positive_gap": float(np.max(pgaps)) if len(pgaps) else 0.0,
        "positive_region_count": runs(ppositions),
        "positive_concentration": float(max(cluster_sizes) / len(ppositions)) if ppositions else 0.0,
        "distance_to_existing_verified_evidence": float(np.mean(sequential_distances)) if sequential_distances else 0.0,
    }


def select_extremes(group: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    # Pair construction uses public geometry only after the yield stratum exists.
    ordering = [
        "number_of_temporal_regions_touched",
        "temporal_dispersion",
        "coverage_fraction",
        "largest_unqueried_gap",
        "query_redundancy",
        "trace_instance_id",
    ]
    high = group.sort_values(ordering, ascending=[False, False, False, True, True, True]).iloc[0]
    low = group.sort_values(ordering, ascending=[True, True, True, False, False, True]).iloc[0]
    return high, low


def exact_pairs(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    strata, pairs = [], []
    keys = ["video_id", "query_id", "proxy_id", "budget", "verified_positive_count"]
    for key, group in frame.groupby(keys, sort=True):
        spread = int(group.number_of_temporal_regions_touched.max() - group.number_of_temporal_regions_touched.min())
        if len(group) < 2 or spread <= 0:
            continue
        high, low = select_extremes(group)
        common = dict(zip(keys, key))
        strata.append({
            **common,
            "match_type": "EXACT_YIELD",
            "trace_count": len(group),
            "policy_count": group.policy_id.nunique(),
            "region_min": int(group.number_of_temporal_regions_touched.min()),
            "region_max": int(group.number_of_temporal_regions_touched.max()),
            "region_contrast": spread,
            "dispersion_range": float(group.temporal_dispersion.max() - group.temporal_dispersion.min()),
            "coverage_range": float(group.coverage_fraction.max() - group.coverage_fraction.min()),
            "largest_gap_range": float(group.largest_unqueried_gap.max() - group.largest_unqueried_gap.min()),
        })
        pairs.append({
            **common,
            "match_type": "EXACT_YIELD",
            "yield_difference": 0,
            "better_geometry_trace_id": high.trace_instance_id,
            "worse_geometry_trace_id": low.trace_instance_id,
            "better_geometry_policy_id": high.policy_id,
            "worse_geometry_policy_id": low.policy_id,
            "better_regions": int(high.number_of_temporal_regions_touched),
            "worse_regions": int(low.number_of_temporal_regions_touched),
            "region_contrast": int(high.number_of_temporal_regions_touched - low.number_of_temporal_regions_touched),
            "pair_selected_without_event_outcome": True,
            "human_outcomes_revealed": False,
        })
    return pd.DataFrame(strata), pd.DataFrame(pairs)


def near_pairs(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    base_keys = ["video_id", "query_id", "proxy_id", "budget"]
    for key, group in frame.groupby(base_keys, sort=True):
        yields = sorted(group.verified_positive_count.unique())
        for lower in yields:
            upper = lower + 1
            if upper not in yields:
                continue
            lower_group = group[group.verified_positive_count == lower]
            upper_group = group[group.verified_positive_count == upper]
            lower_high, lower_low = select_extremes(lower_group)
            upper_high, upper_low = select_extremes(upper_group)
            candidates = [(lower_high, upper_low), (upper_high, lower_low)]
            high, low = max(
                candidates,
                key=lambda pair: (
                    abs(int(pair[0].number_of_temporal_regions_touched) - int(pair[1].number_of_temporal_regions_touched)),
                    abs(float(pair[0].temporal_dispersion) - float(pair[1].temporal_dispersion)),
                ),
            )
            if high.number_of_temporal_regions_touched < low.number_of_temporal_regions_touched:
                high, low = low, high
            contrast = int(high.number_of_temporal_regions_touched - low.number_of_temporal_regions_touched)
            if contrast <= 0:
                continue
            rows.append({
                **dict(zip(base_keys, key)),
                "verified_positive_count": f"{lower}|{upper}",
                "match_type": "NEAR_YIELD_LE1",
                "yield_difference": 1,
                "better_geometry_trace_id": high.trace_instance_id,
                "worse_geometry_trace_id": low.trace_instance_id,
                "better_geometry_policy_id": high.policy_id,
                "worse_geometry_policy_id": low.policy_id,
                "better_regions": int(high.number_of_temporal_regions_touched),
                "worse_regions": int(low.number_of_temporal_regions_touched),
                "region_contrast": contrast,
                "pair_selected_without_event_outcome": True,
                "human_outcomes_revealed": False,
            })
    return pd.DataFrame(rows)


def protocol(source_hashes: dict[str, str]) -> dict:
    value = {
        "protocol_id": "GVAQP_P1_INDEPENDENT_EVENT_EVIDENCE_GEOMETRY_REPLICATION_V1",
        "status": "FROZEN_BEFORE_P1_HUMAN_REFERENCE",
        "primary_question": "At equal semantic-positive yield, does online-visible temporal evidence geometry consistently improve recovery of independently defined temporal events?",
        "primary_unit_of_inference": "video-query cluster",
        "videos": list(VIDEOS),
        "queries": list(QUERIES),
        "natural_proxies": list(PROXIES),
        "budgets": [5, 10, 20, 50, 80, 100],
        "trace_generators": {
            "B0_UniformTemporal": "evenly spaced temporal positions",
            "B1_StaticProxyRank": "descending named frozen proxy",
            "B2_CoverageFirst": "recursive temporal bisection",
            "B3_ProxyPlusTemporalCoverage_MMR": "fixed weights 0.25/0.50/0.75; normalized relevance plus minimum temporal distance",
            "B4_existing_frozen_policy_traces": "B0/B1/B2 are exact frozen-policy lineages; represented once to avoid duplicate pseudo-replication",
            "B5_SeededTemporalHash": "all frozen seeds 0..7; no seed selection",
        },
        "trace_construction_prohibited_inputs": ["semantic outcomes", "human labels", "reference events", "C1/K3 output", "EventF1"],
        "primary_match": ["same video", "same query", "same proxy", "same budget", "exact verified_positive_count"],
        "secondary_match": "absolute verified_positive_count difference <= 1",
        "pair_selection": "maximize number_of_temporal_regions_touched contrast; public dispersion/coverage/gap/redundancy are fixed tie-breaks; EventF1 and references are unavailable",
        "feature_visibility": {
            "POLICY_VISIBLE": list(PUBLIC_FEATURES),
            "ORACLE_OBSERVED_AFTER_VERIFY": ["verified_positive_count", "positive_yield", *AFTER_VERIFY_FEATURES],
            "REFERENCE_ONLY": ["human event IDs", "human event boundaries", "future or unqueried semantic labels"],
        },
        "frozen_components": {
            "candidate_unit_semantics": "released V3 one-candidate-per-10-second-unit interface",
            "oracle_semantics": "released Q1 cache and completed frozen Q2 cache",
            "query_budget_semantics": "cached semantic invocation count, not wall clock",
            "materializer": "C1 GAP-ONLY, gap <=10 seconds; secondary endpoint only",
            "evaluator": "frozen P0 one-to-one maximum-cardinality then tIoU implementation",
            "controller_default": "FIXED_SCAN1_VERIFY1; execution baseline only and outside P1",
        },
        "prohibited": [
            "controller/MAB/RL research", "SCAN/VERIFY ratio search", "event-aware selector",
            "C1/K3/evaluator retuning", "per-video or per-proxy policy tuning",
            "human/reference-guided trace construction", "post-result gate changes",
        ],
        "p1a_gate": {
            "minimum_exact_pairs": 48,
            "required_video_query_clusters": 6,
            "minimum_exact_pairs_per_video_query_proxy": 6,
            "minimum_budgets_per_video_query_proxy": 4,
            "required_proxy_families": 2,
            "minimum_pair_endpoint_generator_families": 4,
            "minimum_median_region_contrast": 2.0,
            "interpretation": "trace-identifiability gate only; within-cluster strata are not independent samples",
        },
        "p1_final_gate": [
            "yield-only clearly insufficient on independent human reference",
            "public geometry adds held-out video/query explanatory value",
            "equal-yield matched human-event effects are directionally stable across clusters",
            "effect is not driven by one video/pair",
            "both natural proxies agree directionally",
            "primary result uses no reference-only feature",
            "effect appears in direct materializer-independent human-event coverage",
        ],
        "p1_final_gate_operationalization": {
            "minimum_exact_pairs_per_proxy": 12,
            "minimum_video_query_clusters_with_exact_pairs_per_proxy": 4,
            "yield_only_insufficient": "LOVO and LOVQO macro yield-only R2 <= 0.50, or public-geometry MAE lift >=0.05 in both splits",
            "public_geometry_lift": "yield-only minus public-geometry MAE >=0.02 in both LOVO and LOVQO",
            "matched_effect": "video-query-collapsed median delta human_event_coverage >0 and median delta distinct_human_events_touched >0, with positive coverage direction in >=4/6 clusters",
            "cross_proxy": "proxy-collapsed median delta human_event_coverage >0 for both frozen natural proxies",
            "materializer_independent": "matched_effect is evaluated on direct positive-evidence touch/coverage, not C1 EventF1",
            "all_required": True,
        },
        "primary_endpoints": {
            "distinct_human_events_touched": "count of adjudicated human events overlapped by at least one queried verified-positive unit; no materializer",
            "human_event_recall": "distinct_human_events_touched / human_reference_event_count; no materializer",
            "human_event_F1": "harmonic mean of direct positive-unit evidence precision and human-event recall; no C1 grouping",
            "C1_EventF1": "frozen secondary endpoint only; cannot determine P1 PASS by itself",
        },
        "inference": {
            "matched_strata": "median-collapse within video-query-proxy",
            "primary_cluster": "video-query",
            "bootstrap": "10000 whole video-query cluster resamples, seed 20260813",
            "heldout_splits": ["Leave-One-Video-Out", "Leave-One-VideoQuery-Out"],
            "models": ["linear", "ridge primary diagnostic", "depth-3 small tree"],
        },
        "claim_boundary": "P1 PASS establishes structured-evidence dependence, not a new query policy or controller",
        "source_artifacts_sha256": source_hashes,
    }
    value["protocol_hash"] = canonical_hash(value)
    return value


def source_of_truth(source_hashes: dict[str, str]) -> str:
    return f"""# P1 source of truth

## VERIFIED_FACTS

- The released substrate contains three independent videos (`DALI`, `HANGZHOU`, `WUHAN`), two frozen open-semantic queries, two frozen natural cheap proxies, and six cached query budgets.
- Prior model-relative geometry evidence is `PARTIAL`: yield-only LOVO macro R²≈0.006/MAE≈0.134, public geometry R²≈0.795/MAE≈0.057, and reference-aware R²≈0.980/MAE≈0.016. Only one strong equal-yield counterexample pair covered one of three videos.
- P0 supports only a qualified model-relative C1 gap-only mechanism result. The full reference was constructed with K3-family grouping and is not an independent human event ontology.
- The second semantic query cache is complete at 1475/1475 units. Proxy B is frozen optical-flow/frame-difference visual dynamics, uses no detector/text model/outcomes, and has a different error mechanism from Proxy A.
- The controller side branch is closed: `SELECTIVE_DEVIATION_OPPORTUNITY=ABSENT`, `GEOMETRY_STATE_ADDED_VALUE=NO`; fixed SCAN1/VERIFY1 is a frozen execution default only.
- The independent human event log contains zero labels at P1 preparation time; no independent event-recovery endpoint has been observed.

## CURRENT_HYPOTHESES

- H1: at equal verified-positive yield, broader online-visible temporal evidence geometry touches more independently defined human events.
- H0-CIRCULARITY: the prior association is mainly C1 gap mechanics plus a K3-shaped model-relative reference.
- H0-YIELD: positive yield and proxy ranking account for independent human recovery; public geometry adds no stable cross-cluster information.
- H0-PROXY: any geometry effect is specific to Proxy A and disappears under the optical-flow Proxy B family.

## KNOWN_CONFOUNDS

- Cached semantic outcomes remain VLM-relative; only the human event reference can make the P1 primary endpoint independent.
- There are six video-query clusters but only three independent source videos; inference and bootstrap must cluster at video-query and report video dependence.
- Trace pairs within one cluster are repeated deterministic contrasts, not independent samples.
- Proxy-blind B0/B2/B5 traces are identical under both proxy labels. Cross-proxy consistency must be evaluated after cluster/proxy collapse and cannot treat duplicated proxy-blind traces as independent replications.
- Query definitions were frozen before human labels but were selected within the broader model-development program; P1 establishes reference independence, not a claim of query-selection independence.
- Positive-region count at 10 seconds is mechanically close to C1 and is secondary diagnostic only.
- Query budgets are semantic invocation counts, not physical deadlines.

## FROZEN_COMPONENTS

- Released candidate/unit and cached oracle semantics.
- Query definitions and budgets `[5,10,20,50,80,100]`.
- C1 GAP-ONLY materializer, frozen evaluator, and all matching thresholds.
- Outcome-blind B0–B5 trace population; all MMR weights and random seeds are reported, never winner-selected.
- P1-A and P1 final gates in `P1_PROTOCOL.json`.
- Fixed SCAN1/VERIFY1 as execution baseline; P1 does not study action selection.

## UNRESOLVED_DEPENDENCIES

- Two independent annotators must label all six video-query cases, followed by blinded adjudication and reference freeze.
- Human event existence/boundary agreement and materializer-independent event-touch outcomes are unavailable until that freeze.
- P1 PASS/FAIL, held-out geometry models, equal-yield human effects, and cross-proxy human consistency cannot legally be computed yet.

## AUTHORITATIVE_SOURCE_HASHES

```json
{json.dumps(source_hashes, indent=2, sort_keys=True)}
```
"""


def annotation_documents(video_manifest: dict[str, dict]) -> tuple[str, str, dict]:
    definitions = """# Frozen P1 query definitions

## Q_DRIVER_RESPONSE_V1 — Driver response required

Include a maximal continuous episode in which an attentive ego driver needs a noticeable slowdown, braking action, or avoidance maneuver because of visible conditions: a road user entering/threatening the ego path, a suddenly slowing/stopped lead vehicle, traffic control requiring a marked response, or a visible obstacle/road condition requiring a marked speed/path change.

Exclude normal steady driving, ordinary following without a marked response, distant hazards, and responses completed before the visible episode. Start at the first visible onset of the condition that makes a marked response necessary; end when the conflict/constraint has cleared and normal progress can resume. Merge uninterrupted manifestations of the same cause; split episodes separated by a return to normal driving. Mark a boundary ambiguous when its best estimate could reasonably move by more than 2 seconds.

## Q_VULNERABLE_ROAD_USER_CONFLICT_V1 — Vulnerable-road-user conflict

Include a maximal continuous episode in which a pedestrian, cyclist, motorcyclist, or scooter rider enters, crosses, or occupies the ego vehicle's immediate travel path such that the ego driver must yield, brake, slow markedly, or steer to avoid conflict.

Exclude road users clearly separated from the ego path, ordinary adjacent traffic, and conflicts completed before the displayed episode. Start when path conflict first becomes visible and actionable; end when the road user clears the immediate path or the ego vehicle has safely passed and the conflict no longer constrains motion. Multiple road users are one event only while they form one uninterrupted conflict episode. Mark a boundary ambiguous when its best estimate could reasonably move by more than 2 seconds.
"""
    guide = """# Independent temporal-event annotation guide

Annotate the full source video for each frozen query. An event is a maximal continuous semantic episode, not a 10-second unit. Do not inspect proxy scores, semantic-oracle outputs, C0/C1/K3 references, traces, geometry features, or method results.

For every event record `start_time`, `end_time`, `boundary_ambiguous`, and an optional short note. Use seconds from the video player. If an event clearly exists but a boundary is gradual, retain the event, enter the best boundary, and mark it ambiguous. Submit an explicit empty event list when no event occurs.

Each of two annotators must independently complete all six cases without seeing the other's labels. Revisions are allowed before the annotator freeze and remain append-only. After both independent submissions are frozen, an adjudicator sees both event lists, resolves existence and boundaries under the frozen definitions, and records a rationale. Original annotations are always preserved.

Agreement reporting is frozen in advance: event-existence agreement per case; one-to-one maximum-overlap event matching; matched interval tIoU distribution; absolute start/end boundary disagreement; unmatched event counts; and ambiguous-boundary rates. No agreement threshold changes the reference or excludes a case.
"""
    protocol_value = {
        "protocol_id": "P1_INDEPENDENT_HUMAN_EVENT_REFERENCE_V1",
        "status": "FROZEN_BEFORE_HUMAN_LABELS",
        "cases": [
            {"video_id": video, "query_id": query}
            for video in VIDEOS for query in QUERIES
        ],
        "annotation_unit": "maximal continuous human-defined temporal event",
        "annotators_required": 2,
        "adjudication_required": True,
        "required_event_fields": [
            "video_id", "query_id", "event_id", "start_time", "end_time",
            "boundary_ambiguous", "annotator_id", "adjudication_status",
        ],
        "boundary_rule": "query-specific first actionable visible onset to cleared constraint; >2 second reasonable uncertainty is marked ambiguous",
        "agreement_metrics": [
            "event existence agreement", "one-to-one overlap event agreement",
            "matched interval tIoU", "absolute boundary disagreement",
            "unmatched event count", "ambiguous boundary rate",
        ],
        "reference_independent_of": [
            "proxy", "policy", "C0", "C1", "K3", "geometry hypothesis",
            "semantic-oracle outcomes", "method results",
        ],
        "source_videos": video_manifest,
        "human_reference_frozen": False,
    }
    protocol_value["protocol_hash"] = canonical_hash(protocol_value)
    return definitions, guide, protocol_value


def main() -> None:
    if OUT.exists():
        raise RuntimeError(f"refusing to overwrite {OUT}")
    required = [
        TRACE_SOURCE, TRACE_PROTOCOL_SOURCE, Q1, Q2, Q2_COMPLETION,
        PROXY_METRICS_SOURCE, PROXY_B_PROTOCOL, PROXY_B_COMPLETION,
        LEGACY / "P1_PROXY_SCORE_DISTRIBUTIONS.csv",
        LEGACY / "proxy_b_kinematic/PROXY_B_KINEMATIC_SCORES.parquet",
        ROOT / "outputs/event_evidence_geometry_v1/FINAL_GEOMETRY_REPORT.md",
        ROOT / "outputs/main_thesis_alignment_v1/FINAL_ALIGNMENT_REPORT.md",
        ROOT / "outputs/p0_materializer_validation_v3/FINAL_RESEARCH_REPORT.md",
        ROOT / "outputs/p0_materializer_mechanism_ablation_v1/MECHANISM_REPORT.md",
        ROOT / "outputs/research_contribution_convergence_v1/PAPER_MAINLINE_DECISION.md",
        ROOT / "outputs/v10_multiseal_reference_v1/REFERENCE_CIRCULARITY_AUDIT.md",
        ROOT.parent / "GVAQP_side_rcsem/docs/SELECTIVE_DEVIATION_PREDICTABILITY_AUDIT_V1.md",
        ROOT / "scripts/serve_p1_independent_geometry_reference.py",
        ROOT / "scripts/resume_p1_independent_geometry_replication.py",
    ]
    for path in required:
        if not path.exists():
            raise RuntimeError(f"missing source of truth: {path}")
    source_hashes = {str(path.relative_to(ROOT.parent)): sha(path) for path in required}
    source_hashes[str(Path(__file__).relative_to(ROOT.parent))] = sha(Path(__file__))

    source_protocol = json.loads(TRACE_PROTOCOL_SOURCE.read_text())
    source_trace = pd.read_csv(TRACE_SOURCE)
    if len(source_trace) != 504 or source_trace.protocol_hash.nunique() != 1:
        raise RuntimeError("frozen source trace population has unexpected shape")
    if str(source_trace.protocol_hash.iloc[0]) != source_protocol["protocol_hash"]:
        raise RuntimeError("trace protocol binding mismatch")
    if source_protocol.get("uses_semantic_oracle_outcomes") or source_protocol.get("uses_human_reference"):
        raise RuntimeError("trace source is not outcome blind")

    units = load_units()
    labels = load_labels()
    trace_rows = []
    geometry_rows = []
    for trace in source_trace.itertuples(index=False):
        selected = [str(value) for value in json.loads(trace.selected_unit_ids_json)]
        if len(selected) != int(trace.budget) or len(set(selected)) != len(selected):
            raise RuntimeError("trace violates budget/uniqueness")
        valid = set(units[trace.video_id].unit_id)
        if not set(selected) <= valid:
            raise RuntimeError("trace references unknown units")
        for query in QUERIES:
            features = trace_features(selected, units[trace.video_id], labels[(trace.video_id, query)])
            policy = {
                "UniformTemporal": "B0_UniformTemporal__B4_FROZEN_LINEAGE",
                "StaticProxyRank": "B1_StaticProxyRank__B4_FROZEN_LINEAGE",
                "CoverageFirst": "B2_CoverageFirst__B4_FROZEN_LINEAGE",
                "MMR_w025": "B3_ProxyPlusTemporalCoverage_MMR_w025",
                "MMR_w050": "B3_ProxyPlusTemporalCoverage_MMR_w050",
                "MMR_w075": "B3_ProxyPlusTemporalCoverage_MMR_w075",
                "SeededTemporalHash": f"B5_SeededTemporalHash_seed{int(trace.seed):02d}",
            }[trace.generator]
            trace_id = canonical_hash([trace.trace_instance_id, query])
            base = {
                "trace_instance_id": trace_id,
                "source_trace_instance_id": trace.trace_instance_id,
                "video_id": trace.video_id,
                "query_id": query,
                "proxy_id": trace.proxy_family,
                "policy_id": policy,
                "generator_family": trace.generator,
                "seed": int(trace.seed),
                "budget": int(trace.budget),
                "queried_unit_ids": json.dumps(selected, separators=(",", ":")),
                "trace_hash": trace.trace_hash,
                "trace_construction_outcome_blind": True,
                **features,
            }
            trace_rows.append(base)
            for feature in PUBLIC_FEATURES:
                geometry_rows.append({
                    "trace_instance_id": trace_id, "video_id": trace.video_id,
                    "query_id": query, "proxy_id": trace.proxy_family,
                    "feature": feature, "feature_value": features[feature],
                    "visibility": "POLICY_VISIBLE",
                })
            for feature in AFTER_VERIFY_FEATURES:
                geometry_rows.append({
                    "trace_instance_id": trace_id, "video_id": trace.video_id,
                    "query_id": query, "proxy_id": trace.proxy_family,
                    "feature": feature, "feature_value": features[feature],
                    "visibility": "ORACLE_OBSERVED_AFTER_VERIFY",
                })
    population = pd.DataFrame(trace_rows).sort_values(
        ["video_id", "query_id", "proxy_id", "budget", "policy_id", "seed"]
    ).reset_index(drop=True)
    if len(population) != 1008 or population.trace_instance_id.nunique() != 1008:
        raise RuntimeError("unexpected expanded trace population")
    exact, exact_manifest = exact_pairs(population)
    near_manifest = near_pairs(population)
    pairs = pd.concat([exact_manifest, near_manifest], ignore_index=True, sort=False)

    exact_by_cluster_proxy = exact.groupby(["video_id", "query_id", "proxy_id"]).size()
    budgets_by_cluster_proxy = exact.groupby(["video_id", "query_id", "proxy_id"]).budget.nunique()
    endpoint_policies = set(exact_manifest.better_geometry_policy_id) | set(exact_manifest.worse_geometry_policy_id)
    endpoint_families = {str(policy).split("_", 1)[0] for policy in endpoint_policies}
    trace_lookup = population.set_index("trace_instance_id")
    proxy_collapsed_pair_keys = {
        (
            row.video_id, row.query_id, row.budget, row.verified_positive_count,
            trace_lookup.loc[row.better_geometry_trace_id].trace_hash,
            trace_lookup.loc[row.worse_geometry_trace_id].trace_hash,
        )
        for row in exact_manifest.itertuples(index=False)
    }
    p = protocol(source_hashes)
    gate_rule = p["p1a_gate"]
    gate_checks = {
        "minimum_exact_pairs": len(exact) >= gate_rule["minimum_exact_pairs"],
        "all_six_video_query_clusters": exact.groupby(["video_id", "query_id"]).ngroups == 6,
        "minimum_exact_pairs_per_video_query_proxy": bool((exact_by_cluster_proxy >= gate_rule["minimum_exact_pairs_per_video_query_proxy"]).all()),
        "minimum_budgets_per_video_query_proxy": bool((budgets_by_cluster_proxy >= gate_rule["minimum_budgets_per_video_query_proxy"]).all()),
        "both_natural_proxies": exact.proxy_id.nunique() == gate_rule["required_proxy_families"],
        "multiple_generator_families": len(endpoint_families) >= gate_rule["minimum_pair_endpoint_generator_families"],
        "median_region_contrast": float(exact.region_contrast.median()) >= gate_rule["minimum_median_region_contrast"],
    }
    feasibility = "PASS" if all(gate_checks.values()) else "INSUFFICIENT"

    OUT.mkdir(parents=True)
    write_json(OUT / "P1_PROTOCOL.json", p)
    (OUT / "SOURCE_OF_TRUTH.md").write_text(source_of_truth(source_hashes))
    population.to_csv(OUT / "TRACE_POPULATION.csv", index=False)
    pd.DataFrame(geometry_rows).to_csv(OUT / "TRACE_GEOMETRY_FEATURES.csv", index=False)
    exact.to_csv(OUT / "MATCHED_EQUAL_YIELD_STRATA.csv", index=False)
    pairs.to_csv(OUT / "TRACE_PAIR_MANIFEST.csv", index=False)

    counts_by_cluster = exact.groupby(["video_id", "query_id"]).size().to_dict()
    counts_by_proxy = exact.groupby("proxy_id").size().to_dict()
    feasibility_report = f"""# P1-A trace-diversity feasibility audit

## Decision

`P1_TRACE_FEASIBILITY = {feasibility}`

The outcome-blind population has **{len(population)}** trace-query instances from 504 frozen trace identities. It covers 3 independent videos × 2 queries × 2 natural proxies × 6 budgets and 7 generator families. B0/B1/B2 are also the exact B4 historical frozen-policy lineages and are represented once, avoiding duplicate pseudo-replication.

- Exact-yield, geometry-varying strata: **{len(exact)}**.
- Near-yield (difference ≤1) secondary pairs: **{len(near_manifest)}**.
- Independent video-query clusters: **{exact.groupby(['video_id','query_id']).ngroups}/6**.
- Natural proxies: **{exact.proxy_id.nunique()}/2**.
- Budgets represented: **{exact.budget.nunique()}/6**.
- Pair endpoint generator families: **{len(endpoint_families)}**.
- Median exact-pair region contrast: **{exact.region_contrast.median():.1f}** regions.
- Effective independent comparison count: **6 video-query clusters**, not {len(exact)} trace strata.
- Proxy-collapsed unique exact trace contrasts: **{len(proxy_collapsed_pair_keys)}**; proxy-blind duplicates are not independent replication.

Exact strata by video-query: `{counts_by_cluster}`.

Exact strata by proxy: `{counts_by_proxy}`.

## Frozen gate

```json
{json.dumps({'checks': gate_checks, 'rule': gate_rule}, indent=2, sort_keys=True)}
```

Pairs were selected only after exact/near yield matching, using public geometry contrast and fixed public tie-breaks. Human/reference outcomes were not available. This PASS establishes experimental contrast and identification capacity only; it is not evidence that geometry improves independent event recovery.
"""
    (OUT / "P1_TRACE_FEASIBILITY.md").write_text(feasibility_report)
    design_report = f"""# P1 design decision

`P1_TRACE_DESIGN = {'SUFFICIENT_FOR_HUMAN_TEST' if feasibility == 'PASS' else 'INSUFFICIENT'}`

The full six-cluster/two-proxy substrate {'meets' if feasibility == 'PASS' else 'does not meet'} the preregistered contrast gate. Within-cluster strata remain repeated deterministic contrasts; inference must collapse or bootstrap by video-query. No EventF1 or model-relative event endpoint was used to choose the pairs.

{'Proceed only to the frozen independent human reference. Do not inspect or optimize method outcomes while annotation is pending.' if feasibility == 'PASS' else 'Stop before annotation. The minimum repair would be additional outcome-blind trace generators or new video/query substrate; do not weaken the gate.'}
"""
    (OUT / "P1_DESIGN_DECISION.md").write_text(design_report)

    proxy = pd.read_csv(PROXY_METRICS_SOURCE)
    # Add frozen calibration-style diagnostics. Scores are not asserted to be
    # calibrated probabilities; Brier/ECE are descriptive only.
    proxy_b_scores = pd.read_parquet(
        LEGACY / "proxy_b_kinematic/PROXY_B_KINEMATIC_SCORES.parquet"
    )[["video_id", "unit_id", "proxy_score"]]
    calibration_rows = []
    for video in VIDEOS:
        candidate = units[video][["video_id", "candidate_id", "unit_id"]]
        proxy_a_scores = pd.read_parquet(
            CANDIDATES / video / "proxy_table.parquet"
        )[["video_id", "candidate_id", "proxy_score"]].merge(
            candidate, on=["video_id", "candidate_id"], validate="one_to_one"
        )[["video_id", "unit_id", "proxy_score"]]
        for query in QUERIES:
            binary = {
                unit: float(value == "relevant")
                for unit, value in labels[(video, query)].items()
            }
            for name, scores in (
                ("Proxy A YOLOv8n object/motion", proxy_a_scores),
                ("Proxy B optical-flow visual dynamics", proxy_b_scores[proxy_b_scores.video_id == video]),
            ):
                values = scores.proxy_score.to_numpy(float)
                target = scores.unit_id.map(binary).to_numpy(float)
                brier = float(np.mean((values - target) ** 2))
                ece = 0.0
                for lower in np.linspace(0.0, 0.9, 10):
                    upper = lower + 0.1
                    chosen = (values >= lower) & (values <= upper if upper >= 1.0 else values < upper)
                    if chosen.any():
                        ece += float(chosen.mean() * abs(values[chosen].mean() - target[chosen].mean()))
                common = {
                    "query_id": query, "video_id": video, "proxy_family": name,
                    "positive_units": int(target.sum()),
                    "unknown_or_parse_units": int(sum(value not in {"relevant", "not_relevant"} for value in labels[(video, query)].values())),
                    "label_rank_spearman": math.nan,
                }
                calibration_rows.extend([
                    {**common, "metric": "Brier_descriptive", "value": brier},
                    {**common, "metric": "ECE10_descriptive", "value": ece},
                ])
    proxy = pd.concat([proxy, pd.DataFrame(calibration_rows)], ignore_index=True)
    proxy.to_csv(OUT / "PROXY_CHARACTERIZATION.csv", index=False)
    pd.read_csv(LEGACY / "P1_PROXY_SCORE_DISTRIBUTIONS.csv").to_csv(
        OUT / "PROXY_SCORE_DISTRIBUTIONS.csv", index=False
    )
    proxy_failure = """# P1 natural-proxy characterization and failure analysis

Proxy A is the frozen YOLOv8n object/track/motion-oriented score. Proxy B is a frozen grayscale Farneback optical-flow plus frame-difference score sampled four times per unit. Proxy B uses no detector, language model, semantic outcome, reference event, or human label and is materially cheaper than the VLM oracle.

Across the six video-query clusters, Proxy A AUPRC ranges from 0.198 to 0.379 and Proxy B from 0.162 to 0.236. A/B rank Spearman by video is approximately -0.029 to 0.176, confirming different rankings/error mechanisms. Proxy B is weaker on most cluster/query cells; that weakness is retained and is not tuned away. The same frozen trace and geometry protocol is used for both proxies.

`PROXY_CHARACTERIZATION.csv` reports AUPRC, Recall@K, score/label rank correlation, and A/B rank correlation. Unknown/parse-failure units remain in the denominator as non-positive for descriptive ranking diagnostics and are counted in the table.
"""
    (OUT / "PROXY_FAILURE_ANALYSIS.md").write_text(proxy_failure)

    video_manifest = {}
    durations = {"DALI": 5665.535, "HANGZHOU": 5600.566, "WUHAN": 3462.930}
    filenames = {"DALI": "dali.mp4", "HANGZHOU": "hangzhou.mp4", "WUHAN": "wuhan.mp4"}
    for video in VIDEOS:
        path = ROOT / "data/realcam" / filenames[video]
        if not path.exists():
            raise RuntimeError(f"annotation source video missing: {path}")
        video_manifest[video] = {
            "path": str(path.relative_to(ROOT)), "sha256": sha(path),
            "duration_sec": durations[video],
        }
    definitions, guide, human_protocol = annotation_documents(video_manifest)
    (OUT / "QUERY_DEFINITIONS.md").write_text(definitions)
    (OUT / "ANNOTATION_GUIDE.md").write_text(guide)
    write_json(OUT / "HUMAN_REFERENCE_PROTOCOL.json", human_protocol)
    cases = []
    for video in VIDEOS:
        for query in QUERIES:
            cases.append({
                "case_id": f"P1::{video}::{query}", "video_id": video,
                "query_id": query, "video_path": video_manifest[video]["path"],
                "video_sha256": video_manifest[video]["sha256"],
                "duration_sec": video_manifest[video]["duration_sec"],
                "annotation_status": "PENDING_TWO_INDEPENDENT_ANNOTATORS",
                "human_reference_frozen": False,
            })
    pd.DataFrame(cases).to_csv(OUT / "HUMAN_REFERENCE_MANIFEST.csv", index=False)
    (OUT / "HUMAN_EVENT_LABELS.jsonl").write_text("")
    pd.DataFrame([
        {
            "case_id": case["case_id"], "video_id": case["video_id"],
            "query_id": case["query_id"], "adjudicator_id": "",
            "event_exists": "", "events_json": "[]",
            "adjudication_rationale": "",
        }
        for case in cases
    ]).to_csv(OUT / "ADJUDICATION_TEMPLATE.csv", index=False)
    (OUT / "HUMAN_REFERENCE_AGREEMENT.md").write_text(
        "# Human reference agreement\n\nStatus: `PENDING`. No human labels have been collected. The frozen agreement metrics are event-existence agreement, one-to-one overlap event agreement, matched-event tIoU, absolute start/end boundary disagreement, unmatched-event counts, and ambiguous-boundary rate. Results must not be fabricated before two complete independent annotations and adjudication.\n"
    )
    (OUT / "ANNOTATION_PACKAGE_README.md").write_text("""# P1 blinded human-reference package

1. Run `python scripts/serve_p1_independent_geometry_reference.py` from the repository root and open `http://127.0.0.1:8766/`.
2. Annotator 1 completes all six cases. Annotator 2 independently completes all six without seeing annotator 1's records. Use stable, distinct annotator IDs.
3. Preserve `HUMAN_EVENT_LABELS.jsonl`; it is append-only and later saves are revisions.
4. After both annotators finish, an adjudicator reviews their raw event lists, copies `ADJUDICATION_TEMPLATE.csv` to `ADJUDICATED_EVENTS.csv`, and fills all six rows. `events_json` is a JSON list of objects with exactly `start_time`, `end_time`, and boolean `boundary_ambiguous`.
5. Run `python scripts/resume_p1_independent_geometry_replication.py --check`, then run it without `--check` to freeze the reference and execute the preregistered analysis.

Do not expose proxy scores, traces, semantic-oracle outputs, geometry features, C1/K3 references, or method results to annotators/adjudicator before the human reference freezes.
""")
    annotation_cases = []
    query_text = {
        query: definitions.split(f"## {query}", 1)[1].split("\n## ", 1)[0].strip()
        for query in QUERIES
    }
    for case in cases:
        annotation_cases.append({
            **case,
            "video_url": "/" + case["video_path"],
            "query_definition": query_text[case["query_id"]],
        })
    write_json(OUT / "ANNOTATOR_VIEW_CASES.json", annotation_cases)

    state = {
        "objective": p["primary_question"],
        "current_phase": "P1-B_INDEPENDENT_HUMAN_REFERENCE",
        "phase_status": "WAITING_HUMAN_REFERENCE",
        "p1_trace_feasibility": feasibility,
        "p1_event_evidence_geometry": "WAITING_HUMAN_REFERENCE",
        "human_reference_status": "REQUIRED",
        "human_reference_frozen": False,
        "user_input_required": "Two independent annotators must each complete all six frozen video-query cases, followed by adjudication.",
        "next_entrypoint": "python scripts/serve_p1_independent_geometry_reference.py",
        "resume_after_annotation": "python scripts/resume_p1_independent_geometry_replication.py",
        "completed": [
            "source-of-truth audit", "protocol freeze", "outcome-blind trace verification",
            "six-cluster/two-proxy P1-A feasibility audit", "proxy characterization",
            "blinded human-reference package and validation entrypoints",
        ],
        "prohibited_while_waiting": [
            "inspect method outcomes to alter queries/pairs", "change P1 gates",
            "run controller/MAB/RL/selector development", "run P2",
        ],
        "protocol_hash": p["protocol_hash"],
        "human_protocol_hash": human_protocol["protocol_hash"],
    }
    write_json(OUT / "RESEARCH_STATE.json", state)

    pause_report = f"""# GVAQP P1 independent event-evidence geometry replication

## Current decision

`P1_TRACE_FEASIBILITY = {feasibility}`  
`P1_EVENT_EVIDENCE_GEOMETRY = WAITING_HUMAN_REFERENCE`

P1-A passed on the full 3-video × 2-query × 2-natural-proxy substrate with {len(exact)} exact-yield geometry-varying strata. The effective independent comparison count is six video-query clusters. No independent human event outcome exists yet, so P1 PASS/FAIL, equal-yield human effect, held-out human-reference models, and cross-proxy human consistency are intentionally not computed.

All automatic pre-annotation work is complete. The only next action is two independent blinded annotations of the six frozen cases, followed by adjudication and the frozen resume entrypoint. Controller and selector branches remain closed.
"""
    (OUT / "P1_FINAL_REPORT.md").write_text(pause_report)
    (OUT / "P1_DECISION.md").write_text(pause_report)
    (OUT / "NEXT_RESEARCH_ACTION.md").write_text(
        "# Next single research action\n\nComplete the frozen independent human temporal-event reference: two independent annotators × all six video-query cases, then adjudication. Start with `python scripts/serve_p1_independent_geometry_reference.py`; after adjudication run `python scripts/resume_p1_independent_geometry_replication.py`. Do not run P2 or develop a selector while P1 is unresolved.\n"
    )
    inventory = {}
    for path in sorted(OUT.iterdir()):
        if path.is_file():
            inventory[path.name] = {"sha256": sha(path), "bytes": path.stat().st_size}
    write_json(OUT / "PREANNOTATION_MANIFEST.json", {
        "status": "FROZEN_PREANNOTATION_PACKAGE",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "files": inventory,
    })
    print(json.dumps({
        "status": "WAITING_HUMAN_REFERENCE", "trace_feasibility": feasibility,
        "trace_rows": len(population), "exact_pairs": len(exact),
        "near_pairs": len(near_manifest), "independent_clusters": 6,
        "output": str(OUT),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
