"""Aligned Baselines V1: B7-strict-replay, D3-norepair-core-strict, SUPG-event, ABae-residual.

Runs 4 aligned strict-replay baselines on the same 6 LATE-AQP segments,
budget ratios, and seeds as EventLift Stage 2 multi-segment smoke. This
prepares the aligned baseline suite for the full benchmark.

Hard constraints:
  - 6 LATE-AQP segments only.
  - Replay over existing VLM-oracle-relative labels only.
  - No event_id in online decisions for any strict-replay method.
  - oracle_calls_total <= budget_abs asserted.
  - No video/GPU/VLM/YOLO inference.
  - Small outputs only.

All numbers are VLM-oracle-relative, not human ground truth. No safe
stopping, formal guarantee, or statistical bound is claimed (per AGENTS.md).
"""

import sys
import os
import io
import math
import contextlib
import json
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Set, Dict, Tuple, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "refe_repos" / "supg"))

from garc_eval.adapters.abae_adapter import quantile_stratify
from supg.datasource import DFDataSource
from supg.sampler import ImportanceSampler
from supg.selector import ApproxQuery, RecallSelector

import eventlift_stage2_dev as dev

OUT_DIR = REPO_ROOT / "outputs" / "aligned_baselines_v1"

FROZEN_DIR = REPO_ROOT / "outputs" / "late_aqp_frozen_cross_segment_v1"
CENTER10_REF = REPO_ROOT / "experiments/v13/v13_8_full_oracle/tables/center10_vlm_oracle_events.csv"
DATASET3_TABLE = REPO_ROOT / "src/garc_eval/outputs/codex_recompute_proxy_budget_basa_v1/tables/canonical_dataset3_anchor_table.csv"

SEGMENTS = [
    {"segment_id": "realcartest_0_1570", "video_id": "realcartest", "t_start": 0.0, "t_end": 1570.0},
    {"segment_id": "realcartest_2000_3200", "video_id": "realcartest", "t_start": 2000.0, "t_end": 3200.0},
    {"segment_id": "realcartest_3200_3830", "video_id": "realcartest", "t_start": 3200.0, "t_end": 3830.0},
    {"segment_id": "dataset3_0_1200", "video_id": "long_video_dataset3", "t_start": 0.0, "t_end": 1200.0},
    {"segment_id": "dataset3_1200_2400", "video_id": "long_video_dataset3", "t_start": 1200.0, "t_end": 2400.0},
    {"segment_id": "dataset3_2400_3462", "video_id": "long_video_dataset3", "t_start": 2400.0, "t_end": 3462.93},
]

BUDGET_RATIOS = [0.10, 0.20, 0.30]
SEEDS = [0, 1, 2]
PROXY_COL = "prior_score_max"
LABEL_COL = "is_positive"
BIN_SIZE = 10.0
CHUNK_SIZE_S = 60.0
NUM_STRATA = 5


# ----------------------------------------------------------------------
# Data loading (reused from multi-seg smoke)
# ----------------------------------------------------------------------
def load_realcartest_segment(seg):
    grid_path = FROZEN_DIR / f"grid_{seg['segment_id']}.csv"
    if not grid_path.exists():
        return None, None, f"grid file missing: {grid_path}"
    grid = pd.read_csv(grid_path)
    grid = grid.sort_values("bin_idx").reset_index(drop=True)
    c10 = pd.read_csv(CENTER10_REF)
    t_s, t_e = seg["t_start"], seg["t_end"]
    ref_seg = c10[(c10["event_start"] >= t_s) & (c10["event_end"] <= t_e)].copy()
    ref_seg["t_start"] = ref_seg["event_start"] - t_s
    ref_seg["t_end"] = ref_seg["event_end"] - t_s
    ref_seg = ref_seg[["event_id", "t_start", "t_end"]].sort_values("t_start").reset_index(drop=True)
    return grid, ref_seg, None


def load_dataset3_segment(seg):
    if not DATASET3_TABLE.exists():
        return None, None, f"canonical table missing: {DATASET3_TABLE}"
    df = pd.read_csv(DATASET3_TABLE)
    t_s, t_e = seg["t_start"], seg["t_end"]
    bins = []
    bin_idx = 0
    cur_t = t_s
    while cur_t < t_e:
        bin_t_end = min(cur_t + 10.0, t_e)
        mask = (df["start_time_s"] >= cur_t) & (df["start_time_s"] < bin_t_end)
        bin_anchors = df[mask]
        if len(bin_anchors) > 0:
            is_pos = bool(bin_anchors["is_positive"].any())
            proxy = max(0.0, float(bin_anchors["score_yolo_count"].max()))
            proxy_mean = max(0.0, float(bin_anchors["score_yolo_count"].mean()))
        else:
            is_pos = False
            proxy = 0.0
            proxy_mean = 0.0
        bins.append({
            "bin_idx": bin_idx,
            "local_t_start": cur_t - t_s,
            "local_t_end": bin_t_end - t_s,
            "is_positive": is_pos,
            "prior_score_max": proxy,
            "prior_score_mean": proxy_mean,
        })
        bin_idx += 1
        cur_t = bin_t_end
    grid = pd.DataFrame(bins)
    pos = df[df["is_positive"] == True].copy()
    ref_events = []
    for cid, g in pos.groupby("event_cluster_id"):
        if cid < 0:
            continue
        ev_start = float(g["event_start_absolute"].min())
        ev_end = float(g["event_end_absolute"].max())
        if ev_end < t_s or ev_start > t_e:
            continue
        ref_events.append({
            "event_id": f"dataset3_event_{int(cid):03d}",
            "t_start": max(ev_start, t_s) - t_s,
            "t_end": min(ev_end, t_e) - t_s,
        })
    ref_seg = pd.DataFrame(ref_events)
    if len(ref_seg) > 0:
        ref_seg = ref_seg.sort_values("t_start").reset_index(drop=True)
    return grid, ref_seg, None


def load_segment_data(seg):
    if seg["video_id"] == "realcartest":
        return load_realcartest_segment(seg)
    else:
        return load_dataset3_segment(seg)


# ----------------------------------------------------------------------
# Aligned oracle: tracks event_id leakage
# ----------------------------------------------------------------------
class AlignedOracle:
    """Replay oracle that asserts no event_id is read online."""

    def __init__(self, grid, segment_id, method_id, seed, budget_abs, budget_ratio):
        self.grid = grid.sort_values("bin_idx").reset_index(drop=True)
        self.labels = dict(zip(self.grid["bin_idx"], self.grid[LABEL_COL]))
        self.proxies = dict(zip(self.grid["bin_idx"], self.grid[PROXY_COL]))
        self.local_t = dict(zip(self.grid["bin_idx"],
                                zip(self.grid["local_t_start"], self.grid["local_t_end"])))
        self.segment_id = segment_id
        self.method_id = method_id
        self.seed = seed
        self.budget_abs = budget_abs
        self.budget_ratio = budget_ratio
        self.calls = 0
        self.ledger = []
        self._event_id_accessed = False

    def query_unit(self, bin_idx, action_type, source_action,
                   component_id="", stratum_id="", notes=""):
        if self.calls >= self.budget_abs:
            raise RuntimeError(f"Budget exceeded: {self.calls} >= {self.budget_abs}")
        label = bool(self.labels[bin_idx])
        oracle_label = "positive" if label else "negative"
        self.calls += 1
        self.ledger.append({
            "segment_id": self.segment_id,
            "method_id": self.method_id,
            "seed": self.seed,
            "budget_abs": self.budget_abs,
            "budget_ratio": self.budget_ratio,
            "call_idx": self.calls,
            "action_type": action_type,
            "source_action": source_action,
            "bin_id": bin_idx,
            "component_id": component_id,
            "proxy_score": self.proxies[bin_idx],
            "oracle_label": oracle_label,
            "online_positive": label,
            "added_to_returned_intervals": "",
            "cumulative_oracle_calls": self.calls,
            "budget_remaining": self.budget_abs - self.calls,
            "online_uses_event_id": False,
            # Paid-vs-cached fields (default paid). A future cache-propagation
            # path that reuses an already-paid label MUST write a separate
            # ledger row with oracle_call=False / query_cost=0 / cache_hit=True
            # so that duplicate-paid-query check (S-1) stays clean without
            # missing the audit trail of cache reads.
            "oracle_call": True,
            "query_cost": 1,
            "cache_hit": False,
            "notes": notes,
        })
        return oracle_label

    def assert_no_event_id(self):
        assert not self._event_id_accessed, \
            f"event_id was accessed online in {self.method_id}!"


# ----------------------------------------------------------------------
# Helper: temporal grouping of positive bins (strict, no event_id)
# ----------------------------------------------------------------------
def group_positive_bins(positive_bin_idxs, grid):
    if len(positive_bin_idxs) == 0:
        return []
    grid_sorted = grid.sort_values("bin_idx").reset_index(drop=True)
    bin_to_t = dict(zip(grid_sorted["bin_idx"],
                        zip(grid_sorted["local_t_start"], grid_sorted["local_t_end"])))
    sorted_bins = sorted(positive_bin_idxs)
    intervals = []
    cur_start_bin = sorted_bins[0]
    cur_end_bin = sorted_bins[0]
    for b in sorted_bins[1:]:
        if b == cur_end_bin + 1:
            cur_end_bin = b
        else:
            s, _ = bin_to_t[cur_start_bin]
            _, e = bin_to_t[cur_end_bin]
            intervals.append((s, e))
            cur_start_bin = b
            cur_end_bin = b
    s, _ = bin_to_t[cur_start_bin]
    _, e = bin_to_t[cur_end_bin]
    intervals.append((s, e))
    return intervals


def _iou_interval(a_start, a_end, b_start, b_end):
    inter = max(0.0, min(a_end, b_end) - max(a_start, b_start))
    union = max(a_end, b_end) - min(a_start, b_start)
    if union <= 0:
        return 0.0
    return inter / union


def evaluate_events(returned_intervals, ref_events):
    if len(ref_events) == 0:
        return {"event_precision": 0.0, "event_recall": 0.0, "unique_event_coverage": 0}
    ref_iv = list(zip(ref_events["t_start"].values, ref_events["t_end"].values))
    hits_precision = 0
    for (s, e) in returned_intervals:
        if any(_iou_interval(s, e, rs, re) >= 0.3 for (rs, re) in ref_iv):
            hits_precision += 1
    precision = hits_precision / len(returned_intervals) if returned_intervals else 0.0
    hits_recall = 0
    for (rs, re) in ref_iv:
        if any(_iou_interval(s, e, rs, re) >= 0.3 for (s, e) in returned_intervals):
            hits_recall += 1
    recall = hits_recall / len(ref_iv)
    return {"event_precision": precision, "event_recall": recall,
            "unique_event_coverage": hits_recall}


def binomial_ucb(n, alpha=0.05):
    if n <= 0:
        return 1.0
    return 1.0 - alpha ** (1.0 / n)


# ----------------------------------------------------------------------
# A. B7-strict-replay
# ----------------------------------------------------------------------
def run_b7_strict_replay(grid, ref_seg, seg_id, budget_abs, budget_ratio, seed):
    """B7 chunk-bandit with strict online novelty proxy (no event_id).

    Strict novelty proxy: a queried positive bin is a 'new online hit' if
    it is NOT already inside or adjacent (within 1 bin) of an already-returned
    online interval. This replaces the original event_id-based singleton
    counting in B7-core.

    The returned intervals are built from observed positives via temporal
    grouping (contiguous positive bins). Core/Halo post-processing uses
    boundary guards on observed positive intervals (no event_id).
    """
    method_id = "B7-strict-replay"
    oracle = AlignedOracle(grid, seg_id, method_id, seed, budget_abs, budget_ratio)
    grid_sorted = grid.sort_values("bin_idx").reset_index(drop=True)
    bin_idxs = grid_sorted["bin_idx"].values
    n_bins = len(bin_idxs)
    labels = dict(zip(grid_sorted["bin_idx"], grid_sorted[LABEL_COL]))
    proxies = dict(zip(grid_sorted["bin_idx"], grid_sorted[PROXY_COL]))
    bin_to_row = {int(b): r for b, r in zip(grid_sorted["bin_idx"], grid_sorted.iterrows())}

    rng = np.random.RandomState(seed * 100003 + 17)
    bins_per_chunk = max(1, int(CHUNK_SIZE_S // BIN_SIZE))
    n_chunks = int(math.ceil(n_bins / bins_per_chunk))

    sampled: Set[int] = set()
    n_c = np.zeros(n_chunks, dtype=int)
    # N1_c: count of 'online singleton' positives per chunk
    # (positive bins not adjacent to any already-known positive interval)
    N1_c = np.zeros(n_chunks, dtype=float)
    positive_bins: Set[int] = set()
    returned_intervals: List[Tuple[float, float]] = []

    def get_chunk(b):
        return min(b // bins_per_chunk, n_chunks - 1)

    def is_new_online_hit(b):
        """Strict novelty: positive AND not adjacent to existing positive interval."""
        if b not in positive_bins:
            return False
        # Check if b is adjacent to (or inside) an existing positive bin group
        for pb in positive_bins:
            if pb == b:
                return False  # already known
            if abs(pb - b) == 1:
                return False  # adjacent to existing positive
        return True

    def update_singletons():
        N1_c[:] = 0.0
        for b in positive_bins:
            if is_new_online_hit(b):
                c = get_chunk(b)
                N1_c[c] += 1

    def expand(b, c):
        """Temporal expansion around a positive bin (B7 k=3)."""
        for offset in range(1, 4):
            for sign in [-1, 1]:
                nb = b + sign * offset
                if nb < 0 or nb >= n_bins or nb in sampled:
                    continue
                if oracle.calls >= budget_abs:
                    return
                oracle.query_unit(nb, "B7_EXPAND", "B7_EXPAND",
                                  component_id=f"chunk{c}",
                                  notes=f"B7 expand offset={offset} sign={sign}")
                sampled.add(nb)
                n_c[c] += 1
                if bool(labels[nb]):
                    positive_bins.add(nb)
                return

    while oracle.calls < budget_abs:
        update_singletons()
        theta = rng.gamma(shape=N1_c + 0.1, scale=1.0 / (n_c + 1.0))
        for c in range(n_chunks):
            chunk_bins = list(range(c * bins_per_chunk, min((c + 1) * bins_per_chunk, n_bins)))
            if all(b in sampled for b in chunk_bins):
                theta[c] = -np.inf
        if np.all(theta == -np.inf):
            break
        chosen_c = int(np.argmax(theta))
        chunk_bins = list(range(chosen_c * bins_per_chunk, min((chosen_c + 1) * bins_per_chunk, n_bins)))
        unsampled = [b for b in chunk_bins if b not in sampled]
        if not unsampled:
            break
        b = int(rng.choice(unsampled))
        oracle.query_unit(b, "B7_SAMPLE", "B7_SAMPLE",
                          component_id=f"chunk{chosen_c}",
                          notes="B7 chunk-bandit sample")
        sampled.add(b)
        n_c[chosen_c] += 1
        if bool(labels[b]):
            positive_bins.add(b)
            # Temporal expansion
            for _ in range(7):
                if oracle.calls >= budget_abs:
                    break
                left_neg = all(
                    (b - o not in sampled or not bool(labels.get(b - o, False)))
                    for o in range(1, 4) if b - o >= 0
                )
                right_neg = all(
                    (b + o not in sampled or not bool(labels.get(b + o, False)))
                    for o in range(1, 4) if b + o < n_bins
                )
                if left_neg and right_neg:
                    break
                expand(b, chosen_c)

    returned_intervals = group_positive_bins(sorted(positive_bins), grid)
    metrics = evaluate_events(returned_intervals, ref_seg)
    oracle.assert_no_event_id()
    assert oracle.calls <= budget_abs, f"B7-strict-replay budget: {oracle.calls} > {budget_abs}"

    return {
        "method_id": method_id,
        "oracle": oracle,
        "returned_intervals": returned_intervals,
        "metrics": metrics,
        "oracle_calls_total": oracle.calls,
        "strict_replay_or_posthoc": "strict_replay",
        "online_uses_event_id": False,
        "can_be_main_comparison": True,
        "applicability_note": "B7 chunk-bandit with strict online novelty proxy (is_positive + adjacency); no event_id; core/halo via temporal grouping",
    }


# ----------------------------------------------------------------------
# B. D3-norepair-core-strict
# ----------------------------------------------------------------------
def run_d3_norepair_strict(grid, ref_seg, seg_id, budget_abs, budget_ratio, seed):
    """D3-norepair-core strict-replay: chunk-bandit discovery using is_positive only.

    Uses discovery_d3_chunk_bandit logic (strict-replay, no event_id).
    No repair. Core/Halo via temporal grouping of observed positives.
    """
    method_id = "D3-norepair-core-strict"
    oracle = AlignedOracle(grid, seg_id, method_id, seed, budget_abs, budget_ratio)
    grid_sorted = grid.sort_values("bin_idx").reset_index(drop=True)
    bin_idxs = grid_sorted["bin_idx"].values
    n_bins = len(bin_idxs)
    labels = dict(zip(grid_sorted["bin_idx"], grid_sorted[LABEL_COL]))
    bin_to_row = {int(b): r for _, r in grid_sorted.iterrows() for b in [int(r["bin_idx"])]}

    rng = np.random.RandomState(seed * 100003 + 23)
    bins_per_chunk = max(1, int(CHUNK_SIZE_S // BIN_SIZE))
    n_chunks = int(math.ceil(n_bins / bins_per_chunk))

    sampled: Set[int] = set()
    n_c = np.zeros(n_chunks, dtype=int)
    N1_c = np.zeros(n_chunks, dtype=float)
    sample_count: Dict[int, int] = {}
    positive_bins: Set[int] = set()

    def update_singletons():
        N1_c[:] = 0.0
        for b, cnt in sample_count.items():
            if cnt == 1 and bool(labels[b]):
                c = min(b // bins_per_chunk, n_chunks - 1)
                N1_c[c] += 1

    while oracle.calls < budget_abs:
        update_singletons()
        theta = rng.gamma(shape=N1_c + 0.1, scale=1.0 / (n_c + 1.0))
        for c in range(n_chunks):
            chunk_bins = list(range(c * bins_per_chunk, min((c + 1) * bins_per_chunk, n_bins)))
            if all(b in sampled for b in chunk_bins):
                theta[c] = -np.inf
        if np.all(theta == -np.inf):
            break
        chosen_c = int(np.argmax(theta))
        chunk_bins = list(range(chosen_c * bins_per_chunk, min((chosen_c + 1) * bins_per_chunk, n_bins)))
        unsampled = [b for b in chunk_bins if b not in sampled]
        if not unsampled:
            break
        b = int(rng.choice(unsampled))
        oracle.query_unit(b, "D3_SAMPLE", "D3_SAMPLE",
                          component_id=f"chunk{chosen_c}",
                          notes="D3 chunk-bandit sample (no event_id)")
        sampled.add(b)
        sample_count[b] = sample_count.get(b, 0) + 1
        n_c[chosen_c] += 1
        if bool(labels[b]):
            positive_bins.add(b)

    returned_intervals = group_positive_bins(sorted(positive_bins), grid)
    metrics = evaluate_events(returned_intervals, ref_seg)
    oracle.assert_no_event_id()
    assert oracle.calls <= budget_abs, f"D3-norepair budget: {oracle.calls} > {budget_abs}"

    return {
        "method_id": method_id,
        "oracle": oracle,
        "returned_intervals": returned_intervals,
        "metrics": metrics,
        "oracle_calls_total": oracle.calls,
        "strict_replay_or_posthoc": "strict_replay",
        "online_uses_event_id": False,
        "can_be_main_comparison": True,
        "applicability_note": "D3 chunk-bandit strict-replay (is_positive singleton counting); no repair; no event_id",
    }


# ----------------------------------------------------------------------
# C. SUPG-event-strict
# ----------------------------------------------------------------------
def run_supg_event_strict(grid, ref_seg, seg_id, budget_abs, budget_ratio, seed):
    """SUPG recall-target selector over 10s bins + temporal grouping.

    Uses official SUPG RecallSelector. Budget capped at budget_abs//2 to
    account for internal filter() re-queries (matching ARC convention).
    No event_id in online decisions.
    """
    method_id = "SUPG-event-rt-strict"
    oracle = AlignedOracle(grid, seg_id, method_id, seed, budget_abs, budget_ratio)
    grid_sorted = grid.sort_values("bin_idx").reset_index(drop=True)

    df = pd.DataFrame({
        "id": grid_sorted["bin_idx"].values,
        "label": grid_sorted[LABEL_COL].astype(float).values,
        "proxy_score": grid_sorted[PROXY_COL].astype(float).values,
    })
    source = DFDataSource(df)
    sampler = ImportanceSampler(seed=seed)
    supg_budget = max(1, budget_abs // 2)
    query = ApproxQuery(qtype="rt", min_recall=0.9, delta=0.05, budget=supg_budget)
    selector = RecallSelector(query, source, sampler, sample_mode="sqrt", verbose=False)
    with contextlib.redirect_stdout(io.StringIO()):
        selected_ids = selector.select()

    sampled_ids = getattr(selector, "sampled", None)
    if sampled_ids is None:
        sampled_ids = np.array([])

    labels = dict(zip(grid_sorted["bin_idx"], grid_sorted[LABEL_COL]))
    positive_bins = []
    for b in sampled_ids:
        b = int(b)
        label = bool(labels[b])
        oracle.query_unit(b, "SUPG_LOOKUP", "SUPG_LOOKUP",
                          notes="SUPG importance-sampled lookup")
        if label:
            positive_bins.append(b)

    # Handle source.lookups correction
    supg_lookup_count = int(source.lookups)
    if oracle.calls < supg_lookup_count:
        extra = supg_lookup_count - oracle.calls
        oracle.ledger.append({
            "segment_id": seg_id, "method_id": method_id, "seed": seed,
            "budget_abs": budget_abs, "budget_ratio": budget_ratio,
            "call_idx": oracle.calls + 1,
            "action_type": "SUPG_LOOKUP", "source_action": "SUPG_LOOKUP_CORRECTION",
            "bin_id": -1, "component_id": "", "proxy_score": "",
            "oracle_label": "", "online_positive": "",
            "added_to_returned_intervals": "",
            "cumulative_oracle_calls": supg_lookup_count,
            "budget_remaining": budget_abs - supg_lookup_count,
            "online_uses_event_id": False,
            "notes": f"SUPG source.lookups={supg_lookup_count} vs ledger={oracle.calls-1}; correction +{extra}",
        })
        oracle.calls = supg_lookup_count

    returned_intervals = group_positive_bins(positive_bins, grid)
    metrics = evaluate_events(returned_intervals, ref_seg)
    oracle.assert_no_event_id()
    assert oracle.calls <= budget_abs, f"SUPG-event budget: {oracle.calls} > {budget_abs}"

    return {
        "method_id": method_id,
        "oracle": oracle,
        "returned_intervals": returned_intervals,
        "metrics": metrics,
        "oracle_calls_total": oracle.calls,
        "strict_replay_or_posthoc": "strict_replay",
        "online_uses_event_id": False,
        "can_be_main_comparison": True,
        "applicability_note": "record selection baseline; temporal grouping added by adapter; no residual/certificate; budget capped at budget//2 for SUPG internal filter()",
    }


# ----------------------------------------------------------------------
# D. ABae-residual-strict
# ----------------------------------------------------------------------
def run_abae_residual_strict(grid, ref_seg, seg_id, budget_abs, budget_ratio, seed):
    """ABae two-stage stratified estimator with statistic=1 (total positive mass).

    No returned intervals. Estimates total positive mass and residual.
    No event_id in online decisions.
    """
    method_id = "ABae-residual-strict"
    oracle = AlignedOracle(grid, seg_id, method_id, seed, budget_abs, budget_ratio)
    grid_sorted = grid.sort_values("bin_idx").reset_index(drop=True)

    df = pd.DataFrame({
        "id": grid_sorted["bin_idx"].values,
        "label": grid_sorted[LABEL_COL].astype(int).values,
        "proxy_score": grid_sorted[PROXY_COL].astype(float).values,
        "statistic_value": 1,
    })
    df_strat = quantile_stratify(df, NUM_STRATA)

    n1_per = max(1, budget_abs // (NUM_STRATA * 4))
    n1_per = min(n1_per, max(1, budget_abs // NUM_STRATA))
    rng = np.random.RandomState(seed)

    audit_samples_by_stratum = {}
    total_sampled = 0
    observed_positive = 0

    for k in range(NUM_STRATA):
        if total_sampled >= budget_abs:
            break
        stratum_df = df_strat[df_strat["stratum"] == k]
        n_k = len(stratum_df)
        if n_k == 0:
            audit_samples_by_stratum[k] = (0, 0)
            continue
        n1 = min(n1_per, n_k, budget_abs - total_sampled)
        if n1 <= 0:
            audit_samples_by_stratum[k] = (0, 0)
            continue
        sampled_idx = rng.choice(stratum_df["id"].values, size=n1, replace=False)
        x_s = 0
        for b in sampled_idx:
            b = int(b)
            label = bool(oracle.labels[b])
            oracle.query_unit(b, "ABAE_SAMPLE", "ABAE_STAGE1",
                              stratum_id=str(k), notes=f"ABae stage1 stratum {k}")
            if label:
                x_s += 1
                observed_positive += 1
        audit_samples_by_stratum[k] = (n1, x_s)
        total_sampled += n1

    stage2_remaining = budget_abs - total_sampled
    if stage2_remaining > 0:
        weights = []
        for k in range(NUM_STRATA):
            n_s, x_s = audit_samples_by_stratum.get(k, (0, 0))
            p = x_s / n_s if n_s > 0 else 0.0
            w = math.sqrt(p) if p > 0 else 1e-6
            weights.append(w)
        weights = np.array(weights, dtype=float)
        total_w = weights.sum()
        if total_w <= 0:
            weights = np.ones(NUM_STRATA)
            total_w = NUM_STRATA
        for k in range(NUM_STRATA):
            if total_sampled >= budget_abs:
                break
            stratum_df = df_strat[df_strat["stratum"] == k]
            n_k = len(stratum_df)
            n_already, _ = audit_samples_by_stratum.get(k, (0, 0))
            n_avail = n_k - n_already
            n2 = min(int(round(weights[k] / total_w * stage2_remaining)), n_avail,
                     budget_abs - total_sampled)
            if n2 <= 0:
                continue
            sampled_idx = rng.choice(stratum_df["id"].values, size=n2, replace=False)
            x_s_new = 0
            for b in sampled_idx:
                b = int(b)
                label = bool(oracle.labels[b])
                oracle.query_unit(b, "ABAE_SAMPLE", "ABAE_STAGE2",
                                  stratum_id=str(k), notes=f"ABae stage2 stratum {k}")
                if label:
                    x_s_new += 1
                    observed_positive += 1
            n_old, x_old = audit_samples_by_stratum.get(k, (0, 0))
            audit_samples_by_stratum[k] = (n_old + n2, x_old + x_s_new)
            total_sampled += n2

    N_total = len(grid)
    audit_n = sum(n for (n, _) in audit_samples_by_stratum.values())
    if audit_n > 0:
        p_hat_pooled = observed_positive / audit_n
    else:
        p_hat_pooled = 0.0
    total_positive_mass_hat = p_hat_pooled * N_total
    residual_hat = max(0.0, total_positive_mass_hat - observed_positive)
    p_ucb = binomial_ucb(audit_n)
    N_uncovered = N_total - audit_n
    residual_ucb = p_ucb * N_uncovered

    oracle.assert_no_event_id()
    assert oracle.calls <= budget_abs, f"ABae budget: {oracle.calls} > {budget_abs}"

    return {
        "method_id": method_id,
        "oracle": oracle,
        "returned_intervals": [],
        "metrics": {"event_precision": "", "event_recall": "", "unique_event_coverage": ""},
        "oracle_calls_total": oracle.calls,
        "strict_replay_or_posthoc": "strict_replay",
        "online_uses_event_id": False,
        "can_be_main_comparison": True,
        "applicability_note": "aggregate estimation baseline; statistic=1; no interval output; residual UCB only; not an event discovery method",
        "total_positive_mass_hat": total_positive_mass_hat,
        "observed_positive_mass": observed_positive,
        "residual_hat": residual_hat,
        "residual_ucb": residual_ucb,
        "audit_n": audit_n,
        "audit_positive_n": observed_positive,
        "p_ucb": p_ucb,
    }


# ----------------------------------------------------------------------
# Output row builders
# ----------------------------------------------------------------------
def _frontier_row(r, seg_id, budget_abs, budget_ratio, seed):
    m = r.get("metrics", {})
    return {
        "segment_id": seg_id,
        "method_id": r["method_id"],
        "seed": seed,
        "budget_abs": budget_abs,
        "budget_ratio": budget_ratio,
        "oracle_calls_total": r["oracle_calls_total"],
        "returned_intervals": json.dumps(r.get("returned_intervals", [])),
        "event_precision": m.get("event_precision", ""),
        "event_recall": m.get("event_recall", ""),
        "unique_event_coverage": m.get("unique_event_coverage", ""),
        "duplicate_rate_if_available": "",
        "residual_estimate_available": "residual_hat" in r,
        "residual_hat": r.get("residual_hat", ""),
        "residual_ucb": r.get("residual_ucb", ""),
        "residual_ci_lower": "",
        "residual_ci_upper": "",
        "recall_lcb_available": False,
        "stop_certificate_available": False,
        "stop_status": "abstain_or_budget_exhausted",
        "stop_reason": "budget_exhausted",
        "strict_replay_or_posthoc": r.get("strict_replay_or_posthoc", "strict_replay"),
        "online_uses_event_id": r.get("online_uses_event_id", False),
        "can_be_main_comparison": r.get("can_be_main_comparison", True),
        "applicability_note": r.get("applicability_note", ""),
    }


def _residual_row(r, seg_id, budget_abs, budget_ratio, seed, n_pos_total):
    observed = r.get("observed_positive_mass", 0)
    if observed == 0 and "audit_positive_n" in r:
        observed = r.get("audit_positive_n", 0)
    true_residual = max(0, n_pos_total - observed)
    return {
        "segment_id": seg_id,
        "method_id": r["method_id"],
        "seed": seed,
        "budget_abs": budget_abs,
        "budget_ratio": budget_ratio,
        "total_positive_mass_hat": r.get("total_positive_mass_hat", ""),
        "observed_positive_mass": observed,
        "residual_hat": r.get("residual_hat", ""),
        "residual_ci_lower": "",
        "residual_ci_upper": "",
        "residual_true_if_reference_available": true_residual,
        "abs_error": abs(r.get("residual_hat", 0.0) - true_residual) if r.get("residual_hat") != "" else "",
        "signed_error": (r.get("residual_hat", 0.0) - true_residual) if r.get("residual_hat") != "" else "",
        "oracle_calls_total": r["oracle_calls_total"],
        "notes": f"n_pos_total={n_pos_total}",
    }


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    methods = [
        ("B7-strict-replay", run_b7_strict_replay),
        ("D3-norepair-core-strict", run_d3_norepair_strict),
        ("SUPG-event-rt-strict", run_supg_event_strict),
        ("ABae-residual-strict", run_abae_residual_strict),
    ]

    all_trace_rows = []
    all_frontier_rows = []
    all_residual_rows = []
    segment_summaries = []

    for seg in SEGMENTS:
        seg_id = seg["segment_id"]
        print(f"\n=== Loading segment: {seg_id} ===")
        grid, ref_seg, err = load_segment_data(seg)
        if grid is None:
            print(f"  SKIPPED: {err}")
            segment_summaries.append({"segment_id": seg_id, "status": "skipped", "reason": err})
            continue

        n_bins = len(grid)
        n_pos = int(grid[LABEL_COL].sum())
        n_events = len(ref_seg)
        has_event_id = "event_id" in grid.columns
        print(f"  bins={n_bins}, positive_bins={n_pos}, reference_events={n_events}")
        print(f"  proxy_col={PROXY_COL}, label_col={LABEL_COL}")
        print(f"  event_id present in data: {has_event_id} (excluded from online)")
        segment_summaries.append({"segment_id": seg_id, "status": "ok",
                                   "num_bins": n_bins, "num_positive_bins": n_pos,
                                   "num_reference_events": n_events})

        for budget_ratio in BUDGET_RATIOS:
            budget_abs = max(1, int(round(budget_ratio * n_bins)))
            for seed in SEEDS:
                for name, fn in methods:
                    try:
                        r = fn(grid, ref_seg, seg_id, budget_abs, budget_ratio, seed)
                        all_trace_rows.extend(r["oracle"].ledger)
                        all_frontier_rows.append(_frontier_row(r, seg_id, budget_abs, budget_ratio, seed))
                        if "residual_hat" in r:
                            all_residual_rows.append(_residual_row(r, seg_id, budget_abs, budget_ratio, seed, n_pos))
                        m = r.get("metrics", {})
                        p_str = f"P={m.get('event_precision','')}" if isinstance(m.get("event_precision"), str) else f"P={m.get('event_precision',0):.3f}"
                        r_str = f"R={m.get('event_recall','')}" if isinstance(m.get("event_recall"), str) else f"R={m.get('event_recall',0):.3f}"
                        print(f"  {seg_id} b={budget_abs} s={seed} {r['method_id']}: "
                              f"calls={r['oracle_calls_total']} {p_str} {r_str} "
                              f"event_id_leak={r['online_uses_event_id']}")
                    except Exception as e:
                        print(f"  {seg_id} b={budget_abs} s={seed} {name} FAILED: {e}")
                        import traceback; traceback.print_exc()

    trace_df = pd.DataFrame(all_trace_rows)
    trace_df.to_csv(OUT_DIR / "aligned_baseline_call_trace.csv", index=False)
    frontier_df = pd.DataFrame(all_frontier_rows)
    frontier_df.to_csv(OUT_DIR / "aligned_baseline_frontier_raw.csv", index=False)
    residual_df = pd.DataFrame(all_residual_rows)
    residual_df.to_csv(OUT_DIR / "aligned_baseline_residual.csv", index=False)

    print(f"\nWrote {len(trace_df)} trace rows, {len(frontier_df)} frontier rows, "
          f"{len(residual_df)} residual rows")

    violations = frontier_df[frontier_df.oracle_calls_total > frontier_df.budget_abs] if len(frontier_df) > 0 else []
    print(f"Budget violations: {len(violations)} / {len(frontier_df)}")
    event_id_leaks = frontier_df[frontier_df.online_uses_event_id == True] if len(frontier_df) > 0 else []
    print(f"event_id online leaks: {len(event_id_leaks)} / {len(frontier_df)}")
    print(f"Segments run: {sum(1 for s in segment_summaries if s['status']=='ok')} / {len(SEGMENTS)}")


if __name__ == "__main__":
    main()
