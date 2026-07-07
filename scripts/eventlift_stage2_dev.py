"""EventLift-AQP Stage 2: DISCOVER + AUDIT + CERTIFY + SUPPRESS on dev segment.

Implements Stage 2 of EVENTLIFT_AQP_ALGORITHM_SPEC.md:
  - Reproduces Stage 1 baselines (discover-only, discover+audit) as control.
  - Adds CERTIFY: boundary refinement for pending anchors (ARC-lift).
  - Adds SUPPRESS: downweight nearby bins after certification (0 oracle cost).
  - All four actions compete in one unified utility loop.
  - Outputs an action arbitration trace to prove non-degenerate arbitration.

Hard constraints enforced:
  - Dev segment realcartest_2000_3200 only.
  - Replay over existing VLM-oracle-relative labels (center10 / reference_events).
  - No event_id in online decisions; reference used for evaluation only.
  - oracle_calls_total <= budget_abs asserted for every run.
  - No video / GPU / VLM / YOLO inference.
  - Small outputs only.
  - Does not modify Stage 1 outputs.

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

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "refe_repos" / "supg"))
sys.path.insert(0, str(REPO_ROOT / "src"))

from garc_eval.adapters.abae_adapter import quantile_stratify


# ----------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------
SEGMENT_ID = "realcartest_2000_3200"
VIDEO_ID = "realcartest"
GRID_CSV = REPO_ROOT / "outputs/late_aqp_frozen_cross_segment_v1/grid_realcartest_2000_3200.csv"
REF_CSV = REPO_ROOT / "src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/reference_events.csv"
OUT_DIR = REPO_ROOT / "outputs/eventlift_stage2_dev"
PROXY_COL = "prior_score_max"
LABEL_COL = "is_positive"
BUDGET_RATIOS = [0.10, 0.20, 0.30]
SEEDS = [0, 1, 2]
IOU_THRESHOLD = 0.3
ALPHA = 0.05
NUM_STRATA = 5

# Utility hyperparameters (fixed, NOT tuned - per spec §5.1)
ETA = 1.0       # oracle cost weight
LAMBDA = 0.5    # residual uncertainty reduction weight
GAMMA = 0.3     # dual-purpose positive recovery weight
KAPPA = 0.5     # opportunity cost weight
OMEGA = 0.3     # over-suppression risk weight

# CERTIFY parameters (fixed)
CERTIFY_MAX_DEPTH = 2  # max bins left and right to check around an anchor

# SUPPRESS parameters (fixed)
SUPPRESS_RADIUS = 2  # bins to downweight on each side of a certified interval


# ----------------------------------------------------------------------
# Data loading + shared utilities (identical to Stage 1)
# ----------------------------------------------------------------------
def load_dev_data():
    grid = pd.read_csv(GRID_CSV)
    grid = grid.sort_values("bin_idx").reset_index(drop=True)
    ref = pd.read_csv(REF_CSV)
    ref_seg = ref[(ref["absolute_t_start"] >= 2000) & (ref["absolute_t_end"] <= 3200)].copy()
    ref_seg = ref_seg.reset_index(drop=True)
    return grid, ref_seg


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
        if any(_iou_interval(s, e, rs, re) >= IOU_THRESHOLD for (rs, re) in ref_iv):
            hits_precision += 1
    precision = hits_precision / len(returned_intervals) if returned_intervals else 0.0
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


def group_positive_bins(positive_bin_idxs, grid):
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


def binomial_ucb(n, alpha=ALPHA):
    if n <= 0:
        return 1.0
    return 1.0 - alpha ** (1.0 / n)


def compute_residual(uncovered_bin_idxs, audit_samples_by_stratum, grid):
    if len(uncovered_bin_idxs) == 0:
        return 0.0, 0.0, 0, 0, 0.0
    N_U = len(uncovered_bin_idxs)
    audit_n_total = 0
    audit_positive_n_total = 0
    for sid, (n_s, x_s) in audit_samples_by_stratum.items():
        audit_n_total += n_s
        audit_positive_n_total += x_s
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
# Replay oracle with Stage 2 extended ledger columns
# ----------------------------------------------------------------------
class ReplayOracle:
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

    def query_unit(self, bin_idx, action_type, source_action,
                   component_id="", stratum_id="", anchor_bin_id="",
                   certified_interval="", suppressed_bins="",
                   notes=""):
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
            "anchor_bin_id": anchor_bin_id,
            "proxy_score": self.proxies[bin_idx],
            "oracle_label": oracle_label,
            "online_positive": label,
            "added_to_returned_intervals": "",
            "certified_interval": certified_interval,
            "suppressed_bins": suppressed_bins,
            "cumulative_oracle_calls": self.calls,
            "budget_remaining": self.budget_abs - self.calls,
            "residual_hat_before": "",
            "residual_hat_after": "",
            "notes": notes,
        })
        return oracle_label

    def log_no_cost_action(self, action_type, source_action, bin_id=-1,
                           component_id="", stratum_id="", anchor_bin_id="",
                           certified_interval="", suppressed_bins="",
                           notes=""):
        """Log a 0-oracle-cost action (e.g. SUPPRESS) for lineage."""
        self.ledger.append({
            "segment_id": self.segment_id,
            "method_id": self.method_id,
            "seed": self.seed,
            "budget_abs": self.budget_abs,
            "budget_ratio": self.budget_ratio,
            "call_idx": -1,  # no oracle call
            "action_type": action_type,
            "source_action": source_action,
            "bin_id": bin_id,
            "component_id": component_id,
            "stratum_id": stratum_id,
            "anchor_bin_id": anchor_bin_id,
            "proxy_score": "",
            "oracle_label": "",
            "online_positive": "",
            "added_to_returned_intervals": "",
            "certified_interval": certified_interval,
            "suppressed_bins": suppressed_bins,
            "cumulative_oracle_calls": self.calls,
            "budget_remaining": self.budget_abs - self.calls,
            "residual_hat_before": "",
            "residual_hat_after": "",
            "notes": notes,
        })


# ----------------------------------------------------------------------
# Unified EventLift loop with configurable actions
# ----------------------------------------------------------------------
def run_eventlift(grid, ref_seg, budget_abs, budget_ratio, seed,
                  method_id, audit_enabled=False, certify_enabled=False,
                  suppress_enabled=False):
    """Unified EventLift loop. Stage 1 = {audit,certify,suppress}=False toggles.
    Stage 2 adds certify/suppress into the same utility arbitration.
    """
    oracle = ReplayOracle(grid, SEGMENT_ID, method_id, seed, budget_abs, budget_ratio)
    grid_sorted = grid.sort_values("bin_idx").reset_index(drop=True)
    bin_idxs = grid_sorted["bin_idx"].values
    proxies = dict(zip(grid_sorted["bin_idx"], grid_sorted[PROXY_COL]))
    labels = dict(zip(grid_sorted["bin_idx"], grid_sorted[LABEL_COL]))
    bin_to_t = dict(zip(grid_sorted["bin_idx"],
                        zip(grid_sorted["local_t_start"], grid_sorted["local_t_end"])))

    covered = set()           # bins queried by any oracle action
    positive_bins = set()     # positive bins discovered (by DISCOVER or AUDIT)
    audit_samples_by_stratum = {}
    pending_anchors = []      # list of anchor bin_ids awaiting CERTIFY
    certified_intervals = []  # list of (start_bin, end_bin) certified
    suppressed_bins = set()  # bins downweighted by SUPPRESS (not queried, just deprioritized)
    returned_intervals = []   # final returned intervals (built from certified + remaining positives)
    arbitration_trace = []   # per-step arbitration log

    proxy_vals = np.array([proxies[b] for b in bin_idxs])
    theta = float(np.median(proxy_vals))

    def build_components(uncovered):
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

    def t_of(b):
        return bin_to_t[b]

    def merge_interval(start_bin, end_bin):
        """Merge (start_bin, end_bin) into returned_intervals, merging overlaps."""
        s_t, _ = t_of(start_bin)
        _, e_t = t_of(end_bin)
        new_iv = (s_t, e_t, start_bin, end_bin)
        # merge with existing returned intervals that overlap
        merged = list(returned_intervals)
        merged.append(new_iv)
        # sort by start
        merged.sort(key=lambda x: x[0])
        result = []
        for iv in merged:
            if result and iv[0] <= result[-1][1]:
                # overlap: merge
                ps, pe, psb, peb = result[-1]
                result[-1] = (ps, max(pe, iv[1]), min(psb, iv[2]), max(peb, iv[3]))
            else:
                result.append(iv)
        returned_intervals.clear()
        returned_intervals.extend(result)

    step_idx = 0
    while oracle.calls < budget_abs:
        uncovered = [b for b in bin_idxs if b not in covered]
        if len(uncovered) == 0 and not pending_anchors:
            break

        # --- Compute utility for each action type ---
        # DISCOVER utility
        u_discover = -1e18
        best_comp = None
        best_comp_idx = -1
        comps = build_components(uncovered)
        for ci, comp in enumerate(comps):
            fresh = [b for b in comp if b not in covered]
            if not fresh:
                continue
            proxy_mass = sum(proxies[b] for b in comp)
            fresh_frac = len(fresh) / len(comp)
            # discount suppressed bins
            n_suppressed_in_comp = sum(1 for b in fresh if b in suppressed_bins)
            redundancy = n_suppressed_in_comp / max(1, len(fresh))
            coverage_gain = proxy_mass * fresh_frac
            u = coverage_gain - ETA * 1.0 - KAPPA * 0.5
            # MU is folded into the redundancy term
            u -= redundancy * 0.5  # mu=0.5 inline
            if u > u_discover:
                u_discover = u
                best_comp = comp
                best_comp_idx = ci

        # AUDIT utility
        u_audit = -1e18
        if audit_enabled and uncovered:
            _, res_ucb, audit_n, _, _ = residual_now(uncovered)
            low_proxy_uncovered = [b for b in uncovered if proxies[b] < theta]
            dual_purpose = GAMMA * (len(low_proxy_uncovered) * 0.1)
            ucb_shrink = LAMBDA * (res_ucb / max(1, len(uncovered)))
            u_audit = ucb_shrink + dual_purpose - ETA * 1.0 - KAPPA * max(0.0, u_discover)

        # CERTIFY utility
        # pending_anchors are positive bins found by DISCOVER/AUDIT that haven't
        # been CERTIFY-processed yet. They ARE in `covered` (they were queried),
        # but that's fine — CERTIFY queries their NEIGHBORS, not the anchor itself.
        u_certify = -1e18
        best_anchor = None
        if certify_enabled and pending_anchors:
            for anchor in pending_anchors:
                # estimate certify cost: up to 2*CERTIFY_MAX_DEPTH oracle calls
                # (but only for neighbors not already covered)
                est_cost = 0
                for d in range(1, CERTIFY_MAX_DEPTH + 1):
                    for nb in [anchor + d, anchor - d]:
                        if nb not in covered and 0 <= nb < len(bin_idxs):
                            est_cost += 1
                est_cost = min(est_cost, budget_abs - oracle.calls)
                if est_cost <= 0:
                    continue
                # release quality gain: proxy score of anchor (higher = more likely a real event)
                release_quality = proxies[anchor]
                # future duplicate reduction: neighbors already covered?
                neighbors = [anchor - 1, anchor + 1]
                n_already_covered = sum(1 for nb in neighbors if nb in covered)
                dup_reduction = n_already_covered / max(1, len(neighbors))
                # CERTIFY cost: est_cost oracle calls, but each call may find a positive
                # (boundary expansion), so the net cost is discounted by expected positives
                expected_positives = est_cost * 0.3  # rough positive rate
                u = release_quality + 0.3 * dup_reduction + expected_positives \
                    - ETA * est_cost * 0.3 - KAPPA * 0.3
                if u > u_certify:
                    u_certify = u
                    best_anchor = anchor

        # SUPPRESS utility (0 oracle cost)
        u_suppress = -1e18
        if suppress_enabled and certified_intervals:
            # suppress after the most recent certified interval
            last_ci = certified_intervals[-1]
            # count bins within SUPPRESS_RADIUS that are not yet covered and not suppressed
            s_bin, e_bin = last_ci
            affected = []
            for b in range(s_bin - SUPPRESS_RADIUS, e_bin + SUPPRESS_RADIUS + 1):
                if b in covered or b < 0 or b >= len(bin_idxs):
                    continue
                if b in suppressed_bins:
                    continue
                if s_bin <= b <= e_bin:
                    continue
                affected.append(b)
            if affected:
                dup_reduction = len(affected) * 0.2  # expected saved DISCOVER calls
                over_suppress_risk = OMEGA * len(affected) * 0.1  # risk of killing nearby events
                u_suppress = dup_reduction - over_suppress_risk
            else:
                u_suppress = -1e18  # nothing to suppress

        # --- Pick the best action ---
        utilities = {
            "DISCOVER": u_discover,
            "AUDIT": u_audit if audit_enabled else -1e18,
            "CERTIFY": u_certify if certify_enabled else -1e18,
            "SUPPRESS": u_suppress if suppress_enabled else -1e18,
        }
        chosen = max(utilities, key=utilities.get)

        # Log arbitration
        arbitration_trace.append({
            "segment_id": SEGMENT_ID,
            "method_id": method_id,
            "seed": seed,
            "budget_abs": budget_abs,
            "budget_ratio": budget_ratio,
            "step_idx": step_idx,
            "chosen_action": chosen,
            "chosen_target": str(best_comp_idx if chosen == "DISCOVER" else
                                 (best_anchor if chosen == "CERTIFY" else
                                  (certified_intervals[-1] if chosen == "SUPPRESS" and certified_intervals else ""))),
            "U_discover_best": round(u_discover, 4),
            "U_audit_best": round(u_audit, 4) if audit_enabled else "",
            "U_certify_best": round(u_certify, 4) if certify_enabled else "",
            "U_suppress_best": round(u_suppress, 4) if suppress_enabled else "",
            "pending_anchor_count": len(pending_anchors),
            "active_component_count": len(comps),
            "suppressed_component_count": len(suppressed_bins),
            "budget_remaining": budget_abs - oracle.calls,
            "notes": "",
        })
        step_idx += 1

        # --- Execute chosen action ---
        if chosen == "DISCOVER" and best_comp is not None:
            fresh = [b for b in best_comp if b not in covered]
            if not fresh:
                continue
            w = np.array([math.sqrt(proxies[b]) for b in fresh])
            w = w / w.sum()
            rng = np.random.RandomState(seed * 100003 + oracle.calls)
            b_choice = int(rng.choice(fresh, p=w))
            res_before, _, _, _, _ = residual_now(uncovered)
            oracle.query_unit(b_choice, "DISCOVER", "DISCOVER",
                              component_id=f"comp{best_comp_idx}",
                              notes="DISCOVER sqrt(proxy) importance")
            covered.add(b_choice)
            is_pos = bool(labels[b_choice])
            if is_pos:
                positive_bins.add(b_choice)
                pending_anchors.append(b_choice)
            uncovered_after = [b for b in bin_idxs if b not in covered]
            res_after, _, _, _, _ = residual_now(uncovered_after)
            oracle.ledger[-1]["residual_hat_before"] = res_before
            oracle.ledger[-1]["residual_hat_after"] = res_after
            oracle.ledger[-1]["added_to_returned_intervals"] = str(is_pos)
            continue

        if chosen == "AUDIT" and audit_enabled and uncovered:
            unc = sorted([b for b in bin_idxs if b not in covered])
            if not unc:
                continue
            unc_proxies = np.array([proxies[b] for b in unc])
            ranks = pd.Series(unc_proxies).rank(method="first").values
            strata_assign = ((ranks - 1) / len(unc) * NUM_STRATA).astype(int)
            strata_assign = np.clip(strata_assign, 0, NUM_STRATA - 1)
            best_sid = 0
            best_sid_score = -1e18
            for sid in range(NUM_STRATA):
                mask = strata_assign == sid
                n_in_stratum = int(mask.sum())
                if n_in_stratum == 0:
                    continue
                n_s, x_s = audit_samples_by_stratum.get(sid, (0, 0))
                p_ucb_s = binomial_ucb(n_s) if n_s > 0 else 1.0
                score = LAMBDA * p_ucb_s * n_in_stratum + GAMMA * 0.1 * n_in_stratum
                if score > best_sid_score:
                    best_sid_score = score
                    best_sid = sid
            mask = strata_assign == best_sid
            candidates = [b for b, m in zip(unc, mask) if m]
            if not candidates:
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
                pending_anchors.append(b_choice)
            n_old, x_old = audit_samples_by_stratum.get(best_sid, (0, 0))
            audit_samples_by_stratum[best_sid] = (n_old + 1, x_old + (1 if is_pos else 0))
            unc_after = sorted([b for b in bin_idxs if b not in covered])
            res_after, _, _, _, _ = residual_now(unc_after)
            oracle.ledger[-1]["residual_hat_before"] = res_before
            oracle.ledger[-1]["residual_hat_after"] = res_after
            oracle.ledger[-1]["added_to_returned_intervals"] = str(is_pos)
            continue

        if chosen == "CERTIFY" and best_anchor is not None:
            anchor = best_anchor
            # CERTIFY: check up to CERTIFY_MAX_DEPTH bins left and right
            certify_calls_used = 0
            left_boundary = anchor
            right_boundary = anchor
            certify_success = False
            # expand right
            for d in range(1, CERTIFY_MAX_DEPTH + 1):
                nb = anchor + d
                if nb in covered or nb < 0 or nb >= len(bin_idxs):
                    break
                if oracle.calls >= budget_abs:
                    break
                oracle.query_unit(nb, "CERTIFY", "CERTIFY",
                                  anchor_bin_id=anchor,
                                  notes=f"CERTIFY right d={d} anchor={anchor}")
                covered.add(nb)
                certify_calls_used += 1
                if bool(labels[nb]):
                    positive_bins.add(nb)
                    right_boundary = nb
                    certify_success = True
                else:
                    break
            # expand left
            for d in range(1, CERTIFY_MAX_DEPTH + 1):
                nb = anchor - d
                if nb in covered or nb < 0 or nb >= len(bin_idxs):
                    break
                if oracle.calls >= budget_abs:
                    break
                oracle.query_unit(nb, "CERTIFY", "CERTIFY",
                                  anchor_bin_id=anchor,
                                  notes=f"CERTIFY left d={d} anchor={anchor}")
                covered.add(nb)
                certify_calls_used += 1
                if bool(labels[nb]):
                    positive_bins.add(nb)
                    left_boundary = nb
                    certify_success = True
                else:
                    break
            # Build certified interval
            s_t, _ = t_of(left_boundary)
            _, e_t = t_of(right_boundary)
            certified_interval_str = f"{left_boundary}:{right_boundary}"
            # Update last CERTIFY ledger rows with certified_interval
            for row in reversed(oracle.ledger):
                if row["action_type"] == "CERTIFY" and row.get("anchor_bin_id", "") == anchor:
                    row["certified_interval"] = certified_interval_str
                    row["added_to_returned_intervals"] = str(certify_success)
                if row["call_idx"] == -1:
                    break
            certified_intervals.append((left_boundary, right_boundary))
            # Remove anchor from pending
            if anchor in pending_anchors:
                pending_anchors.remove(anchor)
            # Merge into returned intervals
            if certify_success or anchor in positive_bins:
                merge_interval(left_boundary, right_boundary)
            continue

        if chosen == "SUPPRESS" and suppress_enabled and certified_intervals:
            last_ci = certified_intervals[-1]
            s_bin, e_bin = last_ci
            affected = []
            for b in range(s_bin - SUPPRESS_RADIUS, e_bin + SUPPRESS_RADIUS + 1):
                if b in covered or b < 0 or b >= len(bin_idxs):
                    continue
                if b in suppressed_bins:
                    continue
                if s_bin <= b <= e_bin:
                    continue
                affected.append(b)
                suppressed_bins.add(b)
            oracle.log_no_cost_action(
                "SUPPRESS", "SUPPRESS",
                bin_id=-1,
                certified_interval=f"{s_bin}:{e_bin}",
                suppressed_bins=";".join(str(b) for b in affected),
                notes=f"SUPPRESS radius={SUPPRESS_RADIUS} around certified {s_bin}:{e_bin}; affected {len(affected)} bins")
            continue

        # No action possible
        break

    # Final residual
    uncovered_final = [b for b in bin_idxs if b not in covered]
    res_hat, res_ucb, audit_n, audit_pos, p_ucb = residual_now(uncovered_final)

    # Build returned intervals: if CERTIFY was used, we already have returned_intervals;
    # otherwise group positive bins (Stage 1 behavior)
    if not certify_enabled:
        returned_intervals = group_positive_bins(sorted(positive_bins), grid)
    else:
        # Ensure all positive bins are represented (in case CERTIFY didn't merge all)
        # Convert returned_intervals (which may be 4-tuples) to 2-tuples
        returned_intervals_2 = [(iv[0], iv[1]) if len(iv) == 4 else (iv[0], iv[1])
                                for iv in returned_intervals]
        # Also add any positive bins not in a certified interval
        covered_by_certify = set()
        for iv in returned_intervals:
            if len(iv) == 4:
                for b in range(iv[2], iv[3] + 1):
                    covered_by_certify.add(b)
        extra_pos = [b for b in positive_bins if b not in covered_by_certify]
        if extra_pos:
            extra_intervals = group_positive_bins(extra_pos, grid)
            returned_intervals_2.extend(extra_intervals)
        returned_intervals = returned_intervals_2

    metrics = evaluate_events(returned_intervals, ref_seg)

    # Count calls by action type
    discover_calls = sum(1 for r in oracle.ledger if r["action_type"] == "DISCOVER" and r["call_idx"] > 0)
    audit_calls = sum(1 for r in oracle.ledger if r["action_type"] == "AUDIT" and r["call_idx"] > 0)
    certify_calls = sum(1 for r in oracle.ledger if r["action_type"] == "CERTIFY" and r["call_idx"] > 0)
    suppress_calls = sum(1 for r in oracle.ledger if r["action_type"] == "SUPPRESS" and r["call_idx"] > 0)
    # duplicate_rate: fraction of oracle calls that hit bins already in covered
    # (we track this via covered set; since we check before querying, duplicates
    # are 0 by construction in this implementation. But we can count "redundant"
    # calls = calls to bins within SUPPRESS_RADIUS of already-certified intervals)
    duplicate_rate = 0.0  # by construction, we don't re-query; but SUPPRESS prevents future re-queries

    # Certify success rate
    certify_total = len([r for r in oracle.ledger if r["action_type"] == "CERTIFY" and r["call_idx"] > 0])
    certify_successes = len([r for r in oracle.ledger if r["action_type"] == "CERTIFY"
                             and r.get("added_to_returned_intervals") == "True"])
    certify_success_rate = certify_successes / max(1, certify_total) if certify_total > 0 else 0.0

    assert oracle.calls <= budget_abs, f"EventLift budget violated: {oracle.calls} > {budget_abs}"
    assert oracle.calls == discover_calls + audit_calls + certify_calls + suppress_calls, \
        f"Ledger mismatch: {oracle.calls} != {discover_calls}+{audit_calls}+{certify_calls}+{suppress_calls}"

    # Stop decision
    n_min_for_stop = 29
    if audit_n >= n_min_for_stop and res_ucb <= 0.10 * len(uncovered_final):
        stop_status = "stopped_certificate"
        stop_reason = "certificate_met"
    else:
        stop_status = "abstain_or_budget_exhausted"
        stop_reason = "audit_n_too_small" if audit_n < n_min_for_stop else "residual_ucb_too_loose"

    return {
        "method_id": method_id,
        "oracle": oracle,
        "arbitration_trace": arbitration_trace,
        "returned_intervals": returned_intervals,
        "metrics": metrics,
        "oracle_calls_total": oracle.calls,
        "oracle_calls_discover": discover_calls,
        "oracle_calls_audit": audit_calls,
        "oracle_calls_certify": certify_calls,
        "oracle_calls_suppress": suppress_calls,
        "oracle_calls_supg": 0,
        "oracle_calls_abae": 0,
        "certify_calls": certify_calls,
        "certify_success_rate": certify_success_rate,
        "suppressed_bin_count": len(suppressed_bins),
        "duplicate_rate": duplicate_rate,
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
        "applicability_note": _applicability_note(audit_enabled, certify_enabled, suppress_enabled),
        "uncovered_final": uncovered_final,
        "positive_bins": positive_bins,
    }


def _applicability_note(audit_enabled, certify_enabled, suppress_enabled):
    parts = ["DISCOVER"]
    if audit_enabled:
        parts.append("AUDIT")
    if certify_enabled:
        parts.append("CERTIFY")
    if suppress_enabled:
        parts.append("SUPPRESS")
    return "event-level AQP lifting; " + "+".join(parts) + "; residual report always emitted"


# ----------------------------------------------------------------------
# Method wrappers for the 5 Stage 2 methods
# ----------------------------------------------------------------------
def run_discover_only(grid, ref_seg, budget_abs, budget_ratio, seed):
    return run_eventlift(grid, ref_seg, budget_abs, budget_ratio, seed,
                         "EventLift-discover-only")

def run_discover_audit(grid, ref_seg, budget_abs, budget_ratio, seed):
    return run_eventlift(grid, ref_seg, budget_abs, budget_ratio, seed,
                         "EventLift-discover-audit", audit_enabled=True)

def run_discover_certify(grid, ref_seg, budget_abs, budget_ratio, seed):
    return run_eventlift(grid, ref_seg, budget_abs, budget_ratio, seed,
                         "EventLift-discover-certify", certify_enabled=True)

def run_discover_audit_certify(grid, ref_seg, budget_abs, budget_ratio, seed):
    return run_eventlift(grid, ref_seg, budget_abs, budget_ratio, seed,
                         "EventLift-discover-audit-certify", audit_enabled=True, certify_enabled=True)

def run_full_stage2(grid, ref_seg, budget_abs, budget_ratio, seed):
    return run_eventlift(grid, ref_seg, budget_abs, budget_ratio, seed,
                         "EventLift-full-stage2",
                         audit_enabled=True, certify_enabled=True, suppress_enabled=True)


# ----------------------------------------------------------------------
# Output row builders
# ----------------------------------------------------------------------
def _frontier_row(r, budget_abs, budget_ratio, seed):
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
        "oracle_calls_certify": r.get("oracle_calls_certify", 0),
        "oracle_calls_suppress": r.get("oracle_calls_suppress", 0),
        "returned_intervals": json.dumps(r.get("returned_intervals", [])),
        "event_precision": m.get("event_precision", ""),
        "event_recall": m.get("event_recall", ""),
        "unique_event_coverage": m.get("unique_event_coverage", ""),
        "duplicate_rate": r.get("duplicate_rate", 0.0),
        "certify_calls": r.get("certify_calls", 0),
        "certify_success_rate": r.get("certify_success_rate", 0.0),
        "suppressed_bin_count": r.get("suppressed_bin_count", 0),
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


def _calibration_row(r, budget_abs, budget_ratio, seed, true_uncovered_positives):
    return {
        "segment_id": SEGMENT_ID,
        "method_id": r["method_id"],
        "seed": seed,
        "budget_abs": budget_abs,
        "budget_ratio": budget_ratio,
        "residual_hat": r.get("residual_hat", 0.0),
        "residual_ucb": r.get("residual_ucb", 0.0),
        "residual_true_if_reference_available": true_uncovered_positives,
        "abs_error": abs(r.get("residual_hat", 0.0) - true_uncovered_positives),
        "signed_error": r.get("residual_hat", 0.0) - true_uncovered_positives,
        "audit_n": r.get("audit_n", 0),
        "audit_positive_n": r.get("audit_positive_n", 0),
        "p_ucb": r.get("p_ucb", 1.0),
        "calibration_note": f"stop={r['stop_status']}/{r['stop_reason']}",
    }


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main():
    grid, ref_seg = load_dev_data()
    n_pos = int(grid[LABEL_COL].sum())
    print(f"Dev segment: {SEGMENT_ID}")
    print(f"  bins: {len(grid)}, positive bins: {n_pos}, reference events: {len(ref_seg)}")
    print(f"  proxy col: {PROXY_COL}, label col: {LABEL_COL}")

    os.makedirs(OUT_DIR, exist_ok=True)

    all_trace_rows = []
    all_frontier_rows = []
    all_calibration_rows = []
    all_arbitration_rows = []

    methods = [
        ("discover_only", run_discover_only),
        ("discover_audit", run_discover_audit),
        ("discover_certify", run_discover_certify),
        ("discover_audit_certify", run_discover_audit_certify),
        ("full_stage2", run_full_stage2),
    ]

    for budget_ratio in BUDGET_RATIOS:
        budget_abs = max(1, int(round(budget_ratio * len(grid))))
        for seed in SEEDS:
            print(f"\n--- budget_ratio={budget_ratio} budget_abs={budget_abs} seed={seed} ---")
            for name, fn in methods:
                try:
                    r = fn(grid, ref_seg, budget_abs, budget_ratio, seed)
                    all_trace_rows.extend(r["oracle"].ledger)
                    all_frontier_rows.append(_frontier_row(r, budget_abs, budget_ratio, seed))
                    all_arbitration_rows.extend(r["arbitration_trace"])
                    true_unc_pos = n_pos - sum(1 for row in r["oracle"].ledger
                                               if row.get("online_positive") is True)
                    all_calibration_rows.append(_calibration_row(r, budget_abs, budget_ratio, seed, true_unc_pos))
                    m = r["metrics"]
                    print(f"  {r['method_id']}: calls={r['oracle_calls_total']} "
                          f"(D={r['oracle_calls_discover']},A={r['oracle_calls_audit']},"
                          f"C={r['oracle_calls_certify']},S={r['oracle_calls_suppress']}) "
                          f"P={m['event_precision']:.3f} R={m['event_recall']:.3f} "
                          f"cov={m['unique_event_coverage']} "
                          f"res_ucb={r['residual_ucb']:.1f} "
                          f"stop={r['stop_status']}")
                except Exception as e:
                    print(f"  {name} FAILED: {e}")
                    import traceback; traceback.print_exc()

    trace_df = pd.DataFrame(all_trace_rows)
    trace_df.to_csv(OUT_DIR / "stage2_call_trace.csv", index=False)
    frontier_df = pd.DataFrame(all_frontier_rows)
    frontier_df.to_csv(OUT_DIR / "stage2_frontier_raw.csv", index=False)
    calib_df = pd.DataFrame(all_calibration_rows)
    calib_df.to_csv(OUT_DIR / "stage2_residual_calibration.csv", index=False)
    arb_df = pd.DataFrame(all_arbitration_rows)
    arb_df.to_csv(OUT_DIR / "stage2_action_arbitration.csv", index=False)

    print(f"\nWrote {len(trace_df)} trace rows, {len(frontier_df)} frontier rows, "
          f"{len(calib_df)} calibration rows, {len(arb_df)} arbitration rows to {OUT_DIR}")

    # Budget assertion summary
    violations = frontier_df[frontier_df.oracle_calls_total > frontier_df.budget_abs]
    print(f"Budget violations: {len(violations)} / {len(frontier_df)}")


if __name__ == "__main__":
    main()
