#!/usr/bin/env python3
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from power_common import (
    BOOTSTRAP_REPS,
    CERT_SAMPLE_FRAC,
    MODES,
    NUM_TRIALS,
    POWER_DIR,
    RANDOM_SEED,
    REFERENCE_DELTA,
    REFERENCE_GAMMA,
    TARGET_EVENT_COUNTS,
    append_progress,
    certified_bound_from_values,
    ensure_dirs,
    practical_bootstrap_lcb,
    stratified_bound,
)


def synthesize_population(ref: pd.DataFrame, target_events: int, rng: np.random.Generator) -> pd.DataFrame:
    event_blocks = ref[ref["Y_i_O"] > 0].reset_index(drop=True)
    non_event_blocks = ref[ref["Y_i_O"] <= 0].reset_index(drop=True)
    positive_block_rate = max(1e-6, len(event_blocks) / len(ref))
    chosen = []
    y_total = 0
    while y_total < target_events:
        block = event_blocks.iloc[int(rng.integers(0, len(event_blocks)))].to_dict()
        chosen.append(block)
        y_total += int(block["Y_i_O"])
    target_n = max(len(chosen), int(math.ceil(len(chosen) / positive_block_rate)))
    non_n = max(0, target_n - len(chosen))
    if non_n > 0 and not non_event_blocks.empty:
        idx = rng.integers(0, len(non_event_blocks), size=non_n)
        chosen.extend(non_event_blocks.iloc[idx].to_dict("records"))
    pop = pd.DataFrame(chosen).sample(frac=1.0, random_state=int(rng.integers(0, 2**31 - 1))).reset_index(drop=True)
    pop["synthetic_block_id"] = [f"synth_{i:06d}" for i in range(len(pop))]
    return pop


def sample_srs(pop: pd.DataFrame, rng: np.random.Generator, frac: float = CERT_SAMPLE_FRAC) -> np.ndarray:
    n = max(1, int(math.ceil(len(pop) * frac)))
    return rng.choice(np.arange(len(pop)), size=min(n, len(pop)), replace=False)


def sample_stratified(pop: pd.DataFrame, rng: np.random.Generator, frac: float = CERT_SAMPLE_FRAC) -> np.ndarray:
    pieces = []
    for _, idxs in pop.groupby("video_id").indices.items():
        idxs = np.array(list(idxs), dtype=int)
        n_h = max(1, int(round(len(idxs) * frac)))
        n_h = min(n_h, len(idxs))
        pieces.append(rng.choice(idxs, size=n_h, replace=False))
    if not pieces:
        return sample_srs(pop, rng, frac)
    return np.concatenate(pieces)


def evaluate(pop: pd.DataFrame, idx: np.ndarray, mode: str, rng: np.random.Generator) -> dict:
    y = pop["Y_i_O"].to_numpy(dtype=float)
    m = pop["M_i_O"].to_numpy(dtype=float)
    total_y = float(y.sum())
    total_m = float(m.sum())
    true_recall = 0.0 if total_y <= 0 else 1.0 - total_m / total_y
    if mode == "stratified_by_video":
        cert = stratified_bound(pop, idx, REFERENCE_DELTA, "video_id")
        lcb = cert["LCB_recall_O"]
        y_hat = cert["Y_hat_O"]
        m_hat = cert["M_hat_O"]
        lcb_y = cert["LCB_Y_O"]
        ucb_m = cert["UCB_M_O"]
    elif mode == "bootstrap_diagnostic":
        sample_y = y[idx]
        sample_m = m[idx]
        base = certified_bound_from_values(sample_y, sample_m, len(pop), REFERENCE_DELTA)
        lcb = practical_bootstrap_lcb(sample_y, sample_m, len(pop), rng, BOOTSTRAP_REPS)
        y_hat = base["Y_hat_O"]
        m_hat = base["M_hat_O"]
        lcb_y = base["LCB_Y_O"]
        ucb_m = base["UCB_M_O"]
    else:
        sample_y = y[idx]
        sample_m = m[idx]
        cert = certified_bound_from_values(sample_y, sample_m, len(pop), REFERENCE_DELTA)
        lcb = cert["LCB_recall_O"]
        y_hat = cert["Y_hat_O"]
        m_hat = cert["M_hat_O"]
        lcb_y = cert["LCB_Y_O"]
        ucb_m = cert["UCB_M_O"]
    return {
        "mode": mode,
        "target_gamma": REFERENCE_GAMMA,
        "delta": REFERENCE_DELTA,
        "population_blocks": len(pop),
        "blocks_sampled": len(idx),
        "actual_event_count": total_y,
        "actual_missed_events": total_m,
        "true_recall": true_recall,
        "Y_hat_O": y_hat,
        "M_hat_O": m_hat,
        "LCB_Y_O": lcb_y,
        "UCB_M_O": ucb_m,
        "LCB_recall": lcb,
        "GVR": lcb > true_recall,
        "coverage": lcb <= true_recall,
        "tightness": true_recall - lcb,
        "certificate_success": lcb >= REFERENCE_GAMMA,
        "fraction_vacuous_indicator": lcb <= 1e-12,
        "cost_to_certificate": len(idx),
        "diagnostic_only": mode == "bootstrap_diagnostic",
    }


def main() -> None:
    ensure_dirs()
    ref = pd.read_csv(POWER_DIR / "tables/empirical_reference_blocks.csv")
    rng = np.random.default_rng(RANDOM_SEED)
    out_rows = []
    for target in TARGET_EVENT_COUNTS:
        for trial in range(NUM_TRIALS):
            pop = synthesize_population(ref, target, rng)
            for mode in MODES:
                idx = sample_stratified(pop, rng) if mode == "stratified_by_video" else sample_srs(pop, rng)
                row = evaluate(pop, idx, mode, rng)
                row["target_event_count"] = target
                row["trial"] = trial
                out_rows.append(row)
    results = pd.DataFrame(out_rows)
    results.to_csv(POWER_DIR / "tables/power_scaling_results.csv", index=False)
    append_progress(
        "power scaling simulation",
        "python scripts/20_power_scaling_simulation.py",
        f"wrote {len(results)} rows with num_trials={NUM_TRIALS}",
        next_action="compare modes and generate figures",
    )


if __name__ == "__main__":
    main()
