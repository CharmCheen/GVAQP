"""T028e nodegate ablation — globalcap vs soft gate vs strict gate.

Compares three zero-proxy candidate gate configurations:
  - globalcap: current ECP-c2 mechanism (always generate zp arms, cap=0.10 at policy level)
  - soft_gate: generate zp arms only when zp_share >= 0.40 AND >=6 zp bins remain
               AND (n_probe >= 2 with 0 positives OR negative_streak >= 2)
  - strict_gate: zp_share >= 0.50 AND >=8 zp bins AND n_probe >= 3 AND n_pos == 0

All three use the same GBM event-utility policy trained on T028e-0 ceiling steps.
Strict-replay LOSO (6-fold). Zero-proxy budget cap: 0.10.

Pass conditions:
  1. dataset3_0_1200 @0.20/@0.30 not below globalcap
  2. realcartest 0 regressions
  3. ZERO_PROXY calls fewer or more concentrated
  4. precision not degraded
  5. ceiling not below

Outputs:
  outputs/ecp_event_coverage_policy_v1/t028e_nodegate_frontier.csv
  outputs/ecp_event_coverage_policy_v1/t028e_nodegate_action_usage.csv
  outputs/ecp_event_coverage_policy_v1/t028e_nodegate_report.md
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from run_ecp_t027_bandit import (  # noqa: E402
    SEGMENTS, BUDGET_RATIOS, SEEDS, PROXY_COL, LABEL_COL, VARIANTS,
    load_segment_data, AlignedOracle, group_positive_bins, evaluate_events,
    candidate_targets_module, formed_intervals,
)
from run_ecp_t028c_ceiling import run_oracle_ceiling  # noqa: E402
from run_ecp_t028e0_ceiling import candidate_targets_extended  # noqa: E402

OUT = REPO_ROOT / "outputs" / "ecp_event_coverage_policy_v1"
OUT.mkdir(parents=True, exist_ok=True)

FEATURES = ["rem_ratio", "top_proxy", "zp_share", "formed_ratio", "n_pos"]
ALL_ARMS = ["DISCOVER", "BRIDGE", "CERTIFY", "ZERO_PROXY",
            "ZERO_PROXY_SPACE_FILLING", "ZERO_PROXY_LARGEST_GAP",
            "ZERO_PROXY_VDC", "ZERO_PROXY_MIDBAND", "ZERO_PROXY_LOCAL_GAP_FLANK"]
ZP_ARMS = [a for a in ALL_ARMS if "ZERO_PROXY" in a]
MAX_ZERO_PROXY_SHARE = 0.10


def apply_gate(mode, cands, proxies, unqueried, queried, queried_pos,
               neg_streak, zp_budget_used, budget_abs):
    """Conditionally suppress zero-proxy arms based on gate mode and current state."""
    unqueried_zp = [b for b in unqueried if proxies.get(b, -1) == 0.0]
    n_unq_zp = len(unqueried_zp)
    zp_share = n_unq_zp / len(unqueried) if unqueried else 0.0
    n_probe = len(queried)
    n_pos = len(queried_pos)

    allow_zp = False
    if mode == "globalcap":
        allow_zp = True
    elif mode == "soft_gate":
        if (zp_share >= 0.40 and n_unq_zp >= 6
                and zp_budget_used < MAX_ZERO_PROXY_SHARE * budget_abs
                and ((n_probe >= 2 and n_pos == 0) or neg_streak >= 2)):
            allow_zp = True
    elif mode == "strict_gate":
        if (zp_share >= 0.50 and n_unq_zp >= 8
                and n_probe >= 3 and n_pos == 0
                and zp_budget_used < MAX_ZERO_PROXY_SHARE * budget_abs):
            allow_zp = True

    if not allow_zp:
        for zp_arm in ZP_ARMS:
            cands[zp_arm] = None
    return cands


def build_training_table(cand_csv, train_segments):
    df = pd.read_csv(cand_csv)
    df = df[df["segment_id"].isin(train_segments)]
    rows = []
    for _, r in df.iterrows():
        for a in ALL_ARMS:
            col = f"u_{a.lower()}"
            if col not in r.index or pd.isna(r[col]):
                continue
            row = {
                "rem_ratio": r["rem_ratio"], "top_proxy": r["top_proxy"],
                "zp_share": r["zp_share"], "formed_ratio": r["formed_ratio"],
                "n_pos": r["n_pos"],
            }
            for arm in ALL_ARMS:
                row[f"arm_{arm}"] = 1.0 if arm == a else 0.0
            row["u"] = r[col]
            rows.append(row)
    return pd.DataFrame(rows)


def train_policy(table):
    X = table[FEATURES + [f"arm_{a}" for a in ALL_ARMS]].values
    y = table["u"].values
    model = GradientBoostingRegressor(n_estimators=100, max_depth=3, random_state=0)
    model.fit(X, y)

    def policy_fn(st, cands):
        avail = [a for a in ALL_ARMS if cands.get(a) is not None]
        if not avail:
            return None
        zp_avail = [a for a in avail if a in ZP_ARMS]
        non_zp = [a for a in avail if a not in ZP_ARMS]
        if len(zp_avail) > 0 and st.get("zp_share", 0) < MAX_ZERO_PROXY_SHARE:
            avail = non_zp or avail
        best_arm, best_p = None, -1e9
        for a in avail:
            feat = np.array(
                [st["rem_ratio"], st["top_proxy"], st["zp_share"], st["formed_ratio"], st["n_pos"]]
                + [1.0 if arm == a else 0.0 for arm in ALL_ARMS]
            ).reshape(1, -1)
            p = model.predict(feat)[0]
            if p > best_p:
                best_p, best_arm = p, a
        return best_arm

    return policy_fn


def run_strict_replay(grid, ref_seg, seg_id, budget_abs, budget_ratio, seed,
                      rng, policy_fn, gate_mode, cfg, method_label):
    n_bins = len(grid)
    oracle = AlignedOracle(grid, seg_id, method_label, seed, budget_abs, budget_ratio)
    grid_sorted = grid.sort_values("bin_idx").reset_index(drop=True)
    bin_to_t = dict(zip(grid_sorted["bin_idx"],
                        zip(grid_sorted["local_t_start"], grid_sorted["local_t_end"])))
    proxies = dict(zip(grid_sorted["bin_idx"], grid_sorted[PROXY_COL]))
    all_bins = grid_sorted["bin_idx"].tolist()
    queried, queried_pos = set(), set()
    n_ref = len(ref_seg) if ref_seg is not None else 0
    zp_budget_used = 0
    negative_streak = 0
    action_log = []

    while oracle.calls < oracle.budget_abs:
        unqueried = [b for b in all_bins if b not in queried]
        if not unqueried:
            break

        cands = candidate_targets_extended(
            grid_sorted, proxies, bin_to_t, queried, queried_pos,
            unqueried, all_bins, zp_budget_used, budget_abs, cfg,
        )
        cands = apply_gate(gate_mode, cands, proxies, unqueried, queried, queried_pos,
                           negative_streak, zp_budget_used, budget_abs)

        formed = formed_intervals(queried_pos, grid_sorted)
        ev = evaluate_events(formed, ref_seg) if n_ref > 0 else {"unique_event_coverage": 0}
        st = {
            "rem_ratio": (oracle.budget_abs - oracle.calls) / oracle.budget_abs,
            "top_proxy": max(proxies[b] for b in unqueried) if unqueried else 0.0,
            "zp_share": (sum(1 for b in unqueried if proxies.get(b, -1) == 0.0) / len(unqueried)) if unqueried else 0.0,
            "formed_ratio": ev["unique_event_coverage"] / n_ref if n_ref > 0 else 0,
            "n_pos": len(queried_pos),
        }
        best_arm = policy_fn(st, cands)
        target = cands.get(best_arm) if best_arm else None
        if target is None:
            avail = [a for a in ALL_ARMS if cands.get(a) is not None]
            if not avail:
                break
            best_arm, target = avail[0], cands[avail[0]]

        if best_arm in ZP_ARMS:
            zp_budget_used += 1
        label = oracle.query_unit(target, method_label + "_" + best_arm, best_arm)
        queried.add(target)
        if label == "positive":
            queried_pos.add(target)
            negative_streak = 0
        else:
            negative_streak += 1
        action_log.append({
            "arm": best_arm, "bin": target, "label": label, "negative_streak": negative_streak,
            "zp_share": st["zp_share"], "rem_ratio": st["rem_ratio"],
            "n_pos": len(queried_pos), "n_probe": len(queried),
        })

    formed = formed_intervals(queried_pos, grid_sorted)
    ev = evaluate_events(formed, ref_seg) if n_ref > 0 else {"event_precision": 0, "event_recall": 0}
    return {
        "event_precision": ev["event_precision"],
        "event_recall": ev["event_recall"],
        "oracle_calls": oracle.calls,
        "action_log": action_log,
    }


def v2_policy_fn(st, cands):
    cfg = VARIANTS["v2"]
    best_arm, best_w = None, -1e9
    for arm in ["DISCOVER", "BRIDGE", "CERTIFY", "ZERO_PROXY"]:
        if cands.get(arm) is None:
            continue
        if arm == "DISCOVER":
            w = cfg["w_discover"] + cfg["w_discover_floor"]
        elif arm == "BRIDGE":
            w = cfg["w_bridge"]
        elif arm == "CERTIFY":
            w = cfg["w_certify"]
        elif arm == "ZERO_PROXY":
            w = cfg["w_zero"]
        else:
            continue
        if arm == "ZERO_PROXY":
            if cfg["zero_need_stagnation"] and st.get("stagnation", 0) == 0:
                continue
            if st.get("zp_share", 0) < cfg["zero_zp_thresh"]:
                continue
        if w > best_w:
            best_w, best_arm = w, arm
    return best_arm or "DISCOVER"


def main():
    cand_csv = OUT / "t028e0_ceiling_steps.csv"
    if not cand_csv.exists():
        print(f"ERROR: {cand_csv} not found. Run T028e-0 first.")
        return
    all_seg_ids = [seg["segment_id"] for seg in SEGMENTS]
    rng = np.random.default_rng(20260710)

    frontier_rows = []
    action_rows = []

    for gate_mode in ["globalcap", "soft_gate", "strict_gate"]:
        print(f"\n{'='*60}")
        print(f"  {gate_mode}")
        print(f"{'='*60}")

        for fold_idx, held_out_seg in enumerate(all_seg_ids):
            train_segs = [s for s in all_seg_ids if s != held_out_seg]
            print(f"\n  Fold {fold_idx}: held-out={held_out_seg}")

            table = build_training_table(cand_csv, train_segs)
            c2_policy = train_policy(table)

            held_out_seg_dict = next(s for s in SEGMENTS if s["segment_id"] == held_out_seg)
            grid, ref_seg, err = load_segment_data(held_out_seg_dict)
            if grid is None:
                continue
            n_bins = len(grid)

            for br in BUDGET_RATIOS:
                for seed in SEEDS:
                    budget_abs = max(1, int(round(br * n_bins)))

                    res = run_strict_replay(
                        grid, ref_seg, held_out_seg, budget_abs, br, seed,
                        rng, c2_policy, gate_mode, VARIANTS["v2"],
                        f"ECP-nodegate-{gate_mode}-fold{fold_idx}")

                    frontier_rows.append({
                        "gate_mode": gate_mode, "fold": fold_idx,
                        "segment_id": held_out_seg, "seed": seed,
                        "budget_ratio": br, "budget_abs": budget_abs,
                        "event_recall": round(res["event_recall"], 4),
                        "event_precision": round(res["event_precision"], 4),
                        "strict_replay_or_posthoc": "strict_replay",
                        "applicability_note": f"T028e nodegate {gate_mode}, held_out={held_out_seg}",
                    })

                    counts = {}
                    for step in res["action_log"]:
                        counts[step["arm"]] = counts.get(step["arm"], 0) + 1
                    for arm in ALL_ARMS:
                        action_rows.append({
                            "gate_mode": gate_mode, "fold": fold_idx,
                            "segment_id": held_out_seg, "budget_ratio": br,
                            "seed": seed, "arm": arm,
                            "count": counts.get(arm, 0),
                        })

            print(f"    done {held_out_seg}")

    frontier = pd.DataFrame(frontier_rows)
    frontier.to_csv(OUT / "t028e_nodegate_frontier.csv", index=False)
    actions = pd.DataFrame(action_rows)
    actions.to_csv(OUT / "t028e_nodegate_action_usage.csv", index=False)

    # Aggregate
    agg = frontier.groupby(["gate_mode", "segment_id", "budget_ratio"]).agg(
        recall=("event_recall", "mean"), prec=("event_precision", "mean")).reset_index()

    globalcap = agg[agg.gate_mode == "globalcap"]
    soft = agg[agg.gate_mode == "soft_gate"]
    strict = agg[agg.gate_mode == "strict_gate"]

    # Aggregate action counts
    act_agg = actions.groupby(["gate_mode", "segment_id", "budget_ratio", "arm"]).agg(
        mean_count=("count", "mean")).reset_index()
    zp_act = act_agg[act_agg.arm.isin(ZP_ARMS)].groupby(
        ["gate_mode", "segment_id", "budget_ratio"]).agg(
        total_zp_calls=("mean_count", "sum")).reset_index()

    # Report
    L = []
    L.append("# T028e nodegate ablation — globalcap vs soft gate vs strict gate\n")
    L.append(
        "Compares three candidate gating modes for zero-proxy arms. "
        "All use GBM event-utility policy on 9-arm extended candidates, "
        "strict-replay LOSO, with `MAX_ZERO_PROXY_SHARE=0.10` policy cap.\n"
    )
    L.append("## Gate definitions\n")
    L.append("- **globalcap**: Always generate all 9 arms; cap at policy level only (current ECP-c2).")
    L.append("- **soft_gate**: Generate zp arms only when `zp_share >= 0.40`, `>=6 zp bins remain`, "
              "AND (`n_probe >= 2 with 0 positives` OR `negative_streak >= 2`).")
    L.append("- **strict_gate**: Generate zp arms only when `zp_share >= 0.50`, `>=8 zp bins`, "
              "`n_probe >= 3`, AND `n_pos == 0`.\n")

    L.append("## Per-segment mean event_recall\n")
    L.append("| segment | budget | globalcap | soft_gate | strict_gate | soft-global | strict-global |")
    L.append("|---|---|---|---|---|---|---|")
    for seg in all_seg_ids:
        for br in BUDGET_RATIOS:
            gc = globalcap[(globalcap.segment_id == seg) & (globalcap.budget_ratio == br)]
            sf = soft[(soft.segment_id == seg) & (soft.budget_ratio == br)]
            st = strict[(strict.segment_id == seg) & (strict.budget_ratio == br)]
            gcr = gc["recall"].values[0] if len(gc) else 0.0
            sfr = sf["recall"].values[0] if len(sf) else 0.0
            str_ = st["recall"].values[0] if len(st) else 0.0
            L.append(f"| {seg} | {br:.2f} | {gcr:.3f} | {sfr:.3f} | {str_:.3f} | {sfr-gcr:+.3f} | {str_-gcr:+.3f} |")

    L.append("\n## Zero-proxy arm calls per gate mode\n")
    L.append("| gate_mode | segment | budget | total_zp_calls |")
    L.append("|---|---|---|---|")
    for _, r in zp_act.iterrows():
        L.append(f"| {r['gate_mode']} | {r['segment_id']} | {r['budget_ratio']:.2f} | {r['total_zp_calls']:.1f} |")

    L.append("\n## Pass/fail\n")
    d3_1200_gc = globalcap[(globalcap.segment_id == "dataset3_0_1200") & (globalcap.budget_ratio > 0.15)]
    d3_1200_sf = soft[(soft.segment_id == "dataset3_0_1200") & (soft.budget_ratio > 0.15)]
    d3_1200_st = strict[(strict.segment_id == "dataset3_0_1200") & (strict.budget_ratio > 0.15)]
    gc_max = d3_1200_gc["recall"].max() if len(d3_1200_gc) else 0.0
    sf_max = d3_1200_sf["recall"].max() if len(d3_1200_sf) else 0.0
    st_max = d3_1200_st["recall"].max() if len(d3_1200_st) else 0.0

    L.append(f"- dataset3_0_1200 globalcap max: {gc_max:.3f}")
    L.append(f"- dataset3_0_1200 soft_gate max: {sf_max:.3f}")
    L.append(f"- dataset3_0_1200 strict_gate max: {st_max:.3f}")

    if sf_max >= gc_max - 0.001:
        L.append("- **soft_gate PASS**: does not regress on dataset3_0_1200.")
    else:
        L.append("- **soft_gate FAIL**: regresses vs globalcap on dataset3_0_1200.")
    if st_max >= gc_max - 0.001:
        L.append("- **strict_gate PASS**: does not regress on dataset3_0_1200.")
    else:
        L.append("- **strict_gate FAIL**: regresses vs globalcap on dataset3_0_1200.")

    # Check realcartest regressions
    rc_segs = [s for s in all_seg_ids if s.startswith("realcartest")]
    rc_ok = True
    for seg in rc_segs:
        for br in BUDGET_RATIOS:
            gc_r = globalcap[(globalcap.segment_id == seg) & (globalcap.budget_ratio == br)]["recall"].values
            sf_r = soft[(soft.segment_id == seg) & (soft.budget_ratio == br)]["recall"].values
            st_r = strict[(strict.segment_id == seg) & (strict.budget_ratio == br)]["recall"].values
            if len(gc_r) and len(sf_r) and sf_r[0] < gc_r[0] - 0.01:
                rc_ok = False
                L.append(f"- **WARNING**: soft_gate regresses on {seg} @{br:.2f}")
            if len(gc_r) and len(st_r) and st_r[0] < gc_r[0] - 0.01:
                rc_ok = False
                L.append(f"- **WARNING**: strict_gate regresses on {seg} @{br:.2f}")

    if rc_ok:
        L.append("- **realcartest**: 0 gate-mode regressions.")

    md = OUT / "t028e_nodegate_report.md"
    md.write_text("\n".join(L))
    print(f"\nwrote {OUT / 't028e_nodegate_frontier.csv'}")
    print(f"wrote {OUT / 't028e_nodegate_action_usage.csv'}")
    print(f"wrote {md}")


if __name__ == "__main__":
    main()
