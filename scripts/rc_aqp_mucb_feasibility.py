"""RC-AQP preflight — M_UCB / RecallLCB feasibility arithmetic.

Read-only feasibility computation over existing repo data only:
  outputs/late_aqp_d3_accounting_fix_v1/segment_info.csv
  outputs/late_aqp_event_diverse_discovery_v1/unique_event_coverage.csv

No oracle, no new discovery run, no model call. Pure arithmetic.

Computes the binomial zero-hit upper bound
    p_ucb(n, alpha) = 1 - alpha ** (1 / n)     (alpha = 0.05)
for audit sample sizes implied by budget ratios 10/20/30% and audit shares
10/20/30%, and translates it into:
  * M_allowed for RecallLCB >= tau_r at discovered event counts D
  * M_ucb = uncovered_units * p_ucb  /  RecallLCB = D / (D + M_ucb)   (unit-level)

Output:
  outputs/rc_aqp_preflight/mucb_feasibility.csv
  outputs/rc_aqp_preflight/mucb_feasibility_summary.md
"""

from __future__ import annotations

import csv
import math
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SEG_INFO = REPO_ROOT / "outputs/late_aqp_d3_accounting_fix_v1/segment_info.csv"
UVC = REPO_ROOT / "outputs/late_aqp_event_diverse_discovery_v1/unique_event_coverage.csv"
OUT_DIR = REPO_ROOT / "outputs/rc_aqp_preflight"

ALPHA = 0.05
BUDGET_RATIOS = (0.10, 0.20, 0.30)
AUDIT_SHARES = (0.10, 0.20, 0.30)
TAU_R_TARGETS = (0.80, 0.90, 0.95)
P_UCB_TARGETS = (0.20, 0.10, 0.05, 0.02)


def p_ucb(n: int, alpha: float = ALPHA) -> float:
    """Binomial zero-hit upper bound: 1 - alpha**(1/n). Returns NaN for n<=0."""
    if n <= 0:
        return float("nan")
    return 1.0 - alpha ** (1.0 / n)


def read_segment_info(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append(
                {
                    "segment_id": row["segment_id"],
                    "num_units": int(row["num_units"]),
                    "num_positive_units": int(row["num_positive_units"]),
                    "num_events": int(row["num_events"]),
                }
            )
    return rows


def read_unique_event_coverage(path: Path) -> dict[str, dict[str, float]]:
    """Return {segment_id: {method: best_unique_events_hit_le30}}."""
    out: dict[str, dict[str, float]] = {}
    if not path.exists():
        return out
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            seg = row["segment_id"]
            method = row["method"]
            val = float(row["best_unique_events_hit_le30"])
            out.setdefault(seg, {})[method] = val
    return out


def n_for_p_ucb(target: float, alpha: float = ALPHA) -> int:
    """Smallest n with p_ucb(n, alpha) <= target."""
    # 1 - alpha**(1/n) <= target  =>  alpha**(1/n) >= 1-target
    # 1/n * ln(alpha) >= ln(1-target)  (ln(alpha)<0)
    # 1/n <= ln(1-target)/ln(alpha)  => n >= ln(alpha)/ln(1-target)
    if target >= 1.0 or target <= 0.0:
        return -1
    return math.ceil(math.log(alpha) / math.log(1.0 - target))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    segs = read_segment_info(SEG_INFO)
    uvc = read_unique_event_coverage(UVC)
    discovered_methods = ["B7-core", "D3-norepair-core-chunk120"]

    csv_path = OUT_DIR / "mucb_feasibility.csv"
    summary_path = OUT_DIR / "mucb_feasibility_summary.md"

    rows: list[dict] = []

    # --- Per-segment feasibility table -------------------------------------
    for seg in segs:
        n_units = seg["num_units"]
        n_pos = seg["num_positive_units"]
        n_events = seg["num_events"]
        for br in BUDGET_RATIOS:
            budget = max(1, int(round(n_units * br)))
            for a in AUDIT_SHARES:
                n_audit = max(1, int(round(budget * a)))
                p = p_ucb(n_audit)
                # uncovered units ~ n_units - units touched by discovery+audit
                # treat as a conservative fraction: uncovered after audit
                uncovered = max(0, n_units - n_audit)
                m_ucb = uncovered * p
                # discovered events from the strongest baselines (le30 budget)
                for m in discovered_methods:
                    d = uvc.get(seg["segment_id"], {}).get(m, float("nan"))
                    if math.isnan(d):
                        recall_lcb = float("nan")
                    else:
                        recall_lcb = d / (d + m_ucb) if (d + m_ucb) > 0 else float("nan")
                    rows.append(
                        {
                            "segment_id": seg["segment_id"],
                            "num_units": n_units,
                            "num_events": n_events,
                            "num_positive_units": n_pos,
                            "budget_ratio": br,
                            "budget_calls": budget,
                            "audit_share": a,
                            "n_audit": n_audit,
                            "p_ucb_0.05": round(p, 6) if not math.isnan(p) else "",
                            "uncovered_units_est": uncovered,
                            "M_ucb_unit": round(m_ucb, 4),
                            "discovery_method": m,
                            "discovered_events_le30": d if not math.isnan(d) else "",
                            "RecallLCB_unit": round(recall_lcb, 6)
                            if not math.isnan(recall_lcb)
                            else "",
                        }
                    )

    with open(csv_path, "w", newline="") as f:
        if rows:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    # --- Unit-agnostic reference table -------------------------------------
    ref_rows = []
    for n in [1, 2, 3, 5, 8, 10, 12, 15, 20, 30, 50, 80, 120, 200, 500]:
        ref_rows.append({"n_audit": n, "p_ucb_0.05": round(p_ucb(n), 6)})

    ref_csv = OUT_DIR / "mucb_unit_agnostic_reference.csv"
    with open(ref_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["n_audit", "p_ucb_0.05"])
        w.writeheader()
        w.writerows(ref_rows)

    # --- Required sample sizes ---------------------------------------------
    req_rows = []
    for t in P_UCB_TARGETS:
        req_rows.append({"p_ucb_target": t, "min_n_audit_0.05": n_for_p_ucb(t)})
    req_csv = OUT_DIR / "mucb_required_n.csv"
    with open(req_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["p_ucb_target", "min_n_audit_0.05"])
        w.writeheader()
        w.writerows(req_rows)

    # --- M_allowed table per segment per tau_r -----------------------------
    m_allowed_rows = []
    for seg in segs:
        for m in discovered_methods:
            d = uvc.get(seg["segment_id"], {}).get(m, float("nan"))
            for tau in TAU_R_TARGETS:
                if not math.isnan(d) and d > 0 and tau < 1.0:
                    m_allowed = d * (1.0 / tau - 1.0)
                else:
                    m_allowed = float("nan")
                m_allowed_rows.append(
                    {
                        "segment_id": seg["segment_id"],
                        "discovery_method": m,
                        "discovered_events_le30": d if not math.isnan(d) else "",
                        "tau_r": tau,
                        "M_allowed_for_RecallLCB_ge_tau": round(m_allowed, 4)
                        if not math.isnan(m_allowed)
                        else "",
                    }
                )
    ma_csv = OUT_DIR / "m_allowed_table.csv"
    with open(ma_csv, "w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "segment_id",
                "discovery_method",
                "discovered_events_le30",
                "tau_r",
                "M_allowed_for_RecallLCB_ge_tau",
            ],
        )
        w.writeheader()
        w.writerows(m_allowed_rows)

    # --- Markdown summary ---------------------------------------------------
    lines: list[str] = []
    lines.append("# RC-AQP Preflight — M_UCB / RecallLCB feasibility summary\n")
    lines.append(
        "Binomial zero-hit upper bound `p_ucb(n, alpha) = 1 - alpha**(1/n)` with alpha=0.05. "
        "All counts are *oracle-relative* and computed from existing CSV artifacts only; "
        "no oracle / model / new discovery was run.\n"
    )
    lines.append("## Inputs\n")
    lines.append(f"- segment info: `{SEG_INFO.relative_to(REPO_ROOT)}`")
    lines.append(f"- discovered events (le30 budget): `{UVC.relative_to(REPO_ROOT)}`\n")
    seg_lines = ["| segment_id | num_units | num_positive_units | num_events |", "|---|---:|---:|---:|"]
    for s in segs:
        seg_lines.append(
            f"| {s['segment_id']} | {s['num_units']} | {s['num_positive_units']} | {s['num_events']} |"
        )
    lines.extend(seg_lines)
    lines.append("")
    lines.append("## 1. p_ucb reference vs n_audit (alpha=0.05)\n")
    lines.append("| n_audit | p_ucb |")
    lines.append("|---:|---:|")
    for r in ref_rows:
        lines.append(f"| {r['n_audit']} | {r['p_ucb_0.05']} |")
    lines.append("")
    lines.append("## 2. Min n_audit to obtain p_ucb <= target (alpha=0.05)\n")
    lines.append("| p_ucb_target | min_n_audit |")
    lines.append("|---:|---:|")
    for r in req_rows:
        lines.append(f"| {r['p_ucb_target']} | {r['min_n_audit_0.05']} |")
    lines.append("")
    lines.append("## 3. M_allowed for RecallLCB >= tau_r (per discovered-event count)\n")
    lines.append(
        "M_allowed = D * (1/tau_r - 1). RecallLCB=D/(D+M_ucb) >= tau_r requires M_ucb <= M_allowed.\n"
    )
    lines.append("| segment_id | discovery_method | discovered_events_le30 | tau_r | M_allowed |")
    lines.append("|---|---|---:|---:|---:|")
    for r in m_allowed_rows:
        d = r["discovered_events_le30"]
        ma = r["M_allowed_for_RecallLCB_ge_tau"]
        lines.append(
            f"| {r['segment_id']} | {r['discovery_method']} | {d} | {r['tau_r']} | {ma} |"
        )
    lines.append("")
    lines.append("## 4. Headline per-segment feasibility (unit-level RecallLCB)\n")
    lines.append(
        "Uncovered units are conservatively estimated as `num_units - n_audit` (no discovery coverage subtracted); "
        "M_ucb_unit = uncovered_units * p_ucb; RecallLCB_unit = D/(D+M_ucb_unit) using `B7-core` D (le 30 budget).\n"
    )
    lines.append(
        "| segment_id | num_units | budget_ratio | budget_calls | audit_share | n_audit | p_ucb | M_ucb_unit | D_B7 | RecallLCB_unit |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for seg in segs:
        for br in BUDGET_RATIOS:
            budget = max(1, int(round(seg["num_units"] * br)))
            # report the 20% audit share row only to keep the table compact
            a = 0.20
            n_audit = max(1, int(round(budget * a)))
            p = p_ucb(n_audit)
            uncovered = max(0, seg["num_units"] - n_audit)
            m_ucb = uncovered * p
            d = uvc.get(seg["segment_id"], {}).get("B7-core", float("nan"))
            rcb = d / (d + m_ucb) if (not math.isnan(d) and d + m_ucb > 0) else float("nan")
            lines.append(
                f"| {seg['segment_id']} | {seg['num_units']} | {br:.2f} | {budget} | {a:.2f} | "
                f"{n_audit} | {p:.4f} | {m_ucb:.2f} | {d if not math.isnan(d) else ''} | "
                f"{rcb if not math.isnan(rcb) else ''} |"
            )
    lines.append("")
    lines.append("## 5. Caveats\n")
    lines.append(
        "- Uncovered-unit count is a *loose* upper estimate; no discovery coverage is subtracted, "
        "so M_ucb_unit is an *upper* upper bound. Tightening requires the per-call query ledger."
    )
    lines.append(
        "- Per-segment oracle event counts are ~6-20 and audit_n at low budget is often <=15; "
        "per-segment safe stopping at tau_r>=0.9 is statistically weak (p_ucb(15)=0.181, "
        "p_ucb(10)=0.259). Pooling across the 6 segments raises n_audit by ~6x but breaks the "
        "per-segment claim."
    )
    lines.append(
        "- The legacy `strategy7_certificate_power_v1` audit already validated the exact "
        "hypergeometric bound coverage (1.0 >= 0.95 nominal) and found R_lower too conservative "
        "(0.02-0.08 vs true recall 0.19-0.50) on these videos. That is a direct precedent for "
        "'residual uncertainty reporting' but not for 'safe stopping certificate'."
    )
    lines.append(
        "- All discovered-event counts are `posthoc_eval` oracle-relative (B7-core uses event_id "
        "in selection); only D3-norepair-core is `strict_replay`. RC-AQP would need to re-discover "
        "its own candidate set, not inherit B7-core's D."
    )

    summary_path.write_text("\n".join(lines) + "\n")
    print(f"wrote {csv_path.relative_to(REPO_ROOT)}")
    print(f"wrote {ref_csv.relative_to(REPO_ROOT)}")
    print(f"wrote {req_csv.relative_to(REPO_ROOT)}")
    print(f"wrote {ma_csv.relative_to(REPO_ROOT)}")
    print(f"wrote {summary_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()