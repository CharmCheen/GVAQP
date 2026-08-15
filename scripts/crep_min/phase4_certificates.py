#!/usr/bin/env python3
"""CREP-Min Phase 4: certificates for existing GVAQP conclusions + real
partial intervals (unknown-label bounds on Q_DRIVER traces). CPU-only."""
import csv, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "outputs/crep_min_v1"
sys.path.insert(0, str(ROOT / "scripts/mab_cpu_gate"))

import numpy as np
import pandas as pd

from common import (VIDEOS, QUERY_VULN, QUERY_DRIVER, load_unit_grid,
                    load_qwen32_labels, load_trace_labels, load_seal_labels,
                    c1_materialize, event_f1)

GRID = load_unit_grid()
Q32 = load_qwen32_labels()
UNION = {**load_trace_labels(), **load_seal_labels()}

UNIT_INTERVAL = {}
for v in VIDEOS:
    for u in GRID[v]:
        UNIT_INTERVAL[u["candidate_id"]] = (u["candidate_id"], u["start_time"], u["end_time"])


def build_reference(video, query, labels):
    pos = [UNIT_INTERVAL[c] for c in UNIT_INTERVAL
           if c.startswith(f"{video}_") and labels.get(c) == "relevant"]
    return c1_materialize(video, query, pos)


def f1_for(video, query, queried, labels, unknown_as):
    pos = [UNIT_INTERVAL[u] for u in queried
           if labels.get(u) == "relevant" or (unknown_as == "relevant" and labels.get(u) in ("unknown", "parse_failure"))]
    pred = c1_materialize(video, query, pos)
    ref = build_reference(video, query, labels)
    return event_f1(pred, ref)["EventF1"]


def partial_intervals():
    rows = []
    with open(ROOT / "outputs/p2_query_policy_novelty_killer_v1/TRACE_MANIFEST.csv") as f:
        for r in csv.DictReader(f):
            if r["query_id"] != QUERY_DRIVER:
                continue
            units = json.loads(r["queried_unit_ids_json"])
            lo = f1_for(r["video_id"], r["query_id"], units, UNION, unknown_as="negative")
            hi = f1_for(r["video_id"], r["query_id"], units, UNION, unknown_as="relevant")
            rows.append({"video_id": r["video_id"], "policy": r["policy"], "budget": int(r["budget"]),
                         "EventF1_lower_unknown_as_negative": lo, "EventF1_upper_unknown_as_relevant": hi,
                         "interval_width": hi - lo, "trace_hash": r["trace_hash"]})
    df = pd.DataFrame(rows)
    df.to_csv(GATE / "PARTIAL_INTERVALS.csv", index=False)
    # cluster-level medians
    med = df.groupby(["video_id", "policy"])[["EventF1_lower_unknown_as_negative",
                                              "EventF1_upper_unknown_as_relevant", "interval_width"]].median()
    return med.round(4), df


def main():
    med, df = partial_intervals()
    # sanity: interval widths are genuinely sub-trivial (< 1.0) and non-degenerate
    n_nontrivial = int((df["interval_width"] > 0.01).sum())
    n_trivial_full = int((df["interval_width"] < 1.0).sum())
    print("Q_DRIVER partial intervals: rows", len(df), "| width>0.01:", n_nontrivial,
          "| width<1.0:", n_trivial_full)
    print(med.to_string())

    certs = [
        dict(claim_id="CLAIM_1_FIXED_VS_DYNAMIC",
             target_policies="FIXED_SCAN1_VERIFY1 vs DYNAMIC_ADAPTIVE_K3_VALUE_V3 (cached)",
             target_metric="mean anytime event-recall AUC",
             replay_status="CERTIFIED_REPLAYABLE (cached corpus, dataset3_development)",
             closures_satisfied="A,B,C,D(abstract),E,F",
             closures_missing="none within corpus; physical generalization outside corpus",
             exact_value="0.13323 vs 0.12228 (RC_SEM manifest; deterministic rerun hash verified)",
             counterexample_witness="none (corpus-scoped exact)",
             version_hashes="RC_SEM_PACKAGE_MANIFEST.json bundle aef5f751...; artifact hashes 8adc3fed...",
             scope_note="CERTIFIED only for the recorded cached corpus; single domain"),
        dict(claim_id="CLAIM_2_MAB_V0_VS_RELATION_GREEDY",
             target_policies="Bayesian-logistic contextual TS vs relation-greedy (top-50 proxy)",
             target_metric="EventF1-AUC (abstract budgets 5..100)",
             replay_status="CERTIFIED_REPLAYABLE (fixed-candidate semantics)",
             closures_satisfied="A,B,C,D(abstract),E,F",
             closures_missing="none",
             exact_value="TS-RG mean delta per budget: +0.0029..+0.0090; MAB_NOT_CORE; 50 seeds x 6 budgets x 6 clusters",
             counterexample_witness="none; deterministic seeds archived in MAB_V0_RESULTS.csv",
             version_hashes="mab_cpu_gate_v1 PROVENANCE.md; engine fidelity 252/252",
             scope_note="MODEL_RELATIVE_DIAGNOSTIC"),
        dict(claim_id="CLAIM_3_RELATION_VS_GENERIC",
             target_policies="relation_greedy vs {stratified, frozen-MMR, region-UCB, coverage, facility, exsample}",
             target_metric="EventF1-AUC",
             replay_status="CERTIFIED_REPLAYABLE (fixed-candidate semantics)",
             closures_satisfied="A,B,C,D(abstract),E,F",
             closures_missing="none",
             exact_value="G_generic median -0.0194; equal-yield residual median 0.0; R1=R2=R3=R4",
             counterexample_witness="E4 materializer reversal_rate 0.2222 (C6/C7 witness); E4GAP gap sensitivity 0.0001-0.0016",
             version_hashes="eraea_cpu_novelty_gate_v1 PROVENANCE.md",
             scope_note="MODEL_RELATIVE_DIAGNOSTIC; the reversal witness bounds the cert to the C1-pinned evaluator"),
        dict(claim_id="CLAIM_4_MATERIALIZER_RANKING",
             target_policies="K0 vs C1(gap-only) vs C3 vs K3 (same 54 traces)",
             target_metric="Delta EventF1 (controlled pairs)",
             replay_status="CERTIFIED_REPLAYABLE (frozen trace corpus)",
             closures_satisfied="A,B,C,D(abstract),E,F",
             closures_missing="none; REFERENCE_CIRCULARITY is an external-validity flag, not a replay gap",
             exact_value="K3>K0 40/14/0, median +0.1457; gap-only +0.1377; duration/barrier/extras 0.0",
             counterexample_witness="none for the corpus; C6/C7 generic witnesses show ranking is materializer-version-bound",
             version_hashes="P0 protocol ad619c84...; mechanism protocol bde64b32...",
             scope_note="K3 reference defined by same model+adapter (circularity qualified)"),
        dict(claim_id="CLAIM_5_ORACLE_HEADROOM",
             target_policies="one-step/depth-2 oracle vs strongest legal fixed baseline",
             target_metric="EventF1-AUC",
             replay_status="CERTIFIED_REPLAYABLE (as an upper-bound measurement)",
             closures_satisfied="A,B,C,D(abstract),E,F",
             closures_missing="none for the bound itself; the bound is an upper bound, not reachable",
             exact_value="G_oracle=0.474; rho_0.02=0.590; oracle1==oracle2 (G_lookahead=0.0)",
             counterexample_witness="C5: a leaked policy could imitate the oracle -> oracle-like numbers are not evidence of legal headroom capture",
             version_hashes="mab_cpu_gate_v1 PROVENANCE.md",
             scope_note="full-information upper bound; legal capture remains unachieved (CLAIM_2/3)"),
        dict(claim_id="CLAIM_6_GRANULARITY",
             target_policies="G2/G5/G10 fixed grids; adaptive-granularity oracle",
             target_metric="boundary-IoU ceiling; EventF1-AUC",
             replay_status="CERTIFIED_REPLAYABLE (model-relative reference only) + NOT_IDENTIFIABLE (human-event extension)",
             closures_satisfied="A,B(full-grid VLM),C,D(abstract),E,F",
             closures_missing="B(human outcome law) for the human-scale claim; continuous-time reference absent",
             exact_value="geometric G_granularity=0.0 vs 10s-quantized reference; semantic NOT_ESTIMABLE; WUHAN 5s proxy coverage 32/32 (proxy-level)",
             counterexample_witness="none needed: reference quantization makes finer grids structurally inert",
             version_hashes="mab_cpu_gate_v1 GRANULARITY_PHASE_DIAGRAM.csv",
             scope_note="BLOCKED_GPU_MULTIGRANULARITY + BLOCKED_HUMAN_REFERENCE"),
        dict(claim_id="CLAIM_7_CANDIDATE_EXPOSURE",
             target_policies="exposure semantics of the audited substrate",
             target_metric="candidate exposure recall; natural miss rate",
             replay_status="CERTIFIED_REPLAYABLE (audited substrate) + NOT_IDENTIFIABLE (natural-endogenous claim)",
             closures_satisfied="A,B,C,D(abstract),E,F for precomputed universe",
             closures_missing="C2/C3 (candidate creation, legal-action transitions) for endogenous SCAN",
             exact_value="exposure recall = 1.0 by construction (1475/1475); synthetic E3 gap 0.0; natural misses structurally impossible",
             counterexample_witness="C2/C3 witnesses: same observation can yield different candidate sets in unlogged worlds",
             version_hashes="main_thesis_alignment PROTOCOL_HASH 14e0b391...; SCAN_MANIFEST hashes",
             scope_note="no natural exposure claim is certifiable on this substrate"),
        dict(claim_id="CLAIM_8_DEADLINE_UTILITY",
             target_policies="chronological A / bisection B / scan-then-verify C (Guangzhou, 300s)",
             target_metric="deadline-safe event Recall/F1@300s; AUC[0,300]",
             replay_status="PARTIALLY_IDENTIFIABLE",
             closures_satisfied="D(physical finish timestamps recorded),F",
             closures_missing="A,B,C cross-source closure (single source video); E partially (physical runs)",
             exact_value="B: 1 event at 224.68s (repeat 224.20s); A/C zero deadline utility; 0/18, 1/7 probes",
             counterexample_witness="C4 witness: identical outcome before/after deadline flips ranking (B vs C is exactly this)",
             version_hashes="RESULTS_DEADLINE_SAFE.json 72efde93...; B trace bbfac511...",
             scope_note="single-source exploratory; NOT cross-source certified"),
    ]
    (GATE / "CLAIM_CERTIFICATES.csv").write_text(
        pd.DataFrame(certs).to_csv(index=False))
    print("CLAIM_CERTIFICATES.csv written")


if __name__ == "__main__":
    main()
