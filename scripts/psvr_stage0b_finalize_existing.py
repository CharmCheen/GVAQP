#!/usr/bin/env python3
"""Recompute the Stage 0B gate from already captured physical observations."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/psvr_stage0b_physical_profile"


def main() -> None:
    summary = pd.read_csv(OUT / "operator_latency_summary.csv").set_index(["operator", "phase"])
    old = json.loads((OUT / "partial_proxy_gate.json").read_text())
    get = lambda op, phase, col: float(summary.loc[(op, phase), col])
    proxy_init = get("proxy_model_initialization", "cold", "p95_seconds")
    oracle_init = get("oracle_model_initialization", "cold", "p95_seconds")
    coarse = get("coarse_scan", "warm", "p95_seconds")
    full = get("full_proxy", "warm", "p50_seconds")
    verify = get("VERIFY", "warm", "p95_seconds")
    k3 = get("K3_replay", "warm", "p95_seconds")
    snapshot = get("snapshot_serialization_commit", "warm", "p95_seconds")
    epsilon = float(old["epsilon"])
    commit = k3 + snapshot + epsilon
    warm_min, warm_max = coarse + verify + commit, full
    cold_min = proxy_init + coarse + oracle_init + verify + commit
    cold_max = proxy_init + full
    width = cold_max - cold_min
    old.update({
        "PARTIAL_PROXY_REGIME": "NO_GO" if width <= 0 else "WEAK",
        "statistical_qualification": "PILOT_ONLY_INCOMPLETE_REPETITION_PROTOCOL",
        "gate_workload": "strict_cold_v3_section_6_1",
        "C_p95_proxy_initialization_cold": proxy_init,
        "C_p95_oracle_initialization_cold": oracle_init,
        "C_p95_coarse_warm": coarse,
        "C_p50_full_proxy_warm": full,
        "warm_conditional_T_min": warm_min,
        "warm_conditional_T_max": warm_max,
        "warm_conditional_interval_width": warm_max - warm_min,
        "warm_conditional_normalized_interval_width": (warm_max - warm_min) / warm_max,
        "C_p95_coarse": proxy_init + coarse,
        "C_p95_VERIFY": oracle_init + verify,
        "C_p50_full_proxy": cold_max,
        "T_min": cold_min,
        "T_max": cold_max,
        "interval_width": width,
        "normalized_interval_width": width / cold_max,
        "interpretation": "Cold oracle initialization is counted because v3 section 6.1 defines model initialization as cold workload cost. The positive warm-oracle interval is secondary evidence only.",
    })
    (OUT / "partial_proxy_gate.json").write_text(json.dumps(old, indent=2) + "\n")
    report = f"""# PSVR Stage 0B — Single-Video Physical Regime Pilot

`PARTIAL_PROXY_REGIME = {old['PARTIAL_PROXY_REGIME']}` (observed single-run pilot; not statistically qualified)

## Decisive evidence

- Coarse scan: {coarse:.3f} s warm operator time with global 30-second coverage.
- Full proxy: {full:.3f} s warm operator time for the 5-second YOLO grid plus 2 FPS motion decode.
- Physical VERIFY warm p95: {verify:.3f} s from {old['physical_oracle_calls']} Qwen3-VL-32B calls; cache replay calls: 0.
- Cold initialization: proxy {proxy_init:.3f} s; oracle {oracle_init:.3f} s.
- C_commit: {commit:.3f} s (K3 p95 {k3:.6f} + snapshot p95 {snapshot:.6f} + epsilon {epsilon:.3f}).
- Strict-cold T_min: {cold_min:.3f} s; strict-cold T_max: {cold_max:.3f} s.
- Strict-cold interval width: {width:.3f} s; normalized width: {width/cold_max:.4f}.

## Competing regime

If the oracle is already resident, the conditional interval is [{warm_min:.3f}, {warm_max:.3f}] s, width {warm_max-warm_min:.3f} s. This is evidence for warm oracle scheduling, not for the cold partial-proxy claim.

## Decision

The observed strict-cold interval is negative because loading the frozen 32B oracle ({oracle_init:.3f} s) consumes more than the warm coarse-to-full proxy gap. This strongly points to NO_GO and redirects work toward warm oracle scheduling. However, full coarse/full-proxy and independent cold-start runs have n=1, so the percentile protocol is not complete and the result must not be presented as a statistically qualified gate. Per protocol, Stage 1 physical smoke testing is not entered after observed NO_GO.
"""
    (OUT / "FINAL_REPORT.md").write_text(report)
    print(old["PARTIAL_PROXY_REGIME"])


if __name__ == "__main__":
    main()
