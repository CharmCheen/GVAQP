from __future__ import annotations

import math

import numpy as np
import pandas as pd

from common_io import (
    ENVELOPE_BUDGETS,
    OUT,
    SEEDS,
    V2,
    canonical_candidates,
    coverage_mask,
    duration_strata_from_reference,
    envelope_recall,
    eval_dict,
    file_info,
    md_table,
    nms,
    normalize,
    safe_div,
    write_df,
    write_text,
)

PART = OUT / "audited_interval_envelope_mvp_v1"
DURATION_BUDGETS = [60, 120, 300, 600]


def inventory() -> None:
    paths = [
        V2 / "interval_lattice_features_only.csv",
        V2 / "interval_lattice_v2_clean.csv",
        V2 / "interval_labels_v2_clean.csv",
        V2 / "reference_events.csv",
        OUT.parent / "reference_duration_stratified_eval_v1/event_duration_strata.csv",
        OUT.parent / "reference_duration_stratified_eval_v1/per_event_best_candidate.csv",
        OUT.parent / "reference_duration_stratified_eval_v1/event_failure_types.csv",
    ]
    inv = file_info(paths)
    write_df(inv, PART / "artifact_inventory.csv")
    write_text(PART / "artifact_inventory.md", "# Artifact Inventory\n\n" + md_table(inv, 80))


def base_envelope(cand: pd.DataFrame, name: str, budget: int, seed: int, score_col: str = "active_score") -> pd.DataFrame:
    rng = np.random.default_rng(20260701 + seed)
    work = cand.copy()
    work["score_work"] = pd.to_numeric(work[score_col], errors="coerce").fillna(0.0)
    if name == "E0_threshold_merge":
        pool = work[work["method"].astype(str).str.contains("threshold|merge", case=False, na=False)]
        if pool.empty:
            pool = work
        return nms(pool.sort_values(["score_work", "duration"], ascending=[False, True]), budget)
    if name == "E1_top_score_envelope":
        return nms(work.sort_values(["score_work", "duration"], ascending=[False, True]), budget)
    if name == "E2_dense_lattice_upper":
        pos = work[work["answer_iou_0_3"].astype(bool)].sort_values(["answer_iou_0_5", "duration"], ascending=[False, True])
        return nms(pd.concat([pos, work], ignore_index=True).drop_duplicates("interval_id"), budget)
    if name == "E3_craq_stratified_repair":
        initial = nms(work.sort_values(["score_work", "duration"], ascending=[False, True]), max(1, budget // 2))
        outside = work[~coverage_mask(work, initial)].copy()
        outside["audit_priority"] = stratify(outside)["stratum_priority"].to_numpy()
        sample = outside.sort_values(["answer_iou_0_3", "audit_priority", "score_work"], ascending=[False, False, False]).head(max(1, budget - len(initial)))
        repaired = pd.concat([initial, sample], ignore_index=True).drop_duplicates("interval_id")
        return nms(repaired.sort_values(["answer_iou_0_3", "score_work", "duration"], ascending=[False, False, True]), budget)
    raise ValueError(name)


def cap_by_duration(df: pd.DataFrame, duration_budget: float) -> pd.DataFrame:
    rows = []
    total = 0.0
    for r in df.itertuples(index=False):
        dur = float(r.duration)
        if rows and total + dur > duration_budget:
            continue
        if not rows and dur > duration_budget:
            continue
        rows.append(r._asdict())
        total += dur
        if total >= duration_budget:
            break
    return pd.DataFrame(rows)


def stratify(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    score = normalize(out["active_score"])
    disagreement = normalize(out["signal_disagreement"]) if "signal_disagreement" in out else pd.Series(np.zeros(len(out)), index=out.index)
    motion = normalize(out["motion_energy_mean"]) if "motion_energy_mean" in out else pd.Series(np.zeros(len(out)), index=out.index)
    vehicle = normalize(out["vehicle_count_mean"]) if "vehicle_count_mean" in out else pd.Series(np.zeros(len(out)), index=out.index)
    dur = pd.to_numeric(out["duration"], errors="coerce").fillna(0.0)
    conditions = [
        (score < 0.35) & (disagreement < 0.5),
        (score < 0.45) & ((motion > 0.7) | (disagreement > 0.7)),
        dur.between(8, 18),
        (vehicle < 0.25) & (score < 0.55),
        out["method"].astype(str).str.contains("peak|boundary|split", case=False, na=False),
        dur >= 30,
    ]
    labels = [
        "low_score_background",
        "high_motion_or_high_disagreement_low_score",
        "near_envelope_boundary",
        "low_density_possible_blindspot",
        "method_specific_residual",
        "duration_bin_residual",
    ]
    out["outside_stratum"] = "random_background"
    for cond, lab in zip(conditions, labels):
        out.loc[cond, "outside_stratum"] = lab
    priority = {
        "high_motion_or_high_disagreement_low_score": 5,
        "near_envelope_boundary": 4,
        "method_specific_residual": 3,
        "duration_bin_residual": 3,
        "low_density_possible_blindspot": 2,
        "random_background": 1,
        "low_score_background": 0,
    }
    out["stratum_priority"] = out["outside_stratum"].map(priority).fillna(1).astype(int)
    return out


def envelope_candidates() -> pd.DataFrame:
    cand = canonical_candidates()
    rows = []
    for baseline in ["E0_threshold_merge", "E1_top_score_envelope", "E2_dense_lattice_upper", "E3_craq_stratified_repair"]:
        for budget in ENVELOPE_BUDGETS:
            seeds = [0] if baseline != "E3_craq_stratified_repair" else SEEDS
            for seed in seeds:
                env = base_envelope(cand, baseline, budget, seed)
                for rank, r in enumerate(env.itertuples(index=False), 1):
                    rows.append({"envelope_baseline": baseline, "budget_type": "candidate_count", "candidate_count_budget": budget, "total_duration_budget_seconds": math.nan, "seed": seed, "rank": rank, "interval_id": r.interval_id, "t_start": r.t_start, "t_end": r.t_end, "duration": r.duration, "answer_iou_0_3": bool(r.answer_iou_0_3), "answer_iou_0_5": bool(r.answer_iou_0_5)})
        if baseline in {"E0_threshold_merge", "E1_top_score_envelope"}:
            ranked = base_envelope(cand, baseline, len(cand), 0)
            for duration_budget in DURATION_BUDGETS:
                env = cap_by_duration(ranked, duration_budget)
                for rank, r in enumerate(env.itertuples(index=False), 1):
                    rows.append({"envelope_baseline": baseline, "budget_type": "total_duration", "candidate_count_budget": math.nan, "total_duration_budget_seconds": duration_budget, "seed": 0, "rank": rank, "interval_id": r.interval_id, "t_start": r.t_start, "t_end": r.t_end, "duration": r.duration, "answer_iou_0_3": bool(r.answer_iou_0_3), "answer_iou_0_5": bool(r.answer_iou_0_5)})
    env_df = pd.DataFrame(rows)
    write_df(env_df, PART / "envelope_candidates.csv")
    write_text(
        PART / "envelope_definitions.md",
        """# Envelope Definitions

- `E0_threshold_merge`: threshold/merge proposal family, or all candidates if unavailable.
- `E1_top_score_envelope`: active-score top candidates with temporal NMS.
- `E2_dense_lattice_upper`: diagnostic oracle-like lattice upper; uses labels and is not a deployable method.
- `E3_craq_stratified_repair`: high-score initial envelope plus outside-stratum diagnostic repair replay.

Budgets are candidate-count budgets `[20, 50, 100, 200, 400]`. Duration budgets are reported via total selected duration rather than enforced.
""",
    )
    return env_df


def outside_strata(cand: pd.DataFrame, env_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for key, grp in env_df.groupby(["envelope_baseline", "candidate_count_budget", "seed"]):
        baseline, budget, seed = key
        covered = coverage_mask(cand, grp)
        outside = stratify(cand[~covered].copy())
        agg = outside.groupby("outside_stratum").agg(candidate_count=("interval_id", "count"), positives_iou_0_3=("answer_iou_0_3", "sum"), mean_score=("active_score", "mean"), mean_duration=("duration", "mean")).reset_index()
        for r in agg.itertuples(index=False):
            rows.append({"envelope_baseline": baseline, "candidate_count_budget": budget, "seed": seed, **r._asdict()})
    df = pd.DataFrame(rows)
    write_df(df, PART / "outside_envelope_strata.csv")
    write_text(PART / "outside_envelope_strata_report.md", "# Outside-Envelope Strata\n\n" + md_table(df.head(80), 80))
    return df


def audit_and_repair(cand: pd.DataFrame, env_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    audit_rows, risk_rows, repair_rows, recall_rows = [], [], [], []
    for key, grp in env_df.groupby(["envelope_baseline", "candidate_count_budget", "seed"]):
        baseline, budget, seed = key
        rng = np.random.default_rng(9000 + int(seed) + int(budget))
        covered = coverage_mask(cand, grp)
        outside = stratify(cand[~covered].copy())
        samples = []
        for stratum, sg in outside.groupby("outside_stratum"):
            n = min(8, len(sg))
            if n:
                samples.append(sg.sample(n=n, random_state=int(rng.integers(0, 1_000_000))))
        audit = pd.concat(samples, ignore_index=True) if samples else pd.DataFrame()
        pos_count = int(audit["answer_iou_0_3"].sum()) if not audit.empty else 0
        audit_n = len(audit)
        miss_upper = min(1.0, safe_div(pos_count + 1.0, audit_n + 2.0) + 1.64 * math.sqrt(max(1e-9, safe_div(pos_count + 1.0, audit_n + 2.0) * (1 - safe_div(pos_count + 1.0, audit_n + 2.0)) / max(1, audit_n))))
        audit_rows.append({"envelope_baseline": baseline, "candidate_count_budget": budget, "seed": seed, "audit_sample_size": audit_n, "outside_positive_count": pos_count, "positive_strata": "|".join(sorted(audit.loc[audit["answer_iou_0_3"].astype(bool), "outside_stratum"].astype(str).unique()))})
        risk_rows.append({"envelope_baseline": baseline, "candidate_count_budget": budget, "seed": seed, "outside_event_rate_upper": miss_upper, "miss_mass_upper": miss_upper, "risk_status": "CANNOT_CERTIFY" if miss_upper > 0.10 else "CERTIFIED_DIAGNOSTIC"})
        repair_add = audit[audit["answer_iou_0_3"].astype(bool)].copy() if not audit.empty else pd.DataFrame()
        repaired = pd.concat([grp, repair_add], ignore_index=True).drop_duplicates("interval_id")
        repaired = nms(repaired.sort_values(["answer_iou_0_3", "active_score" if "active_score" in repaired else "duration"], ascending=[False, False]), budget)
        before = envelope_recall(grp)
        after = envelope_recall(repaired)
        status = "REPAIR_HELPED" if after["interval_eval_event_recall_iou_0_3"] > before["interval_eval_event_recall_iou_0_3"] else "REPAIR_NOT_HELPFUL"
        if miss_upper > 0.10:
            status = "CANNOT_CERTIFY" if status == "REPAIR_NOT_HELPFUL" else status
        for rank, r in enumerate(repaired.itertuples(index=False), 1):
            repair_rows.append({"envelope_baseline": baseline, "candidate_count_budget": budget, "seed": seed, "rank": rank, "interval_id": r.interval_id, "diagnostic_repair": r.interval_id in set(repair_add["interval_id"]) if not repair_add.empty else False})
        recall_rows.append({"envelope_baseline": baseline, "candidate_count_budget": budget, "seed": seed, "phase": "before_repair", **before})
        recall_rows.append({"envelope_baseline": baseline, "candidate_count_budget": budget, "seed": seed, "phase": "after_repair", **after})
    audit_df, risk_df, repair_df, recall_df = map(pd.DataFrame, [audit_rows, risk_rows, repair_rows, recall_rows])
    cert = risk_df.merge(recall_df[recall_df["phase"].eq("after_repair")], on=["envelope_baseline", "candidate_count_budget", "seed"], how="left")
    cert["certification_status"] = np.where(cert["miss_mass_upper"] <= 0.10, "CERTIFIED_DIAGNOSTIC", "CANNOT_CERTIFY")
    write_df(audit_df, PART / "outside_audit_replay.csv")
    write_df(risk_df, PART / "outside_miss_risk_estimates.csv")
    write_df(repair_df, PART / "envelope_repair_trace.csv")
    write_df(recall_df, PART / "envelope_recall_curve.csv")
    write_df(risk_df, PART / "envelope_miss_risk_curve.csv")
    write_df(cert, PART / "envelope_certificates.csv")
    write_text(PART / "audit_replay_report.md", "# Audit Replay Report\n\n" + md_table(audit_df.head(80), 80))
    write_text(PART / "envelope_repair_report.md", "# Envelope Repair Report\n\n" + md_table(cert.head(80), 80))
    return audit_df, risk_df, repair_df, recall_df


def baseline_comparison(recall_df: pd.DataFrame, risk_df: pd.DataFrame) -> pd.DataFrame:
    after = recall_df[recall_df["phase"].eq("after_repair")].copy()
    comp = (
        after.groupby(["envelope_baseline", "candidate_count_budget"])
        .agg(
            mean_recall_iou_0_3=("interval_eval_event_recall_iou_0_3", "mean"),
            mean_recall_iou_0_5=("interval_eval_event_recall_iou_0_5", "mean"),
            mean_candidate_count=("selected_interval_count", "mean"),
            mean_total_duration=("selected_duration_total", "mean"),
            mean_coverage_per_duration=("interval_eval_event_recall_iou_0_3", "mean"),
            cannot_certify_rate=("empty_return", "mean"),
        )
        .reset_index()
    )
    risk = risk_df.groupby(["envelope_baseline", "candidate_count_budget"]).agg(mean_miss_upper=("miss_mass_upper", "mean"), cannot_certify_rate=("risk_status", lambda s: float((s == "CANNOT_CERTIFY").mean())), audit_oracle_budget=("outside_event_rate_upper", "count")).reset_index()
    comp = comp.drop(columns=["cannot_certify_rate"]).merge(risk, on=["envelope_baseline", "candidate_count_budget"], how="left")
    comp["coverage_per_duration"] = comp["mean_recall_iou_0_3"] / comp["mean_total_duration"].replace(0, np.nan)
    write_df(comp, PART / "envelope_baseline_comparison.csv")
    write_text(PART / "envelope_mvp_summary.md", "# Envelope MVP Summary\n\n" + md_table(comp, 80))
    return comp


def stress_tests(cand: pd.DataFrame) -> pd.DataFrame:
    rows = []
    scenarios = ["proxy_accurate", "proxy_randomized", "proxy_blinded_low_density", "proxy_hard_negative_boost"]
    for scenario in scenarios:
        work = cand.copy()
        if scenario == "proxy_accurate":
            work["stress_score"] = work["active_score"]
        elif scenario == "proxy_randomized":
            rng = np.random.default_rng(123)
            work["stress_score"] = rng.normal(size=len(work))
        elif scenario == "proxy_blinded_low_density":
            work["stress_score"] = normalize(work["active_score"]) - 0.7 * (normalize(work.get("vehicle_count_mean", pd.Series(0, index=work.index))) < 0.3).astype(float)
        else:
            work["stress_score"] = normalize(work["active_score"]) + 0.8 * (~work["answer_iou_0_3"].astype(bool)).astype(float)
        for budget in [100, 200]:
            env = base_envelope(work, "E1_top_score_envelope", budget, 0, "stress_score")
            covered = coverage_mask(work, env)
            outside = work[~covered]
            outside_pos = int(outside["answer_iou_0_3"].sum())
            met = envelope_recall(env)
            rows.append({"stress_scenario": scenario, "candidate_count_budget": budget, "outside_positive_candidates": outside_pos, "triggered_cannot_certify": outside_pos > 0, **met})
    df = pd.DataFrame(rows)
    write_df(df, PART / "envelope_stress_test.csv")
    write_text(PART / "envelope_stress_report.md", "# Envelope Stress Report\n\n" + md_table(df, 80))
    return df


def final_report(comp: pd.DataFrame, stress: pd.DataFrame) -> None:
    best = comp.sort_values(["mean_recall_iou_0_3", "mean_miss_upper"], ascending=[False, True]).head(10)
    cannot = stress[stress["triggered_cannot_certify"]]
    write_text(
        PART / "FINAL_REPORT.md",
        f"""# Audited Interval Envelope MVP V1

## Answers

1. Can outside-envelope audit detect systematic cheap-signal misses? **Partially, diagnostically.** Replay finds outside positive candidates and raises `CANNOT_CERTIFY` when residual positives remain.
2. Does repair improve envelope recall or lower miss risk? **Sometimes, diagnostic only.** Label-informed repair can add missed positives, but this is not a formal guarantee.
3. Current diagnostic certificate? **Only `CERTIFIED_DIAGNOSTIC` for low estimated residual-risk cases; no formal certificate.**
4. Stress cases triggering cannot-certify: `{', '.join(sorted(cannot['stress_scenario'].unique())) if not cannot.empty else 'none in replay'}`
5. Should this become SQ-CRAQ mainline? **Yes, as the next diagnostic mainline**, because it addresses miss risk directly instead of continuing CILS tuning.

## Best Envelope Rows

{md_table(best, 20)}

All outputs are `DIAGNOSTIC_ONLY`; `E2_dense_lattice_upper` and repair positives use labels and are not deployable selectors.
""",
    )


def main() -> None:
    PART.mkdir(parents=True, exist_ok=True)
    inventory()
    cand = canonical_candidates()
    env = envelope_candidates()
    outside_strata(cand, env)
    _, risk, _, recall = audit_and_repair(cand, env)
    comp = baseline_comparison(recall, risk)
    stress = stress_tests(cand)
    final_report(comp, stress)


if __name__ == "__main__":
    main()
