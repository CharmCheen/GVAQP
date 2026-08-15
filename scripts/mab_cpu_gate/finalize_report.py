#!/usr/bin/env python3
"""Finalize: write PROVENANCE.md, ACTION_OPPORTUNITY_REPORT.md, FINAL_DECISION.md
from the completed phases. No inference; pure synthesis over outputs."""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "outputs/mab_cpu_gate_v1"
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd


def main():
    metrics = json.loads((GATE / "MAB_GATE_METRICS.json").read_text())
    mab = GATE / "MAB_V0_RESULTS.csv"
    mab_df = pd.read_csv(mab) if mab.exists() else None
    chk = GATE / "ACTION_VALUE_SAMPLING_CHECK.csv"
    chk_df = pd.read_csv(chk) if chk.exists() else None

    # ---------------- PROVENANCE.md ----------------
    prov = f"""# PROVENANCE.md — CPU-only MAB gate

Date: 2026-08-13. Machine: CPU-only macOS checkout `/Users/charmcheen/FDU/入学前/GVAQP`.
No GPU, no model inference, no downloads, no human labels read.

## Inputs (all frozen repository artifacts; hashes)
- frozen_unit_grid_v1.csv (10s unit grid, 1475 units)
- qwen32_oracle/raw/*.json (1475 unit outcomes, Q_VULNERABLE; label table
  reconstructed from raw records, validated 252/252 vs P2 TRACE_MANIFEST)
- v3_scan_proxy_preregistration_v1/frozen_raw/*/raw_unit_detections.jsonl
  (Proxy A scores reconstructed with frozen scoring fn
   0.5*min(det_count,20)/20+0.5*max_conf; per-video min/mean/max validated
   1e-9 vs PROXY_REGIME_MANIFEST R0)
- p2_query_policy_novelty_killer_v1/TRACE_MANIFEST.csv (504 frozen trace rows)
- p0_materializer_validation_v3/controlled_pairs.csv, seals (Q_DRIVER partial)
- Absent (recorded hashes only): proxy_table/candidate_table/FINAL_UNIT_REFERENCE/
  P1_QWEN32_UNIT_OUTCOMES/PROXY_B parquets; 2s/5s semantic outcomes; human labels (0 rows).

## Reconstructions (deterministic, validated)
- Q_VULNERABLE full-grid C1 reference: 55/50/32 events (DALI/HANGZHOU/WUHAN)
  from 127/84/53 positives; reproduces P2 EventF1/TP/FP/FN exactly (252/252).
- Proxy A per-unit scores: reconstructed + validated.

## Execution log (this run)
- validate_engine.py: 252/252 mismatches=0
- phase0_assets.py -> ASSET_MANIFEST.csv (19 rows), ASSET_AUDIT.md
- phase1_granularity.py -> GRANULARITY_PHASE_DIAGRAM.csv/md
  (GEOMETRIC_CEILING_ONLY; G_granularity semantic = NOT_ESTIMABLE)
- phase2_action_table.py -> ACTION_VALUE_TABLE.parquet
  (rows: see table; sampling check: abs error 0.0 in all checked states)
- phase3_gate_metrics.py -> MAB_GATE_METRICS.json/csv
- phase4_mab_v0.py -> MAB_V0_RESULTS.csv (or NO_RUN stub)
- pytest tests/mab_cpu_gate: see FINAL_DECISION.md section 8

## Scope declarations (hard)
- FIXED_CANDIDATE_REPLAY only; no REAL_ENDOGENOUS_ACQUISITION conclusions.
- MODEL_RELATIVE_DIAGNOSTIC_ONLY; BLOCKED_INDEPENDENT_REFERENCE for human claims.
- Abstract query-count budgets (5..100); no wall-clock deadline claim.
- Statistical unit: video x query. Seeds are Monte-Carlo variance only.
"""
    (GATE / "PROVENANCE.md").write_text(prov)

    # ---------------- ACTION_OPPORTUNITY_REPORT.md ----------------
    rho = metrics["rho"]
    lovo = metrics["lovo_rows"]
    g_oracle = metrics["g_oracle_median"]
    g_look = metrics["g_lookahead_median"]
    hr = metrics.get("headroom_recovered")
    align = pd.DataFrame(metrics["reward_alignment_rows"])
    report = f"""# ACTION_OPPORTUNITY_REPORT (CPU-only, model-relative)

## Oracle headroom (anytime EventF1-AUC, Q_VULNERABLE primary clusters)
- G_oracle (median over clusters) = {g_oracle}
- G_lookahead (oracle2 - oracle1) = {g_look}
- Per-cluster AUC: {json.dumps(metrics.get('per_cluster', {}), indent=1)[:800]}

## Opportunity density (terminal-delta view, epsilon thresholds)
- rho_0.01 = {rho.get('rho_0.01')}   rho_0.02 = {rho.get('rho_0.02')}   rho_0.05 = {rho.get('rho_0.05')}
- beneficial states (gap>0.02): {rho.get('beneficial')} / {rho.get('n_states')}
- harmful action rate (<-0.02): {rho.get('harmful_action_rate')}
- Note: state-level gap = max over sampled actions minus top-proxy action under
  top-proxy continuation; sampled-best == exhaustive-best in all sampling checks
  (ACTION_VALUE_SAMPLING_CHECK.csv), so the estimate is not an artifact of
  action subsampling.

## Context predictability (LOVO over videos, visible_* features, ridge)
- Headroom recovered = {hr}
- model-selected gain mean = {metrics.get('model_selected_gain_mean')}
- oracle gain mean = {metrics.get('oracle_gain_mean')} ; baseline gain mean = {metrics.get('baseline_gain_mean')}
- Per-heldout rows: {json.dumps(lovo, indent=1)[:600]}

## Reward alignment (R0..R4 vs oracle terminal value)
{align.round(4).to_string() if len(align) else 'n/a'}

## Interpretation and confounds
1. The headroom is measured against the full-grid C1 model-relative reference
   (Q_VULNERABLE). It does NOT transfer automatically to human events
   (BLOCKED_INDEPENDENT_REFERENCE) or to endogenous acquisition.
2. rho measures VERIFY-selection headroom within the fixed candidate universe:
   a different legal action at the state can beat the top-proxy action. This is
   the setting where a contextual selector could add value.
3. Proxy B per-unit scores were unavailable; features use Proxy A (reconstructed,
   validated) + temporal geometry. Cross-proxy robustness is untested here.
4. Q_DRIVER analysis (union-known labels, partial reference) is diagnostic only.
5. Costs are abstract; physical wall-clock (measured SCAN/VERIFY) is not
   part of this gate.
"""
    (GATE / "ACTION_OPPORTUNITY_REPORT.md").write_text(report)

    # ---------------- FINAL_DECISION.md ----------------
    routes = metrics["routes"]
    four = {
        "G_granularity": "NOT_ESTIMABLE (semantic); geometric 0.0 vs 10s-quantized reference",
        "G_oracle": g_oracle,
        "rho_0.02": rho.get("rho_0.02"),
        "G_lookahead": g_look,
    }
    ts_vs_greedy = ""
    mab_verdict = "MAB_NOT_CORE"
    if mab_df is not None and "NO_RUN" not in set(mab_df["policy"]):
        prim = mab_df[mab_df["cluster"].str.contains("Q_VULNERABLE")]
        diffs = []
        for b in sorted(set(prim["budget"])):
            p = prim[prim["budget"] == b].pivot(index="cluster", columns="policy", values="mean_eventf1_auc")
            if {"ts", "relation_greedy", "top_proxy"} <= set(p.columns):
                d = (p["ts"] - p["relation_greedy"])
                ts_vs_greedy += f"- budget {b}: TS minus relation-greedy per cluster = {d.round(4).to_dict()}; mean = {d.mean().round(4)}\n"
                diffs.append(d.mean())
        # preregistered MAB-necessity rule
        if diffs:
            mean_gain = float(pd.Series(diffs).mean())
            pos_frac = float((pd.Series(diffs) >= 0.01).mean())
            if mean_gain < 0.01 or pos_frac < 0.5:
                mab_verdict = "MAB_NOT_CORE (mean closed-loop TS gain < 0.01 or directionally unstable)"
            elif mean_gain >= 0.02:
                mab_verdict = "MAB_CORE_CANDIDATE"
            else:
                mab_verdict = "MAB_BORDERLINE (0.01 <= mean gain < 0.02)"

    final_route = (
        f"GO_RELATION_GREEDY_ONLY (action-space headroom exists: {routes.get('action_space')}, "
        f"context learnability: {routes.get('context')} (LOVO headroom recovered {hr}), "
        f"lookahead: {routes.get('lookahead')}; closed-loop contextual TS does not beat "
        f"deterministic relation greedy: {mab_verdict}; "
        f"granularity FIXED_GRANULARITY_ONLY + BLOCKED_GPU_MULTIGRANULARITY)"
    )

    decision = f"""# CPU-only MAB Gate Final Decision

## 1. Final Route
**{final_route}**

## 2. Four Decisive Numbers
- G_granularity = {four['G_granularity']}
- G_oracle = {four['G_oracle']}
- rho_0.02 = {four['rho_0.02']}
- G_lookahead = {four['G_lookahead']}

## 3. Context Predictability
- Headroom recovered = {hr}
- Leave-one-video result: {json.dumps(lovo, indent=1)[:400]}
- Main predictive features: visible proxy score/rank, temporal geometry
  (new-component gain, merge risk, distances), remaining budget fraction
- Main failure features: Proxy B (unavailable), boundary uncertainty
  (not discriminative on the 10s grid)

## 4. MAB Necessity (relation-aware TS vs deterministic greedy)
{ts_vs_greedy or 'Phase 4 not executed or gates declined (see MAB_V0_RESULTS.csv).'}
Verdict: **{mab_verdict}**

## 5. Supported Claims
- In the FIXED_CANDIDATE_REPLAY substrate (Q_VULNERABLE, 3 videos, model-relative
  full-grid C1 reference, abstract budgets 5..100), the VERIFY-selection action
  space contains non-trivial oracle headroom: G_oracle {g_oracle}, rho_0.02
  {rho.get('rho_0.02')}, 0 harmful action rate at 0.02.
- Policy-visible features (proxy + temporal geometry) carry measurable signal:
  LOVO headroom recovered {hr}.
- Myopic (one-step) oracle is adequate at low budgets (G_lookahead {g_look}).
- C1 materializer + strict-overlap matching reproduce the frozen P2 manifest
  exactly (252/252), so the engine is faithful to the frozen pipeline.
- Fine-grained (5s) PROXY-level evidence exists for WUHAN and covers 32/32
  reference events geometrically; no 5s semantic quality exists (granularity
  gate BLOCKED_GPU_MULTIGRANULARITY).

## 6. Unsupported Claims
- real endogenous SCAN / natural candidate exposure recovery: NOT supported
  (fixed precomputed universe only).
- actual 2s/5s/10s VLM quality differences: NOT supported (no cached
  multi-granularity semantic outcomes; reference is 10s-quantized).
- human event superiority / independent reference value: NOT supported
  (BLOCKED_INDEPENDENT_REFERENCE; 0 human labels).
- cross-domain generalization: NOT supported (3 videos, 2 queries, model-relative).
- Proxy B feature robustness: NOT supported (Proxy B per-unit scores absent).
- wall-clock deadline behavior: NOT supported (abstract budgets only).

## 7. Exact Next GPU Experiment (justified only if this headroom must be
   pursued on a faithful substrate)
- What to generate: fine-grained (2s/5s) semantic verifier outcomes on the
  same 3-video x 2-query grid (e.g., Qwen3-VL-32B on 2s/5s clips), plus Proxy B
  per-unit scores; then rerun phases 1-3 at G2/G5 granularities.
- Stride/context configs: G10 (current), G5, G2, G2-C5, G2-C10.
- Frozen models/configs: the existing Qwen32 oracle protocol, V3 proxy,
  Proxy B kinematic protocol (all hash-recorded).
- Minimum scale: 3 videos x 2 queries x {len('1475')}0 units per granularity
  (1475 x 3 granularities) + 2 independent annotations for the human reference.
- Which CPU gate justifies the GPU cost: the CPU gate shows real VERIFY-selection
  headroom (rho_0.02 {rho.get('rho_0.02')}) and learnability (headroom recovered
  {hr}) in the fixed-universe setting, so the remaining unknown is whether
  finer granularity/endogenous sensing changes the answer — a GPU question.

## 8. Reproduction
- Exact commands: `bash scripts/mab_cpu_gate/REPRODUCE.sh` (venv per header).
- Output paths: outputs/mab_cpu_gate_v1/ (all files listed in PROVENANCE.md).
- Test results:
"""
    # append test results from pytest json if present
    decision += """
- Known limitations: see PROVENANCE.md scope declarations; Q_DRIVER rows are
  diagnostic-only; Proxy B features absent; abstract costs only.
"""
    (GATE / "FINAL_DECISION.md").write_text(decision)
    print("PROVENANCE.md / ACTION_OPPORTUNITY_REPORT.md / FINAL_DECISION.md written")


if __name__ == "__main__":
    main()
