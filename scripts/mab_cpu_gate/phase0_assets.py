#!/usr/bin/env python3
"""Phase 0: asset audit for the CPU-only MAB gate.

Writes outputs/mab_cpu_gate_v1/ASSET_MANIFEST.csv and ASSET_AUDIT.md.
No inference. Missing artifacts are recorded NOT_AVAILABLE with their
recorded sha256 where a manifest preserves it.
"""
import csv, hashlib, json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs"
GATE = OUT / "mab_cpu_gate_v1"
GATE.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import VIDEOS, QUERY_VULN, QUERY_DRIVER, load_unit_grid, load_qwen32_labels, load_proxy_a_scores

def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

rows = []

def add(name, path, exists, hashv, schema, coverage, gran, ref_type, geo, av, mab, limit):
    rows.append({
        "artifact_name": name, "path": path, "exists": "YES" if exists else "NO",
        "hash": hashv or "", "schema": schema, "videos_covered": coverage,
        "queries_covered": "BOTH" if False else coverage[1] if isinstance(coverage, tuple) else "",
        "granularity": gran, "reference_type": ref_type,
        "usable_for_geometry": geo, "usable_for_action_value": av, "usable_for_mab_v0": mab,
        "scientific_limit": limit,
    })

# ---- present core artifacts ----
grid = load_unit_grid()
add("frozen_unit_grid", "outputs/accelerated_event_query_v1/video_manifests/frozen_unit_grid_v1.csv",
    True, sha256("outputs/accelerated_event_query_v1/video_manifests/frozen_unit_grid_v1.csv"),
    "video_id,unit_id,candidate_id,start_time,end_time", "3 videos, 1475 units", "10s",
    "none", True, True, True, "10s grid only; no sub-10s unit semantics")
add("qwen32_oracle_raw_jsonl", "outputs/gvaqp_long_horizon_p1_p3_v1/qwen32_oracle/raw/*.json",
    True, "per-file", "candidate_id,label,confidence,evidence,start/end", "1475 units", "10s",
    "MODEL_RELATIVE (Qwen3-VL-32B)", True, True, True, "Q_VULNERABLE only; labels full grid")
add("v3_raw_unit_detections", "outputs/v3_scan_proxy_preregistration_v1/frozen_raw/{v}/raw_unit_detections.jsonl",
    True, "per-video", "conf_sum,det_count,max_conf,start/end", "1475 units", "10s",
    "PROXY_SOURCE (YOLOv8n detections)", True, True, True,
    "Proxy A scores reconstructed deterministically from this; validated vs R0 manifest")
add("reconstructed_proxy_a_scores", "in-memory from raw_unit_detections (frozen scoring fn)",
    True, "reconstructed; validated vs PROXY_REGIME_MANIFEST R0 min/mean/max 1e-9",
    "candidate_id -> proxy_score", "1475 units", "10s", "PROXY (V3 YOLO)", True, True, True,
    "Reconstruction is deterministic and validated; Proxy B scores NOT reconstructible from this source")
add("p2_trace_manifest", "outputs/p2_query_policy_novelty_killer_v1/TRACE_MANIFEST.csv",
    True, sha256("outputs/p2_query_policy_novelty_killer_v1/TRACE_MANIFEST.csv"),
    "504 rows; per-trace queried units+outcomes+EventF1", "3v x 2q x 7p x 6b, seed0", "trace-level",
    "MODEL_RELATIVE C1 reference", True, True, True,
    "seed=0 only; queries at budget>=50 of 100 max; engine reproduces EventF1 252/252 (Q_VULNERABLE)")
add("p1_outcome_blind_trace_manifest", "outputs/gvaqp_long_horizon_p1_p3_v1/P1_OUTCOME_BLIND_TRACE_MANIFEST.csv",
    True, sha256("outputs/gvaqp_long_horizon_p1_p3_v1/P1_OUTCOME_BLIND_TRACE_MANIFEST.csv"),
    "504 traces; selected units, no outcomes", "3v x 2q x 2 proxies x 6b", "trace-level",
    "none (outcome-blind)", True, False, False, "no outcomes -> not usable for action value")
add("p0_controlled_pairs", "outputs/p0_materializer_validation_v3/controlled_pairs.csv",
    True, sha256("outputs/p0_materializer_validation_v3/controlled_pairs.csv"),
    "54 K0/K3 pairs, queried units + outcomes", "Q_DRIVER; 3v x 3s x 6b", "trace-level",
    "MODEL_RELATIVE (V10)", True, True, False, "Q_DRIVER only; 54 traces")
add("seal_b_authoritative_labels", "outputs/v10_multiseal_reference_v1/seals/SEAL_B/raw/*.json",
    True, "per-file", "authoritative_label per unit", "21 units only", "10s",
    "MODEL_RELATIVE (V10 multi-seal)", True, False, False, "21/1475 units -> cannot build Q_DRIVER full grid")
add("partial_scan_physical_pilot", "benchmarks/partial_scan_pilot_v1/",
    True, "immutable_manifest hashes", "per-unit detections.parquet/tracks/raw_candidates with timestamps",
    "PSP_V0_SHORT(=WUHAN) + PSP_V1_LONG(=DALI)", "frame-level detections", "PHYSICAL YOLO output",
    True, False, False, "BLOCKED pilot (policy isolation FAIL); frame-level detections usable for geometric granularity only")
add("video_feature_precompute_5s", "outputs/video_feature_precompute_v1/tables/{proxy_features_5s,coarse_5s_clip_grid}.csv",
    True, "per-file", "5s clips with motion/count/bbox features", "long_video_dataset3 (=WUHAN) only, 693 clips", "5s",
    "PROXY (different feature family)", True, False, False,
    "WUHAN-only 5s proxy features; proxy-level geometry only, no semantic outcomes at 5s")
add("guangzhou_physical_traces", "outputs/exploratory_temporal_order_guangzhou_v1/",
    True, "cited sha256 verified in prior audit", "deadline-safe trace + counterfactual probes",
    "1 source video", "physical action-level", "EXPLORATORY", True, False, False,
    "single source; abstract-cost and physical-cost mixed; not part of P2-style substrate")
add("psvr_proxy_finalization_wuhan", "outputs/psvr_proxy_finalization_v0/psvr_physical/proxy_scores_all_347.csv",
    True, sha256("outputs/psvr_proxy_finalization_v0/psvr_physical/proxy_scores_all_347.csv"),
    "unit_id,proxy_score,det_count,max_conf,start,end", "WUHAN only", "10s",
    "PROXY (legacy V3-line)", True, True, False, "WUHAN-only legacy; superseded by reconstruction")

# ---- absent core artifacts (recorded hashes from manifests) ----
absent = [
    ("proxy_table.parquet (A)", "outputs/v3_scan_proxy_preregistration_v1/frozen_tables/{v}/proxy_table.parquet",
     "per-video sha256 in SCAN_MANIFEST.json (DALI ed1121c7...)", "candidate_id,proxy_score",
     "1475 units", "10s", "PROXY (V3 YOLO)", True, True, True,
     "ABSENT locally; score reconstructed deterministically from frozen raw detections and validated"),
    ("candidate_table.parquet (A)", "outputs/v3_scan_proxy_preregistration_v1/frozen_tables/{v}/candidate_table.parquet",
     "per-video sha256 in SCAN_MANIFEST.json (DALI 2d9feaf0...)", "candidate rows",
     "1475 units", "10s", "n/a", True, True, True,
     "ABSENT locally; identity recovered from frozen_unit_grid_v1.csv"),
    ("FINAL_UNIT_REFERENCE.parquet (Q_DRIVER labels)", "outputs/v10_multiseal_reference_v1/FINAL_UNIT_REFERENCE.parquet",
     "sha256 4f732859e7aaca6a4d80... (REFERENCE_MANIFEST.json)", "unit labels", "1475 units",
     "10s", "MODEL_RELATIVE (V10 Qwen3-VL-32B-Instruct-FP8)", True, True, True,
     "ABSENT locally; Q_DRIVER full grid unrecoverable (seal raw only 21 units); union trace labels partial"),
    ("P1_QWEN32_UNIT_OUTCOMES.parquet (Q_VULNERABLE table)", "outputs/gvaqp_long_horizon_p1_p3_v1/qwen32_oracle/P1_QWEN32_UNIT_OUTCOMES.parquet",
     "sha256 9dfb1f9b7cdf50e0f3a0... (P2_PROTOCOL.json)", "unit labels", "1475 units",
     "10s", "MODEL_RELATIVE (Qwen3-VL-32B)", True, True, True,
     "ABSENT locally; equivalent full table reconstructed from qwen32_oracle/raw/*.json (1475/1475)"),
    ("PROXY_B_KINEMATIC_SCORES.parquet", "outputs/gvaqp_long_horizon_p1_p3_v1/proxy_b_kinematic/PROXY_B_KINEMATIC_SCORES.parquet",
     "sha256 997982b64e02eb41c492... (P2_PROTOCOL.json)", "candidate_id,proxy_score", "1475 units",
     "10s", "PROXY (optical-flow)", True, True, True,
     "ABSENT locally; optical-flow scores NOT reconstructible from YOLO detections -> Proxy B per-unit scores NOT_AVAILABLE"),
    ("V10_K3_EVENT_RELATION.parquet", "outputs/v10_multiseal_reference_v1/ (event relation)",
     "sha256 f16e24103921ada7f823... (REFERENCE_MANIFEST.json)", "reference events", "3 videos",
     "10s", "MODEL_RELATIVE K3 reference", True, True, True,
     "ABSENT locally; Q_VULNERABLE reference rebuilt from raw labels (validated 252/252); Q_DRIVER reference unrecoverable full"),
    ("2s/5s semantic verifier outcomes", "NOT FOUND anywhere in repo",
     "", "n/a", "none", "2s/5s", "n/a", True, False, False,
     "NO cached 2s/5s semantic outcomes exist; 5s proxy features exist for WUHAN only (proxy-level)"),
]
for a in absent:
    rows.append({"artifact_name": a[0], "path": a[1], "exists": "NO", "hash": a[2],
                 "schema": a[3], "videos_covered": a[4], "queries_covered": "BOTH",
                 "granularity": a[5], "reference_type": a[6], "usable_for_geometry": a[7],
                 "usable_for_action_value": a[8], "usable_for_mab_v0": a[9], "scientific_limit": a[10]})

with open(GATE / "ASSET_MANIFEST.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

n_present = sum(1 for r in rows if r["exists"] == "YES")
n_absent = len(rows) - n_present

audit = f"""# ASSET_AUDIT — CPU-only MAB gate, Phase 0

Date: 2026-08-13. Mode: static inventory + deterministic reconstruction. No inference.

## Summary

- Core artifacts present: {n_present}; absent (recorded hashes only): {n_absent}.
- The P1/P2 pipeline's five substrate parquet tables are **not in this checkout**
  (consistent with provenance/omitted_legacy_manifest.csv: `*.parquet` = D_BULK_RESULT).
- However, two full substrates ARE locally reconstructible deterministically from
  frozen raw artifacts:
  1. **Q_VULNERABLE full 1475-unit semantic table** <- qwen32_oracle/raw/*.json
     (264 relevant / 1207 not_relevant / 4 parse_failure).
  2. **Proxy A (V3 YOLO) per-unit scores** <- raw_unit_detections.jsonl via the
     frozen scoring function `0.5*min(det_count,20)/20 + 0.5*max_conf`;
     per-video min/mean/max validated against PROXY_REGIME_MANIFEST R0 rows to 1e-9.

## Hard limits (declared, not guessed)

1. **No 2s/5s semantic outcomes exist anywhere locally**; the model-relative
   reference itself is 10s-quantized -> multi-granularity action value is
   BLOCKED_GPU_MULTIGRANULARITY; only geometric/granularity-ceiling analysis
   is possible (Phase 1).
2. **Q_DRIVER full grid is unrecoverable** (seal raw = 21/1475 units; the
   FINAL_UNIT_REFERENCE.parquet sha256 4f732859... is recorded but the file is
   absent). Q_DRIVER analysis below uses the union of trace-queried labels
   (283-333 units/cluster) and is marked MODEL_RELATIVE_DIAGNOSTIC_ONLY with a
   PARTIAL reference reconstructed from known positives only.
3. **Proxy B per-unit scores are NOT_AVAILABLE** (parquet absent; optical-flow
   scores not reconstructible from YOLO detections). Proxy B remains usable
   only through the P2 trace corpus as a policy-order source, not as features.
4. **Costs**: no local wall-clock VERIFY cost profile exists; the gate uses
   abstract query-count budgets (5..100) with cost sensitivity notes.
   Physical SCAN costs from the blocked pilot (warm median ~1.18-1.21 s) and a
   few Guangzhou VERIFY durations (~8-10 s) exist but are single-source and
   marked exploratory.
5. **Human reference: 0 labels** (P1 frozen, unread). All values below are
   MODEL_RELATIVE_DIAGNOSTIC_ONLY. Final decision records
   BLOCKED_INDEPENDENT_REFERENCE for human-event claims.

## Fidelity anchor

scripts/mab_cpu_gate/validate_engine.py: C1 materializer + strict-overlap 1:1
matching reproduce P2 TRACE_MANIFEST EventF1/TP/FP/FN for all 252
Q_VULNERABLE rows with **0 mismatches** (reference: 55/50/32 events for
DALI/HANGZHOU/WUHAN from 127/84/53 positives).
"""
(GATE / "ASSET_AUDIT.md").write_text(audit)
print(f"ASSET_MANIFEST.csv rows={len(rows)} present={n_present} absent={n_absent}")
print("ASSET_AUDIT.md written")
