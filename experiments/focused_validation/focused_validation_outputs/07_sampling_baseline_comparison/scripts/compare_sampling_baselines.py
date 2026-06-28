#!/usr/bin/env python3
"""Diagnostic sampling baseline comparison for VLM pseudo-oracle benchmark."""

from __future__ import annotations

import argparse
import math
import random
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_LABELS = Path("/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded/vlm_labels_conservative.csv")
DEFAULT_PROXY = Path("/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded/proxy_scores_with_learned.csv")
DEFAULT_EVENT_METRICS = Path("/qiuyeqing/llama_prl/G-ARC/test_vlm/focused_validation_outputs/03_event_conversion/event_level_metrics.csv")
DEFAULT_REPORT = Path("/qiuyeqing/llama_prl/G-ARC/test_vlm/focused_validation_outputs/06_focused_validation_report.md")
RF_CANDIDATES = ["score_learned_rf", "learned_rf_score", "rf_score", "score_rf"]


def as_positive(value) -> bool:
    return str(value).strip().lower() in {"yes", "true", "1", "positive"}


def safe_float(value, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def parse_floats(text: str) -> list[float]:
    return [float(x) for x in text.split(",") if x.strip()]


def auto_find(pattern: str) -> Path | None:
    cmd = "find /qiuyeqing/llama_prl/G-ARC/test_vlm -name '*.csv' | grep -E 'vlm|label|proxy|focused|event'"
    out = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    paths = [Path(x) for x in out.stdout.splitlines()]
    for p in paths:
        if pattern in p.name:
            return p
    return None


def resolve_inputs(labels_csv: Path | None, proxy_csv: Path | None, event_metrics_csv: Path | None) -> tuple[Path, Path, Path | None]:
    labels = labels_csv or (DEFAULT_LABELS if DEFAULT_LABELS.exists() else auto_find("vlm_labels_conservative"))
    proxy = proxy_csv or (DEFAULT_PROXY if DEFAULT_PROXY.exists() else auto_find("proxy_scores_with_learned"))
    event_metrics = event_metrics_csv or (DEFAULT_EVENT_METRICS if DEFAULT_EVENT_METRICS.exists() else auto_find("event_level_metrics"))
    if labels is None or not labels.exists():
        raise SystemExit("Could not locate labels CSV; pass --labels_csv")
    if proxy is None or not proxy.exists():
        raise SystemExit("Could not locate proxy CSV; pass --proxy_csv")
    return labels, proxy, event_metrics


def load_rows(labels_csv: Path, proxy_csv: Path) -> tuple[pd.DataFrame, str | None, list[str]]:
    labels = pd.read_csv(labels_csv)
    proxy = pd.read_csv(proxy_csv)
    missing = []
    for col in ["clip_id", "segment_id", "start_time", "end_time", "conservative_positive"]:
        if col not in labels.columns and col not in proxy.columns:
            missing.append(col)
    for col in ["clip_id", "score_count"]:
        if col not in proxy.columns:
            missing.append(col)
    if missing:
        raise SystemExit(f"Missing required columns: {missing}")

    label_cols = [c for c in ["clip_id", "segment_id", "start_time", "end_time", "clip_path", "conservative_positive", "risk_level", "event_type", "negative_reason", "evidence"] if c in labels.columns]
    proxy_cols = [c for c in proxy.columns if c in {
        "clip_id", "video_id", "segment_id", "start_time", "end_time", "clip_path",
        "score_count", "score_naive", "score_kinematic", *RF_CANDIDATES,
    }]
    rows = proxy[proxy_cols].merge(labels[label_cols], on="clip_id", how="inner", suffixes=("", "_label"))
    for col in ["segment_id", "start_time", "end_time", "clip_path"]:
        alt = f"{col}_label"
        if col not in rows.columns and alt in rows.columns:
            rows[col] = rows[alt]
        elif alt in rows.columns:
            rows[col] = rows[col].combine_first(rows[alt])
    if "video_id" not in rows.columns:
        rows["video_id"] = rows["segment_id"].astype(str).str.rsplit("_seg", n=1).str[0]
    for col in ["score_naive", "score_kinematic"]:
        if col not in rows.columns:
            rows[col] = 0.0
    rf_col = next((c for c in RF_CANDIDATES if c in rows.columns), None)
    rows["oracle_positive"] = rows["conservative_positive"].map(as_positive)
    rows["start_time"] = rows["start_time"].map(safe_float)
    rows["end_time"] = rows["end_time"].map(safe_float)
    rows["score_count"] = rows["score_count"].map(safe_float)
    rows["score_naive"] = rows["score_naive"].map(safe_float)
    rows["score_kinematic"] = rows["score_kinematic"].map(safe_float)
    if rf_col:
        rows[rf_col] = rows[rf_col].map(safe_float)
    rows = rows.sort_values(["segment_id", "start_time", "clip_id"]).reset_index(drop=True)
    return rows, rf_col, sorted(set(RF_CANDIDATES) - set(rows.columns))


def write_inventory(out_dir: Path, labels_csv: Path, proxy_csv: Path, event_metrics_csv: Path | None, rows: pd.DataFrame, labels: pd.DataFrame, proxy: pd.DataFrame, rf_col: str | None, missing_rf: list[str]) -> None:
    lines = [
        "# Sampling Baseline Input Inventory",
        "",
        f"- labels_csv: `{labels_csv}`",
        f"- proxy_csv: `{proxy_csv}`",
        f"- focused_event_metrics_csv: `{event_metrics_csv}` exists={bool(event_metrics_csv and event_metrics_csv.exists())}",
        f"- joined rows: {len(rows)}",
        f"- oracle positives: {int(rows['oracle_positive'].sum())}",
        f"- learned RF field used: `{rf_col}`" if rf_col else "- learned RF field used: missing",
        f"- missing RF candidate fields: `{missing_rf}`",
        "",
        "## Label Fields",
        f"`{list(labels.columns)}`",
        "",
        "## Proxy Fields",
        f"`{list(proxy.columns)}`",
        "",
        "## Joined Fields",
        f"`{list(rows.columns)}`",
        "",
    ]
    (out_dir / "input_inventory.md").write_text("\n".join(lines), encoding="utf-8")
    print(out_dir / "input_inventory.md")


def allocation_equal(rows: pd.DataFrame, budget: int) -> dict[str, int]:
    segs = sorted(rows["segment_id"].unique())
    base = budget // len(segs)
    rem = budget % len(segs)
    return {seg: base + (i < rem) for i, seg in enumerate(segs)}


def allocation_length(rows: pd.DataFrame, budget: int) -> dict[str, int]:
    counts = rows.groupby("segment_id").size().sort_index()
    raw = counts / counts.sum() * budget
    alloc = np.floor(raw).astype(int)
    rem = budget - int(alloc.sum())
    frac = (raw - alloc).sort_values(ascending=False)
    for seg in frac.index[:rem]:
        alloc.loc[seg] += 1
    return alloc.to_dict()


def fill_to_budget(rows: pd.DataFrame, selected: list[str], budget: int, score_col: str | None = None) -> list[str]:
    seen = set(selected)
    if score_col:
        rest = rows.assign(_score=rows[score_col].map(safe_float)).sort_values(["_score", "segment_id", "start_time"], ascending=[False, True, True])
    else:
        rest = rows.sort_values(["segment_id", "start_time"])
    for cid in rest["clip_id"]:
        if len(selected) >= budget:
            break
        if cid not in seen:
            selected.append(cid)
            seen.add(cid)
    return selected[:budget]


def top_by_score(rows: pd.DataFrame, budget: int, score_col: str) -> list[str]:
    return rows.assign(_score=rows[score_col].map(safe_float)).sort_values(["_score", "segment_id", "start_time"], ascending=[False, True, True])["clip_id"].head(budget).tolist()


def uniform_time(rows: pd.DataFrame, budget: int) -> list[str]:
    ordered = rows.sort_values(["segment_id", "start_time", "clip_id"]).reset_index(drop=True)
    if budget >= len(ordered):
        return ordered["clip_id"].tolist()
    idx = np.linspace(0, len(ordered) - 1, budget).round().astype(int)
    return ordered.iloc[idx]["clip_id"].tolist()


def temporal_uniform_nms(rows: pd.DataFrame, budget: int) -> list[str]:
    ordered = rows.sort_values(["segment_id", "start_time", "clip_id"]).reset_index(drop=True)
    n = len(ordered)
    if budget >= n:
        return ordered["clip_id"].tolist()
    selected_idx = [n // 2]
    while len(selected_idx) < budget:
        arr = np.array(selected_idx)
        best_i, best_d = None, -1
        for i in range(n):
            if i in selected_idx:
                continue
            d = np.min(np.abs(arr - i))
            if d > best_d:
                best_i, best_d = i, d
        selected_idx.append(best_i)
    selected_idx = sorted(selected_idx)
    return ordered.iloc[selected_idx]["clip_id"].tolist()


def segment_random(rows: pd.DataFrame, budget: int, seed: int, mode: str) -> list[str]:
    rng = random.Random(seed)
    alloc = allocation_equal(rows, budget) if mode == "equal" else allocation_length(rows, budget)
    selected = []
    for seg, n in alloc.items():
        ids = rows[rows["segment_id"].eq(seg)]["clip_id"].tolist()
        rng.shuffle(ids)
        selected.extend(ids[:n])
    return fill_to_budget(rows, selected, budget)


def segment_balanced_top(rows: pd.DataFrame, budget: int, score_col: str) -> list[str]:
    alloc = allocation_length(rows, budget)
    selected = []
    for seg, n in alloc.items():
        g = rows[rows["segment_id"].eq(seg)]
        selected.extend(top_by_score(g, min(n, len(g)), score_col))
    return fill_to_budget(rows, selected, budget, score_col)


def temporal_nms_count(rows: pd.DataFrame, budget: int, gap: float) -> list[str]:
    selected = []
    selected_rows = []
    ordered = rows.assign(_score=rows["score_count"].map(safe_float)).sort_values("_score", ascending=False)
    for _, row in ordered.iterrows():
        st = row["start_time"]
        seg = row["segment_id"]
        if all(seg != s["segment_id"] or abs(st - s["start_time"]) > gap for s in selected_rows):
            selected.append(row["clip_id"])
            selected_rows.append(row)
        if len(selected) >= budget:
            break
    return fill_to_budget(rows, selected, budget, "score_count")


def shuffled_top(rows: pd.DataFrame, budget: int, score_col: str, seed: int) -> list[str]:
    rng = np.random.default_rng(seed)
    tmp = rows.copy()
    tmp["_shuffled_score"] = rng.permutation(tmp[score_col].to_numpy())
    return top_by_score(tmp, budget, "_shuffled_score")


def oracle_positive_first(rows: pd.DataFrame, budget: int) -> list[str]:
    pos = rows[rows["oracle_positive"]].sort_values(["segment_id", "start_time"])["clip_id"].tolist()
    neg = rows[~rows["oracle_positive"]].sort_values(["segment_id", "start_time"])["clip_id"].tolist()
    return (pos + neg)[:budget]


def select_policy(rows: pd.DataFrame, method: str, budget: int, seed: int, rf_col: str | None) -> list[str]:
    if method == "random":
        ids = rows["clip_id"].tolist()
        random.Random(seed).shuffle(ids)
        return ids[:budget]
    if method == "uniform_time":
        return uniform_time(rows, budget)
    if method == "segment_equal_random":
        return segment_random(rows, budget, seed, "equal")
    if method == "segment_length_random":
        return segment_random(rows, budget, seed, "length")
    if method == "temporal_uniform_nms":
        return temporal_uniform_nms(rows, budget)
    if method == "top_count":
        return top_by_score(rows, budget, "score_count")
    if method == "temporal_nms_count":
        return temporal_nms_count(rows, budget, 6.0)
    if method == "segment_balanced_top_count":
        return segment_balanced_top(rows, budget, "score_count")
    if method == "top_learned_rf":
        if not rf_col:
            raise KeyError("missing learned RF score")
        return top_by_score(rows, budget, rf_col)
    if method == "segment_balanced_top_learned_rf":
        if not rf_col:
            raise KeyError("missing learned RF score")
        return segment_balanced_top(rows, budget, rf_col)
    if method == "shuffled_count":
        return shuffled_top(rows, budget, "score_count", seed)
    if method == "shuffled_learned_rf":
        if not rf_col:
            raise KeyError("missing learned RF score")
        return shuffled_top(rows, budget, rf_col, seed)
    if method == "oracle_positive_first":
        return oracle_positive_first(rows, budget)
    raise KeyError(method)


def method_meta(method: str) -> dict:
    return {
        "method_family": (
            "random" if "random" in method else
            "uniform" if "uniform" in method else
            "proxy" if "top" in method or "count" in method else
            "oracle_upper_bound" if method == "oracle_positive_first" else
            "control"
        ),
        "uses_proxy": method in {"top_count", "temporal_nms_count", "segment_balanced_top_count", "shuffled_count"},
        "uses_learned_proxy": method in {"top_learned_rf", "segment_balanced_top_learned_rf", "shuffled_learned_rf"},
        "uses_temporal_diversity": method in {"uniform_time", "temporal_uniform_nms", "temporal_nms_count"},
        "uses_segment_balance": method in {"segment_equal_random", "segment_length_random", "segment_balanced_top_count", "segment_balanced_top_learned_rf"},
        "is_shuffled_control": method in {"shuffled_count", "shuffled_learned_rf"},
        "is_oracle_upper_bound": method == "oracle_positive_first",
    }


def build_events(pos_rows: pd.DataFrame, gap: float) -> pd.DataFrame:
    events = []
    eid = 0
    for seg, g in pos_rows.sort_values(["segment_id", "start_time"]).groupby("segment_id"):
        cur = None
        for _, row in g.iterrows():
            st, en = row["start_time"], row["end_time"]
            if cur is None or st - cur["event_end"] > gap:
                if cur is not None:
                    events.append(cur)
                cur = {"event_id": f"event_{eid:04d}", "segment_id": seg, "event_start": st, "event_end": en, "clip_ids": [row["clip_id"]]}
                eid += 1
            else:
                cur["event_end"] = max(cur["event_end"], en)
                cur["clip_ids"].append(row["clip_id"])
        if cur is not None:
            events.append(cur)
    for ev in events:
        ev["duration"] = ev["event_end"] - ev["event_start"]
    return pd.DataFrame(events)


def interval_iou(a0: float, a1: float, b0: float, b1: float) -> float:
    inter = max(0.0, min(a1, b1) - max(a0, b0))
    union = max(a1, b1) - min(a0, b0)
    return inter / union if union > 0 else 0.0


def match_events(oracle: pd.DataFrame, returned: pd.DataFrame, theta: float) -> dict:
    pairs = []
    if oracle.empty:
        return {"matched_oracle_events": 0, "oracle_event_recall": 0.0, "oracle_event_precision": 0.0, "mean_event_iou": 0.0, "median_event_iou": 0.0, "mean_start_error": np.nan, "mean_end_error": np.nan}
    for oi, o in oracle.iterrows():
        if returned.empty:
            continue
        for ri, r in returned[returned["segment_id"].eq(o["segment_id"])].iterrows():
            iou = interval_iou(o["event_start"], o["event_end"], r["event_start"], r["event_end"])
            if iou > 0:
                pairs.append((iou, oi, ri))
    pairs.sort(reverse=True)
    mo, mr, ious, starts, ends = set(), set(), [], [], []
    for iou, oi, ri in pairs:
        if iou < theta or oi in mo or ri in mr:
            continue
        mo.add(oi)
        mr.add(ri)
        o, r = oracle.loc[oi], returned.loc[ri]
        ious.append(iou)
        starts.append(abs(r["event_start"] - o["event_start"]))
        ends.append(abs(r["event_end"] - o["event_end"]))
    return {
        "matched_oracle_events": len(mo),
        "oracle_event_recall": len(mo) / len(oracle) if len(oracle) else 0.0,
        "oracle_event_precision": len(mr) / len(returned) if len(returned) else 0.0,
        "mean_event_iou": float(np.mean(ious)) if ious else 0.0,
        "median_event_iou": float(np.median(ious)) if ious else 0.0,
        "mean_start_error": float(np.mean(starts)) if starts else np.nan,
        "mean_end_error": float(np.mean(ends)) if ends else np.nan,
    }


def evaluate(rows: pd.DataFrame, selected: list[str], gap: float, theta: float) -> dict:
    selected_set = set(selected)
    oracle_pos = set(rows[rows["oracle_positive"]]["clip_id"])
    selected_pos = selected_set & oracle_pos
    oracle_events = build_events(rows[rows["oracle_positive"]], gap)
    returned_events = build_events(rows[rows["clip_id"].isin(selected_pos)], gap)
    ev = match_events(oracle_events, returned_events, theta)
    out = {
        "vlm_calls": len(selected),
        "vlm_call_saving": 1.0 - len(selected) / len(rows),
        "oracle_positive_clips": len(oracle_pos),
        "selected_positive_clips": len(selected_pos),
        "oracle_clip_recall": len(selected_pos) / len(oracle_pos) if oracle_pos else 0.0,
        "selected_clip_precision": len(selected_pos) / len(selected_set) if selected_set else 0.0,
        "num_oracle_events": len(oracle_events),
        "num_returned_events": len(returned_events),
    }
    out.update(ev)
    return out


def bootstrap_ci(values: np.ndarray, seed: int = 0) -> tuple[float, float]:
    if len(values) <= 1:
        val = float(values[0]) if len(values) else np.nan
        return val, val
    rng = np.random.default_rng(seed)
    means = [float(rng.choice(values, len(values), replace=True).mean()) for _ in range(1000)]
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def aggregate(by_seed: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (method, frac, calls), g in by_seed.groupby(["method", "budget_fraction", "budget_calls"]):
        vals = g["oracle_event_recall"].to_numpy()
        lo, hi = bootstrap_ci(vals)
        rows.append({
            "method": method,
            "budget_fraction": frac,
            "budget_calls": calls,
            "mean_oracle_event_recall": float(vals.mean()),
            "std_oracle_event_recall": float(vals.std(ddof=0)),
            "ci95_low_oracle_event_recall": lo,
            "ci95_high_oracle_event_recall": hi,
            "mean_oracle_clip_recall": float(g["oracle_clip_recall"].mean()),
            "std_oracle_clip_recall": float(g["oracle_clip_recall"].std(ddof=0)),
            "mean_event_precision": float(g["oracle_event_precision"].mean()),
            "mean_event_iou": float(g["mean_event_iou"].mean()),
            "num_trials": len(g),
        })
    return pd.DataFrame(rows).sort_values(["budget_fraction", "mean_oracle_event_recall"], ascending=[True, False])


def plot_outputs(out_dir: Path, agg: pd.DataFrame) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:
        (out_dir / "PLOTS_SKIPPED.md").write_text(f"matplotlib unavailable: {exc}\n", encoding="utf-8")
        return
    curve_methods = [
        "random", "uniform_time", "segment_length_random", "top_count", "temporal_nms_count",
        "segment_balanced_top_count", "top_learned_rf", "segment_balanced_top_learned_rf",
        "shuffled_count", "oracle_positive_first",
    ]
    plt.figure(figsize=(10, 6))
    for method in curve_methods:
        d = agg[agg["method"].eq(method)]
        if d.empty:
            continue
        plt.plot(d["budget_fraction"], d["mean_oracle_event_recall"], marker="o", label=method)
    plt.xlabel("budget_fraction")
    plt.ylabel("mean oracle_event_recall")
    plt.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(out_dir / "sampling_baseline_budget_curve.png", dpi=160)
    plt.close()

    d20 = agg[np.isclose(agg["budget_fraction"], 0.20)].sort_values("mean_oracle_event_recall", ascending=False)
    plt.figure(figsize=(12, 5))
    plt.bar(d20["method"], d20["mean_oracle_event_recall"])
    plt.xticks(rotation=70, ha="right")
    plt.ylabel("oracle_event_recall at 20% budget")
    plt.tight_layout()
    plt.savefig(out_dir / "sampling_baseline_event_recall_bar_20pct.png", dpi=160)
    plt.close()


def markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_empty_"
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, r in df.iterrows():
        vals = []
        for c in cols:
            v = r[c]
            vals.append(f"{v:.3f}" if isinstance(v, float) else str(v))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def make_drop_summary(agg: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    pairs = [("count", "top_count", "shuffled_count"), ("learned_rf", "top_learned_rf", "shuffled_learned_rf")]
    rows = []
    for score_type, orig, shuf in pairs:
        for frac in sorted(agg["budget_fraction"].unique()):
            o = agg[(agg.method.eq(orig)) & (agg.budget_fraction.eq(frac))]
            s = agg[(agg.method.eq(shuf)) & (agg.budget_fraction.eq(frac))]
            if o.empty or s.empty:
                continue
            ov = float(o.iloc[0]["mean_oracle_event_recall"])
            sv = float(s.iloc[0]["mean_oracle_event_recall"])
            rows.append({
                "score_type": score_type,
                "budget_fraction": frac,
                "original_method": orig,
                "shuffled_method": shuf,
                "original_event_recall": ov,
                "shuffled_event_recall_mean": sv,
                "absolute_drop": ov - sv,
                "relative_drop": (ov - sv) / ov if ov else np.nan,
            })
    df = pd.DataFrame(rows)
    df.to_csv(out_dir / "shuffled_proxy_drop_summary.csv", index=False)
    try:
        import matplotlib.pyplot as plt
        if not df.empty:
            plt.figure(figsize=(8, 4))
            for st, g in df.groupby("score_type"):
                plt.plot(g["budget_fraction"], g["absolute_drop"], marker="o", label=st)
            plt.axhline(0, color="black", linewidth=0.8)
            plt.xlabel("budget_fraction")
            plt.ylabel("oracle_event_recall drop vs shuffled")
            plt.legend()
            plt.tight_layout()
            plt.savefig(out_dir / "shuffled_proxy_drop.png", dpi=160)
            plt.close()
    except Exception:
        pass
    return df


def make_segment_balanced_summary(agg: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    rows = []
    comparisons = [
        ("top_count", "segment_balanced_top_count"),
        ("top_learned_rf", "segment_balanced_top_learned_rf"),
        ("segment_balanced_top_count", "segment_length_random"),
        ("segment_balanced_top_learned_rf", "segment_length_random"),
    ]
    for a, b in comparisons:
        for frac in sorted(agg["budget_fraction"].unique()):
            da = agg[(agg.method.eq(a)) & (agg.budget_fraction.eq(frac))]
            db = agg[(agg.method.eq(b)) & (agg.budget_fraction.eq(frac))]
            if da.empty or db.empty:
                continue
            av = float(da.iloc[0]["mean_oracle_event_recall"])
            bv = float(db.iloc[0]["mean_oracle_event_recall"])
            rows.append({"method_a": a, "method_b": b, "budget_fraction": frac, "event_recall_a": av, "event_recall_b": bv, "delta_a_minus_b": av - bv})
    df = pd.DataFrame(rows)
    df.to_csv(out_dir / "segment_balanced_summary.csv", index=False)
    return df


def write_report(out_dir: Path, agg: pd.DataFrame, by_seed: pd.DataFrame, drop: pd.DataFrame, segsum: pd.DataFrame, skipped: list[str], labels_csv: Path, proxy_csv: Path, rf_col: str | None) -> str:
    d20 = agg[np.isclose(agg["budget_fraction"], 0.20)].sort_values("mean_oracle_event_recall", ascending=False)
    d10 = agg[np.isclose(agg["budget_fraction"], 0.10)].sort_values("mean_oracle_event_recall", ascending=False)
    def val(method: str, frac: float) -> float | None:
        d = agg[(agg.method.eq(method)) & (np.isclose(agg.budget_fraction, frac))]
        return None if d.empty else float(d.iloc[0]["mean_oracle_event_recall"])
    conclusions = []
    for frac in [0.10, 0.20]:
        tc, rnd = val("top_count", frac), val("random", frac)
        rf, uni = val("top_learned_rf", frac), val("uniform_time", frac)
        if tc is not None and rnd is not None:
            conclusions.append(f"- {int(frac*100)}%: top_count {tc:.3f} vs random {rnd:.3f}.")
        if rf is not None and rnd is not None:
            conclusions.append(f"- {int(frac*100)}%: top_learned_rf {rf:.3f} vs random {rnd:.3f}.")
        if tc is not None and uni is not None:
            conclusions.append(f"- {int(frac*100)}%: top_count {tc:.3f} vs uniform_time {uni:.3f}.")
    proxy_useful = (
        (val("top_count", 0.20) or 0) > (val("random", 0.20) or 0) and
        (val("top_count", 0.20) or 0) > (val("shuffled_count", 0.20) or 0)
    )
    if rf_col and val("top_learned_rf", 0.20) is not None:
        proxy_useful = proxy_useful and (val("top_learned_rf", 0.20) or 0) > (val("shuffled_learned_rf", 0.20) or 0)
    conclusion = "proxy contains useful ranking signal on this pilot/dev set" if proxy_useful else "proxy utility is not clearly separated from controls on this pilot/dev set"
    lines = [
        "# Sampling Baseline Comparison",
        "",
        "All metrics are relative to the full conservative VLM pseudo-oracle, not human ground truth.",
        "",
        f"- labels_csv: `{labels_csv}`",
        f"- proxy_csv: `{proxy_csv}`",
        f"- learned RF score field: `{rf_col}`" if rf_col else "- learned RF score field: missing; learned RF methods skipped",
        f"- skipped methods: `{skipped}`",
        "- event conversion: gap_threshold_seconds=3, iou_threshold=0.3",
        "",
        "## 20% Budget Ranking",
        markdown_table(d20[["method", "mean_oracle_event_recall", "mean_oracle_clip_recall", "mean_event_precision", "mean_event_iou", "num_trials"]]),
        "",
        "## 10% Budget Ranking",
        markdown_table(d10[["method", "mean_oracle_event_recall", "mean_oracle_clip_recall", "mean_event_precision", "mean_event_iou", "num_trials"]]),
        "",
        "## Q1. Proxy vs Random",
        *conclusions,
        "",
        "## Q2. Proxy vs Uniform Temporal Sampling",
        f"- top_count vs uniform_time at 20%: {val('top_count', 0.20):.3f} vs {val('uniform_time', 0.20):.3f}.",
        f"- temporal_nms_count vs temporal_uniform_nms at 20%: {val('temporal_nms_count', 0.20):.3f} vs {val('temporal_uniform_nms', 0.20):.3f}.",
        "",
        "## Q3. Proxy vs Segment-stratified Random",
        f"- segment_balanced_top_count vs segment_length_random at 20%: {val('segment_balanced_top_count', 0.20):.3f} vs {val('segment_length_random', 0.20):.3f}.",
        f"- segment_balanced_top_count vs segment_equal_random at 20%: {val('segment_balanced_top_count', 0.20):.3f} vs {val('segment_equal_random', 0.20):.3f}.",
        "",
        "## Q4. Shuffled Proxy Controls",
        markdown_table(drop[drop["budget_fraction"].isin([0.10, 0.20])]),
        "",
        "## Q5. Segment-balanced Proxy",
        markdown_table(segsum[segsum["budget_fraction"].isin([0.10, 0.20])]),
        "",
        "## Q6. Diagnostic Conclusion",
        f"- Diagnostic conclusion: {conclusion}.",
        "- If proxy methods beat random, uniform, segment-stratified, and shuffled controls, the proxy is carrying ranking signal beyond time coverage and segment prior.",
        "- However, because the pilot positives are temporally/segment concentrated, this remains a pilot/dev diagnostic and should not become the formal 100-trial main evaluation.",
        "- A new, less concentrated video source remains the necessary next step.",
        "",
    ]
    text = "\n".join(lines)
    (out_dir / "sampling_baseline_comparison.md").write_text(text, encoding="utf-8")
    return conclusion


def append_focused_report(out_dir: Path, conclusion: str) -> None:
    report = DEFAULT_REPORT
    if not report.exists():
        return
    section = f"""

## 10. Sampling Baseline Diagnostic Addendum

- Output directory: `{out_dir}`
- Main CSV: `{out_dir / 'sampling_baseline_comparison.csv'}`
- Per-trial CSV: `{out_dir / 'sampling_baseline_comparison_by_budget.csv'}`
- Diagnostic conclusion: {conclusion}.
- These results remain relative to the full conservative VLM pseudo-oracle, not human ground truth.
- The pilot benchmark can diagnose proxy signal, but due to temporal/segment concentration it should still not be promoted to formal 100-trial main evaluation without a less concentrated video source.
"""
    text = report.read_text(encoding="utf-8")
    marker = "\n## 10. Sampling Baseline Diagnostic Addendum\n"
    if marker in text:
        text = text.split(marker)[0].rstrip() + section
    else:
        text = text.rstrip() + section
    report.write_text(text.rstrip() + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels_csv", type=Path, default=None)
    parser.add_argument("--proxy_csv", type=Path, default=None)
    parser.add_argument("--event_metrics_csv", type=Path, default=None)
    parser.add_argument("--out_dir", type=Path, required=True)
    parser.add_argument("--budget_fracs", default="0.05,0.10,0.15,0.20,0.25,0.30")
    parser.add_argument("--gap_seconds", type=float, default=3.0)
    parser.add_argument("--iou_threshold", type=float, default=0.3)
    parser.add_argument("--seeds", type=int, default=100)
    args = parser.parse_args()

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    labels_csv, proxy_csv, event_metrics_csv = resolve_inputs(args.labels_csv, args.proxy_csv, args.event_metrics_csv)
    rows, rf_col, missing_rf = load_rows(labels_csv, proxy_csv)
    labels, proxy = pd.read_csv(labels_csv), pd.read_csv(proxy_csv)
    write_inventory(out_dir, labels_csv, proxy_csv, event_metrics_csv, rows, labels, proxy, rf_col, missing_rf)

    methods = [
        "random", "uniform_time", "segment_equal_random", "segment_length_random",
        "temporal_uniform_nms", "top_count", "temporal_nms_count", "segment_balanced_top_count",
        "top_learned_rf", "segment_balanced_top_learned_rf",
        "shuffled_count", "shuffled_learned_rf", "oracle_positive_first",
    ]
    if not rf_col:
        methods = [m for m in methods if "learned_rf" not in m]
    skipped = ["top_learned_rf", "segment_balanced_top_learned_rf", "shuffled_learned_rf"] if not rf_col else []
    stochastic = {"random", "segment_equal_random", "segment_length_random", "shuffled_count", "shuffled_learned_rf"}
    budgets = parse_floats(args.budget_fracs)
    result_rows = []
    for frac in budgets:
        budget = int(round(frac * len(rows)))
        budget = max(1, min(len(rows), budget))
        for method in methods:
            seeds = range(args.seeds) if method in stochastic else [0]
            for seed in seeds:
                try:
                    selected = select_policy(rows, method, budget, seed, rf_col)
                except KeyError:
                    if method not in skipped:
                        skipped.append(method)
                    continue
                metrics = evaluate(rows, selected, args.gap_seconds, args.iou_threshold)
                rec = {
                    "method": method,
                    **method_meta(method),
                    "seed": seed,
                    "budget_fraction": frac,
                    "budget_calls": budget,
                    "gap_threshold_seconds": args.gap_seconds,
                    "iou_threshold": args.iou_threshold,
                }
                rec.update(metrics)
                result_rows.append(rec)
    by_seed = pd.DataFrame(result_rows)
    by_seed.to_csv(out_dir / "sampling_baseline_comparison_by_budget.csv", index=False)
    agg = aggregate(by_seed)
    agg.to_csv(out_dir / "sampling_baseline_comparison.csv", index=False)
    drop = make_drop_summary(agg, out_dir)
    segsum = make_segment_balanced_summary(agg, out_dir)
    plot_outputs(out_dir, agg)
    conclusion = write_report(out_dir, agg, by_seed, drop, segsum, skipped, labels_csv, proxy_csv, rf_col)
    append_focused_report(out_dir, conclusion)
    print(out_dir / "sampling_baseline_comparison.csv")
    print(out_dir / "sampling_baseline_comparison_by_budget.csv")
    print(out_dir / "sampling_baseline_comparison.md")
    print("sampling_baseline_complete=true")


if __name__ == "__main__":
    main()
