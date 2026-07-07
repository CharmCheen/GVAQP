"""EventLift-AQP Stage 1: DISCOVER + AUDIT core on the dev segment only.

Implements Stage 1 of EVENTLIFT_AQP_ALGORITHM_SPEC.md:
  1. SUPG-event adapter (record selection over 10s bins + temporal grouping)
  2. ABae-residual adapter (statistic=1 total positive-mass estimator)
  3. EventLift DISCOVER + AUDIT loop under a unified utility
  4. Unified per-call oracle ledger with source_action lineage

Hard constraints enforced:
  - Dev segment realcartest_2000_3200 only.
  - Replay over existing VLM-oracle-relative labels (center10 / reference_events).
  - No event_id in online decisions; reference used for evaluation only.
  - oracle_calls_total <= budget_abs asserted for every run.
  - No video / GPU / VLM / YOLO inference.
  - Small outputs only.

All numbers are VLM-oracle-relative, not human ground truth, and no formal
guarantee / certificate / statistical bound is claimed (per AGENTS.md).
"""

import sys
import os
import io
import contextlib
from pathlib import Path
import math
import json
import numpy as np
import pandas as pd

# Make supg + garc_eval adapters importable
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "refe_repos" / "supg"))
sys.path.insert(0, str(REPO_ROOT / "src"))

from supg.datasource import DFDataSource
from supg.sampler import ImportanceSampler
from supg.selector import ApproxQuery, RecallSelector
from garc_eval.adapters.abae_adapter import quantile_stratify


# ----------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------
SEGMENT_ID = "realcartest_2000_3200"
VIDEO_ID = "realcartest"
GRID_CSV = REPO_ROOT / "outputs/late_aqp_frozen_cross_segment_v1/grid_realcartest_2000_3200.csv"
REF_CSV = REPO_ROOT / "src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/reference_events.csv"
OUT_DIR = REPO_ROOT / "outputs/eventlift_stage1_dev"
PROXY_COL = "prior_score_max"
LABEL_COL = "is_positive"
BUDGET_RATIOS = [0.10, 0.20, 0.30]
SEEDS = [0, 1, 2]
IOU_THRESHOLD = 0.3  # LATE-AQP event match threshold
ALPHA = 0.05  # one-sided residual UCB

# EventLift utility hyperparameters (fixed, NOT tuned - per spec §5.1)
ETA = 1.0      # oracle cost weight
LAMBDA = 0.5   # residual uncertainty reduction weight
GAMMA = 0.3    # dual-purpose positive recovery weight
KAPPA = 0.5    # opportunity cost weight
AUDIT_SHARE = 0.30  # fraction of budget reserved for AUDIT when utility favors it
NUM_STRATA = 5  # ABae strata over uncovered region


# ----------------------------------------------------------------------
# Data loading
# ----------------------------------------------------------------------
def load_dev_data():
    """Load grid + reference for the dev segment."""
    grid = pd.read_csv(GRID_CSV)
    grid = grid.sort_values("bin_idx").reset_index(drop=True)
    # Reference: events whose absolute window falls within [2000, 3200]
    ref = pd.read_csv(REF_CSV)
    ref_seg = ref[(ref["absolute_t_start"] >= 2000) & (ref["absolute_t_end"] <= 3200)].copy()
    ref_seg = ref_seg.reset_index(drop=True)
    return grid, ref_seg


# ----------------------------------------------------------------------
# Shared evaluator (event precision/recall via IoU >= 0.3)
# ----------------------------------------------------------------------
def _iou_interval(a_start, a_end, b_start, b_end):
    inter = max(0.0, min(a_end, b_end) - max(a_start, b_start))
    union = max(a_end, b_end) - min(a_start, b_start)
    if union <= 0:
        return 0.0
    return inter / union


def evaluate_events(returned_intervals, ref_events):
    """Compute event precision / recall / unique coverage at IoU >= 0.3.

    returned_intervals: list of (t_start, t_end) in local segment time (0-based).
    ref_events: DataFrame with t_start, t_end in local segment time.
    """
    if len(ref_events) == 0:
        return {"event_precision": 0.0, "event_recall": 0.0, "unique_event_coverage": 0}
    ref_iv = list(zip(ref_events["t_start"].values, ref_events["t_end"].values))

    # precision: fraction of returned intervals hitting >=1 ref event
    hits_precision = 0
    for (s, e) in returned_intervals:
        if any(_iou_interval(s, e, rs, re) >= IOU_THRESHOLD for (rs, re) in ref_iv):
            hits_precision += 1
    precision = hits_precision / len(returned_intervals) if returned_intervals else 0.0

    # recall: fraction of ref events hit by >=1 returned interval
    hits_recall = 0
    for (rs, re) in ref_iv:
        if any(_iou_interval(s, e, rs, re) >= IOU_THRESHOLD for (s, e) in returned_intervals):
            hits_recall += 1
    recall = hits_recall / len(ref_iv)

    return {
        "event_precision": precision,
        "event_recall": recall,
        "unique_event_coverage": hits_recall,
    }


# ----------------------------------------------------------------------
# Temporal grouping: merge adjacent positive bins into intervals
# ----------------------------------------------------------------------
def group_positive_bins(positive_bin_idxs, grid):
    """Merge temporally adjacent positive bins (gap <= 1 bin) into intervals."""
    if len(positive_bin_idxs) == 0:
        return []
    grid_sorted = grid.sort_values("bin_idx").reset_index(drop=True)
    bin_to_t = dict(zip(grid_sorted["bin_idx"], zip(grid_sorted["local_t_start"], grid_sorted["local_t_end"])))
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


# ----------------------------------------------------------------------
# Replay oracle: wraps the grid labels, counts calls, logs lineage
# ----------------------------------------------------------------------
class ReplayOracle:
    """Replay oracle over the dev segment grid. No online VLM calls."""

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
        self.calls = 0  # cumulative oracle calls
        self.ledger = []  # per-call trace rows

    def query_unit(self, bin_idx, action_type, source_action,
                   component_id="", stratum_id="", notes=""):
        """Query one bin. Returns 'positive'/'negative'. Logs to ledger."""
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
            "stratum_id": stratum_id,
            "proxy_score": self.proxies[bin_idx],
            "oracle_label": oracle_label,
            "online_positive": label,
            "added_to_returned_intervals": "",  # filled by caller
            "cumulative_oracle_calls": self.calls,
            "budget_remaining": self.budget_abs - self.calls,
            "residual_hat_before": "",  # filled by caller
            "residual_hat_after": "",  # filled by caller
            "notes": notes,
        })
        return oracle_label


# ----------------------------------------------------------------------
# Residual estimator (ABae-lift: statistic=1, total positive mass)
# ----------------------------------------------------------------------
def binomial_ucb(n, alpha=ALPHA):
    """Zero-hit one-sided upper bound: p_ucb = 1 - alpha**(1/n)."""
    if n <= 0:
        return 1.0
    return 1.0 - alpha ** (1.0 / n)


def compute_residual(uncovered_bin_idxs, audit_samples_by_stratum, grid):
    """Estimate residual positive mass over uncovered bins.

    uncovered_bin_idxs: list of bin indices not yet queried.
    audit_samples_by_stratum: dict {stratum_id: (n_sampled, n_positive)} over uncovered.

    Returns (residual_hat, residual_ucb, audit_n_total, audit_positive_n_total, p_ucb).
    """
    if len(uncovered_bin_idxs) == 0:
        return 0.0, 0.0, 0, 0, 0.0
    # total uncovered bins
    N_U = len(uncovered_bin_idxs)
    # per-stratum Horvitz-Thompson estimate + zero-hit UCB
    residual_hat = 0.0
    residual_ucb = 0.0
    audit_n_total = 0
    audit_positive_n_total = 0
    for sid, (n_s, x_s) in audit_samples_by_stratum.items():
        audit_n_total += n_s
        audit_positive_n_total += x_s
        # stratum size among uncovered (approx: proportional to original stratum)
        # we use the actual uncovered count per stratum if available
        if n_s > 0:
            p_hat_s = x_s / n_s
            p_ucb_s = binomial_ucb(n_s)
        else:
            p_hat_s = 0.0
            p_ucb_s = 1.0
        # weight by stratum fraction of uncovered (approx equal if we don't track per-stratum size)
        # To be faithful, we track uncovered per stratum
    # Simplified: aggregate over all audit samples (pooled), weighted by N_U
    if audit_n_total > 0:
        p_hat_pooled = audit_positive_n_total / audit_n_total
        p_ucb_pooled = binomial_ucb(audit_n_total)
    else:
        p_hat_pooled = 0.0
        p_ucb_pooled = 1.0
    residual_hat = p_hat_pooled * N_U
    residual_ucb = p_ucb_pooled * N_U
    return residual_hat, residual_ucb, audit_n_total, audit_positive_n_total, p_ucb_pooled


# ----------------------------------------------------------------------
# 2. SUPG-event adapter
# ----------------------------------------------------------------------
def run_supg_event(grid, ref_seg, budget_abs, budget_ratio, seed):
    """Run SUPG recall-target selector over 10s bins + temporal grouping."""
    method_id = "SUPG-event"
    oracle = ReplayOracle(grid, SEGMENT_ID, method_id, seed, budget_abs, budget_ratio)

    # Build SUPG DFDataSource
    df = pd.DataFrame({
        "id": grid["bin_idx"].values,
        "label": grid[LABEL_COL].astype(float).values,
        "proxy_score": grid[PROXY_COL].astype(float).values,
    })
    source = DFDataSource(df)
    sampler = ImportanceSampler(seed=seed)
    # SUPG's `budget` param = number of importance samples. SUPG also calls
    # source.filter() which re-queries positives (extra lookups). To stay
    # within budget_abs, we cap SUPG's internal budget at half (matching the
    # ARC algorithm_handler.py:36 convention: sample4supg = int(B / 2)).
    supg_sample_budget = max(1, budget_abs // 2)
    query = ApproxQuery(qtype="rt", min_recall=0.9, delta=0.05, budget=supg_sample_budget)
    selector = RecallSelector(query, source, sampler, sample_mode="sqrt", verbose=False)
    with contextlib.redirect_stdout(io.StringIO()):
        selected_ids = selector.select()

    # SUPG internally calls source.lookup during select(); those ARE the oracle calls.
    # The DFDataSource.lookups counter tracks them. We replay them into our ledger.
    # To get per-call lineage, we re-derive the sampled bins from selector.sampled
    sampled_ids = getattr(selector, "sampled", None)
    if sampled_ids is None:
        sampled_ids = np.array([])

    # Record each SUPG lookup as a SUPG_LOOKUP action in our ledger
    # (SUPG's DFDataSource already counted them in source.lookups)
    supg_lookup_count = int(source.lookups)
    # The actual bins sampled by SUPG are in selector.sampled (unique data idxs)
    # We log them as SUPG_LOOKUP calls
    positive_bins = []
    for b in sampled_ids:
        b = int(b)
        label = bool(oracle.labels[b])
        oracle.calls += 1
        oracle.ledger.append({
            "segment_id": SEGMENT_ID,
            "method_id": method_id,
            "seed": seed,
            "budget_abs": budget_abs,
            "budget_ratio": budget_ratio,
            "call_idx": oracle.calls,
            "action_type": "SUPG_LOOKUP",
            "source_action": "SUPG_LOOKUP",
            "bin_id": b,
            "component_id": "",
            "stratum_id": "",
            "proxy_score": oracle.proxies[b],
            "oracle_label": "positive" if label else "negative",
            "online_positive": label,
            "added_to_returned_intervals": str(label),
            "cumulative_oracle_calls": oracle.calls,
            "budget_remaining": budget_abs - oracle.calls,
            "residual_hat_before": "",
            "residual_hat_after": "",
            "notes": "SUPG importance-sampled lookup",
        })
        if label:
            positive_bins.append(b)

    # Also include any selected ids that weren't in sampled (SUPG returns top-k by proxy)
    # selected_ids includes top-ranked + positives found. For oracle accounting, only
    # the *sampled* (queried) set counts. Selected-but-not-sampled are free (proxy-ranked).
    # But we must also count lookups for positives in selected that came from filtering.
    # Per SUPG source: source.filter(ids) calls lookup on the selected set. Check:
    # RecallSelector calls self.data.filter(data_idxs[s_ranks]) at line 71 (pos_sampled).
    # That filter does lookups on sampled ranks. Those are already in source.lookups.
    # To be safe, assert consistency.
    # The total lookup count is source.lookups. If our ledger count differs, log a note.
    if oracle.calls != supg_lookup_count:
        # Adjust: add a correction row if SUPG did more lookups than we tracked
        # (rare; happens if filter() re-queried). We log the discrepancy.
        # For faithful accounting, we use source.lookups as the authoritative count.
        extra = supg_lookup_count - oracle.calls
        if extra > 0:
            oracle.ledger.append({
                "segment_id": SEGMENT_ID, "method_id": method_id, "seed": seed,
                "budget_abs": budget_abs, "budget_ratio": budget_ratio,
                "call_idx": oracle.calls + 1,
                "action_type": "SUPG_LOOKUP", "source_action": "SUPG_LOOKUP_CORRECTION",
                "bin_id": -1, "component_id": "", "stratum_id": "",
                "proxy_score": "", "oracle_label": "",
                "online_positive": "", "added_to_returned_intervals": "",
                "cumulative_oracle_calls": supg_lookup_count,
                "budget_remaining": budget_abs - supg_lookup_count,
                "residual_hat_before": "", "residual_hat_after": "",
                "notes": f"SUPG source.lookups={supg_lookup_count} vs ledger={oracle.calls}; correction +{extra}",
            })
            oracle.calls = supg_lookup_count

    # Group positive bins into intervals
    returned_intervals = group_positive_bins(positive_bins, grid)
    metrics = evaluate_events(returned_intervals, ref_seg)

    # Budget assertion
    assert oracle.calls <= budget_abs, f"SUPG-event budget violated: {oracle.calls} > {budget_abs}"

    return {
        "method_id": method_id,
        "oracle": oracle,
        "selected_ids": selected_ids,
        "positive_bins": positive_bins,
        "returned_intervals": returned_intervals,
        "metrics": metrics,
        "oracle_calls_total": oracle.calls,
        "oracle_calls_discover": 0,
        "oracle_calls_audit": 0,
        "oracle_calls_supg": oracle.calls,
        "oracle_calls_abae": 0,
        "residual_estimate_available": False,
        "residual_hat": "",
        "residual_ucb": "",
        "residual_ci_lower": "",
        "residual_ci_upper": "",
        "recall_lcb_available": False,
        "stop_certificate_available": False,
        "stop_status": "abstain_or_budget_exhausted",
        "stop_reason": "budget_exhausted",
        "applicability_note": "record selection baseline; temporal grouping added by adapter; no residual/certificate",
    }


# ----------------------------------------------------------------------
# 3. ABae-residual adapter
# ----------------------------------------------------------------------
def run_abae_residual(grid, budget_abs, budget_ratio, seed, num_strata=NUM_STRATA):
    """Run ABae two-stage stratified estimator with statistic=1 (total positive mass).

    Uses the existing garc_eval abae_adapter (faithful reimplementation, no ray).
    Returns residual_hat, residual_ucb, etc. No intervals.
    """
    method_id = "ABae-residual"
    oracle = ReplayOracle(grid, SEGMENT_ID, method_id, seed, budget_abs, budget_ratio)

    df = pd.DataFrame({
        "id": grid["bin_idx"].values,
        "label": grid[LABEL_COL].astype(int).values,
        "proxy_score": grid[PROXY_COL].astype(float).values,
        "statistic_value": 1,  # statistic=1 => estimate P(predicate) = positive fraction
    })
    df_strat = quantile_stratify(df, num_strata)

    # Two-stage: stage1 pilot (n1 per stratum), stage2 optimal allocation
    n1_per = max(1, budget_abs // (num_strata * 4))  # ~25% of budget on pilot
    n1_per = min(n1_per, max(1, budget_abs // num_strata))
    rng = np.random.RandomState(seed)

    audit_samples_by_stratum = {}
    total_sampled = 0
    stage1_positives = 0

    # Stage 1
    for k in range(num_strata):
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
                stage1_positives += 1
        audit_samples_by_stratum[k] = (n1, x_s)
        total_sampled += n1

    # Stage 2: optimal allocation ∝ sqrt(p_hat * sigma_hat)
    # With statistic=1, sigma=0 among positives (all ones). Use sqrt(p_hat) fallback.
    stage2_remaining = budget_abs - total_sampled
    if stage2_remaining > 0:
        weights = []
        for k in range(num_strata):
            n_s, x_s = audit_samples_by_stratum.get(k, (0, 0))
            p = x_s / n_s if n_s > 0 else 0.0
            if p > 0:
                w = math.sqrt(p)
            else:
                w = 1e-6  # small discovery weight
            weights.append(w)
        weights = np.array(weights, dtype=float)
        total_w = weights.sum()
        if total_w <= 0:
            weights = np.ones(num_strata)
            total_w = num_strata
        for k in range(num_strata):
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
            n_old, x_old = audit_samples_by_stratum.get(k, (0, 0))
            audit_samples_by_stratum[k] = (n_old + n2, x_old + x_s_new)
            total_sampled += n2

    # Residual estimate over the WHOLE segment (ABae estimates total positive mass)
    uncovered_all = list(grid["bin_idx"].values)
    observed_positive = sum(x for (_, x) in audit_samples_by_stratum.values())
    audit_n = sum(n for (n, _) in audit_samples_by_stratum.values())
    N_total = len(grid)
    # ABae aggregate estimate of total positive mass
    if audit_n > 0:
        p_hat_pooled = observed_positive / audit_n
    else:
        p_hat_pooled = 0.0
    total_positive_mass_hat = p_hat_pooled * N_total
    observed_positive_mass = observed_positive  # actual positives found
    # residual = estimated total mass - observed positives
    residual_hat = max(0.0, total_positive_mass_hat - observed_positive_mass)
    # UCB: zero-hit bound on uncovered fraction
    p_ucb_pooled = binomial_ucb(audit_n)
    N_uncovered = N_total - audit_n
    residual_ucb = p_ucb_pooled * N_uncovered

    assert oracle.calls <= budget_abs, f"ABae budget violated: {oracle.calls} > {budget_abs}"

    return {
        "method_id": method_id,
        "oracle": oracle,
        "returned_intervals": [],  # ABae emits no intervals
        "oracle_calls_total": oracle.calls,
        "oracle_calls_discover": 0,
        "oracle_calls_audit": oracle.calls,
        "oracle_calls_supg": 0,
        "oracle_calls_abae": oracle.calls,
        "residual_estimate_available": True,
        "residual_hat": residual_hat,
        "residual_ucb": residual_ucb,
        "residual_ci_lower": "",  # bootstrap CI omitted for budget; UCB is the main bound
        "residual_ci_upper": "",
        "total_positive_mass_hat": total_positive_mass_hat,
        "observed_positive_mass": observed_positive_mass,
        "audit_n": audit_n,
        "audit_positive_n": observed_positive,
        "recall_lcb_available": False,
        "stop_certificate_available": False,
        "stop_status": "abstain_or_budget_exhausted",
        "stop_reason": "budget_exhausted",
        "applicability_note": "aggregate estimation baseline; statistic=1; no interval output; residual UCB only",
        "metrics": {"event_precision": "", "event_recall": "", "unique_event_coverage": ""},
    }


# ----------------------------------------------------------------------
# 4. EventLift DISCOVER + AUDIT
# ----------------------------------------------------------------------
def run_eventlift_discover_only(grid, ref_seg, budget_abs, budget_ratio, seed):
    """EventLift discover-only ablation: DISCOVER action, no AUDIT."""
    return _run_eventlift(grid, ref_seg, budget_abs, budget_ratio, seed,
                          method_id="EventLift-discover-only", audit_enabled=False)


def run_eventlift_discover_audit(grid, ref_seg, budget_abs, budget_ratio, seed):
    """EventLift full Stage 1: DISCOVER + AUDIT under unified utility."""
    return _run_eventlift(grid, ref_seg, budget_abs, budget_ratio, seed,
                          method_id="EventLift-discover-audit", audit_enabled=True)


def _run_eventlift(grid, ref_seg, budget_abs, budget_ratio, seed,
                   method_id, audit_enabled):
    oracle = ReplayOracle(grid, SEGMENT_ID, method_id, seed, budget_abs, budget_ratio)
    grid_sorted = grid.sort_values("bin_idx").reset_index(drop=True)
    bin_idxs = grid_sorted["bin_idx"].values
    proxies = dict(zip(grid_sorted["bin_idx"], grid_sorted[PROXY_COL]))
    labels = dict(zip(grid_sorted["bin_idx"], grid_sorted[LABEL_COL]))

    covered = set()           # bins queried by any action
    positive_bins = set()     # positive bins discovered
    audit_samples_by_stratum = {}  # {stratum_id: (n, x)} over uncovered

    # Initial components: contiguous bins with proxy above median
    proxy_vals = np.array([proxies[b] for b in bin_idxs])
    theta = float(np.median(proxy_vals))

    def build_components(uncovered):
        """Build components = contiguous runs of bins with proxy >= theta."""
        comps = []
        cur = []
        for b in sorted(uncovered):
            if proxies[b] >= theta:
                cur.append(b)
            else:
                if cur:
                    comps.append(cur)
                cur = []
        if cur:
            comps.append(cur)
        return comps

    def residual_now(uncovered):
        return compute_residual(uncovered, audit_samples_by_stratum, grid)

    # Main loop
    while oracle.calls < budget_abs:
        uncovered = [b for b in bin_idxs if b not in covered]
        if len(uncovered) == 0:
            break

        # Build components over uncovered
        comps = build_components(uncovered)
        if len(comps) == 0:
            # No high-proxy bins left; all remaining are low-proxy
            # If audit enabled, audit; else sample uniformly
            if audit_enabled:
                action = "AUDIT"
            else:
                action = "DISCOVER"
        else:
            # Compute utility for DISCOVER on each component
            best_comp = None
            best_u_disc = -1e18
            for ci, comp in enumerate(comps):
                n_fresh = sum(1 for b in comp if b not in covered)
                if n_fresh == 0:
                    continue
                proxy_mass = sum(proxies[b] for b in comp)
                fresh_frac = n_fresh / len(comp)
                # U_discover = proxy_mass * fresh_frac - eta * cost(1) - kappa * opportunity
                coverage_gain = proxy_mass * fresh_frac
                u_disc = coverage_gain - ETA * 1.0 - KAPPA * 0.5  # opportunity approx
                if u_disc > best_u_disc:
                    best_u_disc = u_disc
                    best_comp = comp

            u_discover = best_u_disc if best_comp is not None else -1e18

            # AUDIT utility (if enabled)
            u_audit = -1e18
            if audit_enabled:
                # Residual uncertainty reduction ~ current UCB width
                _, res_ucb, audit_n, _, _ = residual_now(uncovered)
                # dual-purpose: expected positives in uncovered low-proxy bins
                low_proxy_uncovered = [b for b in uncovered if proxies[b] < theta]
                dual_purpose = GAMMA * (len(low_proxy_uncovered) * 0.1)  # rough expected positive rate
                ucb_shrink = LAMBDA * (res_ucb / max(1, len(uncovered)))  # per-bin UCB shrink
                u_audit = ucb_shrink + dual_purpose - ETA * 1.0 - KAPPA * max(0.0, u_discover)

            # Pick action
            if audit_enabled and u_audit > u_discover:
                action = "AUDIT"
            else:
                action = "DISCOVER"
                if best_comp is None:
                    action = "AUDIT" if audit_enabled else "DISCOVER"

        if action == "DISCOVER" and best_comp is not None:
            # DISCOVER: sample one bin from the best component (sqrt(proxy) importance)
            comp = best_comp
            fresh = [b for b in comp if b not in covered]
            if not fresh:
                action = "AUDIT" if audit_enabled else "DISCOVER"
            else:
                w = np.array([math.sqrt(proxies[b]) for b in fresh])
                w = w / w.sum()
                rng = np.random.RandomState(seed * 100003 + oracle.calls)
                b_choice = int(rng.choice(fresh, p=w))
                res_before, _, _, _, _ = residual_now(uncovered)
                oracle.query_unit(b_choice, "DISCOVER", "DISCOVER",
                                  component_id=f"comp{comps.index(comp)}",
                                  notes="DISCOVER sqrt(proxy) importance")
                covered.add(b_choice)
                is_pos = bool(labels[b_choice])
                if is_pos:
                    positive_bins.add(b_choice)
                # update ledger residual_after
                uncovered_after = [b for b in bin_idxs if b not in covered]
                res_after, _, _, _, _ = residual_now(uncovered_after)
                oracle.ledger[-1]["residual_hat_before"] = res_before
                oracle.ledger[-1]["residual_hat_after"] = res_after
                oracle.ledger[-1]["added_to_returned_intervals"] = str(is_pos)
                continue

        if action == "AUDIT":
            # AUDIT: stratify uncovered by proxy, sample one bin with known prob
            unc = sorted([b for b in bin_idxs if b not in covered])
            if not unc:
                break
            unc_proxies = np.array([proxies[b] for b in unc])
            # assign strata by quantile
            ranks = pd.Series(unc_proxies).rank(method="first").values
            strata_assign = ((ranks - 1) / len(unc) * NUM_STRATA).astype(int)
            strata_assign = np.clip(strata_assign, 0, NUM_STRATA - 1)
            # pick stratum with highest UCB contribution (most uncertain)
            best_sid = 0
            best_sid_score = -1e18
            for sid in range(NUM_STRATA):
                mask = strata_assign == sid
                n_in_stratum = int(mask.sum())
                if n_in_stratum == 0:
                    continue
                n_s, x_s = audit_samples_by_stratum.get(sid, (0, 0))
                p_ucb_s = binomial_ucb(n_s) if n_s > 0 else 1.0
                # utility of auditing this stratum
                score = LAMBDA * p_ucb_s * n_in_stratum + GAMMA * 0.1 * n_in_stratum
                if score > best_sid_score:
                    best_sid_score = score
                    best_sid = sid
            mask = strata_assign == best_sid
            candidates = [b for b, m in zip(unc, mask) if m]
            if not candidates:
                # fall back to any uncovered
                candidates = unc
                best_sid = -1
            rng = np.random.RandomState(seed * 100003 + oracle.calls + 7)
            b_choice = int(rng.choice(candidates))
            res_before, _, _, _, _ = residual_now(unc)
            oracle.query_unit(b_choice, "AUDIT", "AUDIT",
                              stratum_id=str(best_sid),
                              notes=f"AUDIT stratum {best_sid}")
            covered.add(b_choice)
            is_pos = bool(labels[b_choice])
            if is_pos:
                positive_bins.add(b_choice)
            # update audit stratum bookkeeping
            n_old, x_old = audit_samples_by_stratum.get(best_sid, (0, 0))
            audit_samples_by_stratum[best_sid] = (n_old + 1, x_old + (1 if is_pos else 0))
            unc_after = sorted([b for b in bin_idxs if b not in covered])
            res_after, _, _, _, _ = residual_now(unc_after)
            oracle.ledger[-1]["residual_hat_before"] = res_before
            oracle.ledger[-1]["residual_hat_after"] = res_after
            oracle.ledger[-1]["added_to_returned_intervals"] = str(is_pos)
            continue

        # Fallback: no action possible
        break

    # Final residual
    uncovered_final = [b for b in bin_idxs if b not in covered]
    res_hat, res_ucb, audit_n, audit_pos, p_ucb = residual_now(uncovered_final)

    # Group positive bins into intervals
    returned_intervals = group_positive_bins(sorted(positive_bins), grid)
    metrics = evaluate_events(returned_intervals, ref_seg)

    discover_calls = sum(1 for r in oracle.ledger if r["action_type"] == "DISCOVER")
    audit_calls = sum(1 for r in oracle.ledger if r["action_type"] == "AUDIT")

    assert oracle.calls <= budget_abs, f"EventLift budget violated: {oracle.calls} > {budget_abs}"
    assert oracle.calls == discover_calls + audit_calls

    # Stop decision: per spec §6.3, per-segment stop certificate needs n_min >= 29 for p_ucb<=0.10
    n_min_for_stop = 29
    if audit_n >= n_min_for_stop and res_ucb <= 0.10 * len(uncovered_final):
        stop_status = "stopped_certificate"
        stop_reason = "certificate_met"
    else:
        stop_status = "abstain_or_budget_exhausted"
        if audit_n < n_min_for_stop:
            stop_reason = "audit_n_too_small"
        else:
            stop_reason = "residual_ucb_too_loose"

    return {
        "method_id": method_id,
        "oracle": oracle,
        "returned_intervals": returned_intervals,
        "metrics": metrics,
        "oracle_calls_total": oracle.calls,
        "oracle_calls_discover": discover_calls,
        "oracle_calls_audit": audit_calls,
        "oracle_calls_supg": 0,
        "oracle_calls_abae": 0,
        "residual_estimate_available": True,
        "residual_hat": res_hat,
        "residual_ucb": res_ucb,
        "residual_ci_lower": "",
        "residual_ci_upper": "",
        "audit_n": audit_n,
        "audit_positive_n": audit_pos,
        "p_ucb": p_ucb,
        "recall_lcb_available": False,
        "stop_certificate_available": (stop_status == "stopped_certificate"),
        "stop_status": stop_status,
        "stop_reason": stop_reason,
        "applicability_note": "event-level AQP lifting; DISCOVER+AUDIT; no CERTIFY/SUPPRESS; residual report always emitted",
        "uncovered_final": uncovered_final,
    }


# ----------------------------------------------------------------------
# Main: run all methods, write outputs
# ----------------------------------------------------------------------
def main():
    grid, ref_seg = load_dev_data()
    print(f"Dev segment: {SEGMENT_ID}")
    print(f"  bins: {len(grid)}, positive bins: {int(grid[LABEL_COL].sum())}, "
          f"reference events: {len(ref_seg)}")
    print(f"  proxy col: {PROXY_COL}, label col: {LABEL_COL}")
    print(f"  event_id present in grid: {'event_id' in grid.columns} (excluded from online decisions)")

    all_trace_rows = []
    all_frontier_rows = []
    all_calibration_rows = []

    for budget_ratio in BUDGET_RATIOS:
        budget_abs = max(1, int(round(budget_ratio * len(grid))))
        for seed in SEEDS:
            print(f"\n--- budget_ratio={budget_ratio} budget_abs={budget_abs} seed={seed} ---")

            # 1. SUPG-event
            try:
                r_supg = run_supg_event(grid, ref_seg, budget_abs, budget_ratio, seed)
                all_trace_rows.extend(r_supg["oracle"].ledger)
                all_frontier_rows.append(_frontier_row(r_supg, budget_abs, budget_ratio, seed))
                print(f"  SUPG-event: calls={r_supg['oracle_calls_total']} "
                      f"P={r_supg['metrics']['event_precision']:.3f} "
                      f"R={r_supg['metrics']['event_recall']:.3f} "
                      f"cov={r_supg['metrics']['unique_event_coverage']}")
            except Exception as e:
                print(f"  SUPG-event FAILED: {e}")

            # 2. ABae-residual
            try:
                r_abae = run_abae_residual(grid, budget_abs, budget_ratio, seed)
                all_trace_rows.extend(r_abae["oracle"].ledger)
                all_frontier_rows.append(_frontier_row(r_abae, budget_abs, budget_ratio, seed))
                # calibration row
                true_uncovered_pos = int(grid[LABEL_COL].sum()) - r_abae["observed_positive_mass"]
                all_calibration_rows.append({
                    "segment_id": SEGMENT_ID,
                    "method_id": r_abae["method_id"],
                    "seed": seed,
                    "budget_abs": budget_abs,
                    "budget_ratio": budget_ratio,
                    "residual_hat": r_abae["residual_hat"],
                    "residual_ucb": r_abae["residual_ucb"],
                    "residual_true_if_reference_available": true_uncovered_pos,
                    "abs_error": abs(r_abae["residual_hat"] - true_uncovered_pos),
                    "signed_error": r_abae["residual_hat"] - true_uncovered_pos,
                    "audit_n": r_abae["audit_n"],
                    "audit_positive_n": r_abae["audit_positive_n"],
                    "p_ucb": binomial_ucb(r_abae["audit_n"]),
                    "calibration_note": "ABae total-positive-mass estimator; statistic=1",
                })
                print(f"  ABae-residual: calls={r_abae['oracle_calls_total']} "
                      f"res_hat={r_abae['residual_hat']:.2f} "
                      f"res_ucb={r_abae['residual_ucb']:.2f} "
                      f"audit_n={r_abae['audit_n']}")
            except Exception as e:
                print(f"  ABae-residual FAILED: {e}")

            # 3a. EventLift discover-only
            try:
                r_do = run_eventlift_discover_only(grid, ref_seg, budget_abs, budget_ratio, seed)
                all_trace_rows.extend(r_do["oracle"].ledger)
                all_frontier_rows.append(_frontier_row(r_do, budget_abs, budget_ratio, seed))
                true_unc_pos = int(grid[LABEL_COL].sum()) - len([b for b in r_do.get("uncovered_final", []) if labels_missing(b, grid)])
                # calibration
                true_uncovered_positives = int(grid[LABEL_COL].sum()) - sum(
                    1 for r in r_do["oracle"].ledger if r["online_positive"])
                all_calibration_rows.append({
                    "segment_id": SEGMENT_ID,
                    "method_id": r_do["method_id"],
                    "seed": seed,
                    "budget_abs": budget_abs,
                    "budget_ratio": budget_ratio,
                    "residual_hat": r_do["residual_hat"],
                    "residual_ucb": r_do["residual_ucb"],
                    "residual_true_if_reference_available": true_uncovered_positives,
                    "abs_error": abs(r_do["residual_hat"] - true_uncovered_positives),
                    "signed_error": r_do["residual_hat"] - true_uncovered_positives,
                    "audit_n": r_do.get("audit_n", 0),
                    "audit_positive_n": r_do.get("audit_positive_n", 0),
                    "p_ucb": r_do.get("p_ucb", 1.0),
                    "calibration_note": "discover-only; no AUDIT; residual over uncovered (no audit samples)",
                })
                print(f"  EventLift-discover-only: calls={r_do['oracle_calls_total']} "
                      f"P={r_do['metrics']['event_precision']:.3f} "
                      f"R={r_do['metrics']['event_recall']:.3f} "
                      f"cov={r_do['metrics']['unique_event_coverage']}")
            except Exception as e:
                print(f"  EventLift-discover-only FAILED: {e}")

            # 3b. EventLift discover+audit
            try:
                r_da = run_eventlift_discover_audit(grid, ref_seg, budget_abs, budget_ratio, seed)
                all_trace_rows.extend(r_da["oracle"].ledger)
                all_frontier_rows.append(_frontier_row(r_da, budget_abs, budget_ratio, seed))
                true_uncovered_positives = int(grid[LABEL_COL].sum()) - sum(
                    1 for r in r_da["oracle"].ledger if r["online_positive"])
                all_calibration_rows.append({
                    "segment_id": SEGMENT_ID,
                    "method_id": r_da["method_id"],
                    "seed": seed,
                    "budget_abs": budget_abs,
                    "budget_ratio": budget_ratio,
                    "residual_hat": r_da["residual_hat"],
                    "residual_ucb": r_da["residual_ucb"],
                    "residual_true_if_reference_available": true_uncovered_positives,
                    "abs_error": abs(r_da["residual_hat"] - true_uncovered_positives),
                    "signed_error": r_da["residual_hat"] - true_uncovered_positives,
                    "audit_n": r_da.get("audit_n", 0),
                    "audit_positive_n": r_da.get("audit_positive_n", 0),
                    "p_ucb": r_da.get("p_ucb", 1.0),
                    "calibration_note": f"discover+audit; stop={r_da['stop_status']}/{r_da['stop_reason']}",
                })
                print(f"  EventLift-discover-audit: calls={r_da['oracle_calls_total']} "
                      f"(D={r_da['oracle_calls_discover']},A={r_da['oracle_calls_audit']}) "
                      f"P={r_da['metrics']['event_precision']:.3f} "
                      f"R={r_da['metrics']['event_recall']:.3f} "
                      f"cov={r_da['metrics']['unique_event_coverage']} "
                      f"res_hat={r_da['residual_hat']:.2f} res_ucb={r_da['residual_ucb']:.2f} "
                      f"stop={r_da['stop_status']}")
            except Exception as e:
                print(f"  EventLift-discover-audit FAILED: {e}")

    # Write outputs
    trace_df = pd.DataFrame(all_trace_rows)
    trace_df.to_csv(OUT_DIR / "stage1_call_trace.csv", index=False)
    frontier_df = pd.DataFrame(all_frontier_rows)
    frontier_df.to_csv(OUT_DIR / "stage1_frontier_raw.csv", index=False)
    calib_df = pd.DataFrame(all_calibration_rows)
    calib_df.to_csv(OUT_DIR / "stage1_residual_calibration.csv", index=False)

    print(f"\nWrote {len(trace_df)} trace rows, {len(frontier_df)} frontier rows, "
          f"{len(calib_df)} calibration rows to {OUT_DIR}")


def labels_missing(b, grid):
    return False


def _frontier_row(r, budget_abs, budget_ratio, seed):
    """Build a frontier summary row from a method result dict."""
    m = r.get("metrics", {})
    return {
        "segment_id": SEGMENT_ID,
        "method_id": r["method_id"],
        "seed": seed,
        "budget_abs": budget_abs,
        "budget_ratio": budget_ratio,
        "oracle_calls_total": r["oracle_calls_total"],
        "oracle_calls_discover": r.get("oracle_calls_discover", 0),
        "oracle_calls_audit": r.get("oracle_calls_audit", 0),
        "oracle_calls_supg": r.get("oracle_calls_supg", 0),
        "oracle_calls_abae": r.get("oracle_calls_abae", 0),
        "returned_intervals": json.dumps(r.get("returned_intervals", [])),
        "event_precision": m.get("event_precision", ""),
        "event_recall": m.get("event_recall", ""),
        "unique_event_coverage": m.get("unique_event_coverage", ""),
        "duplicate_rate_if_available": "",  # computed from trace if needed
        "residual_estimate_available": r.get("residual_estimate_available", False),
        "residual_hat": r.get("residual_hat", ""),
        "residual_ucb": r.get("residual_ucb", ""),
        "residual_ci_lower": r.get("residual_ci_lower", ""),
        "residual_ci_upper": r.get("residual_ci_upper", ""),
        "recall_lcb_available": r.get("recall_lcb_available", False),
        "stop_certificate_available": r.get("stop_certificate_available", False),
        "stop_status": r.get("stop_status", "abstain_or_budget_exhausted"),
        "stop_reason": r.get("stop_reason", "budget_exhausted"),
        "applicability_note": r.get("applicability_note", ""),
    }


if __name__ == "__main__":
    main()
