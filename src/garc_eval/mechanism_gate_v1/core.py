"""Core generator, policies, materializer and evaluator for mechanism gate v1.

Policy functions accept only :class:`PublicInstance`.  Hidden labels and event
IDs live in a separate object consumed only after acquisition by the evaluator.
The ORACLE_INFORMED policy is implemented in an explicitly evaluator-only
entry point.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, log, sqrt
from statistics import NormalDist
from time import perf_counter
from typing import Callable, Iterable

import numpy as np
from scipy.optimize import linear_sum_assignment
from sklearn.metrics import roc_auc_score


POLICIES = (
    "R0_RANDOM", "R1_UNIFORM_TEMPORAL", "P0_POSITIVE_PROBABILITY",
    "P1_EVENT_SATURATION", "P2_SATURATION_PLUS_EXPLORE",
    "P3_FROZEN", "P3_GENERATIVE_CALIBRATED", "MAP_LIKE",
)


@dataclass(frozen=True)
class PublicInstance:
    unit_ids: np.ndarray
    scores: np.ndarray
    probabilities: np.ndarray
    frozen_probabilities: np.ndarray
    hypothesis_ids: np.ndarray
    region_ids: np.ndarray
    candidate_mask: np.ndarray
    support_start: np.ndarray
    support_end: np.ndarray
    generator_public: dict


@dataclass(frozen=True)
class HiddenInstance:
    labels: np.ndarray
    event_ids: np.ndarray
    event_intervals: tuple[tuple[int, int, int], ...]
    generation_hidden: dict


@dataclass
class PolicyResult:
    policy: str
    order: list[int]
    outcomes: list[int]
    action_types: list[str]
    runtime_seconds: float
    structure_eligible: int
    structure_selected: int


def posterior_probability(score: np.ndarray, mu: float, prior: float) -> np.ndarray:
    """Exact posterior for N(0,1)/N(mu,1) class-conditionals."""
    prior = float(np.clip(prior, 1e-9, 1 - 1e-9))
    log_odds = log(prior / (1 - prior)) + mu * score - 0.5 * mu * mu
    return 1.0 / (1.0 + np.exp(-np.clip(log_odds, -40, 40)))


def target_mu(target_auroc: float) -> float:
    return sqrt(2.0) * NormalDist().inv_cdf(target_auroc)


def _event_layout(n: int, duration: int, rng: np.random.Generator) -> list[tuple[int, int, int]]:
    duration = max(1, int(duration))
    gap = max(2, duration // 2 + 1)
    count = max(4, min(26, n // max(duration + gap, 7)))
    total = count * duration + (count + 1) * gap
    if total > n:
        count = max(2, (n - gap) // (duration + gap))
    slack = max(0, n - (count * duration + (count + 1) * gap))
    offsets = rng.multinomial(slack, np.ones(count + 1) / (count + 1)) if slack else np.zeros(count + 1, int)
    cursor = gap + int(offsets[0]); out = []
    for eid in range(count):
        out.append((eid, cursor, cursor + duration - 1))
        cursor += duration + gap + int(offsets[eid + 1])
    return out


def generate_instance(
    *, n: int, duration: int, target_auroc: float, candidate_recall: float,
    false_burden: float, fragmentation: int, seed: int, suite: str,
    residual_prevalence: float = 0.25, merge_ambiguity: float = 0.5,
    calibration: str = "correct",
) -> tuple[PublicInstance, HiddenInstance]:
    rng = np.random.default_rng(seed)
    intervals = _event_layout(n, duration, rng)
    labels = np.zeros(n, dtype=np.int8)
    event_ids = np.full(n, -1, dtype=np.int32)
    for eid, start, end in intervals:
        labels[start:end + 1] = 1; event_ids[start:end + 1] = eid

    mu = target_mu(target_auroc)
    scores = rng.normal(mu * labels, 1.0, n)
    prior = float(labels.mean())
    calibrated = posterior_probability(scores, mu, prior)
    # Frozen pipeline deliberately uses the historical weak prior/mapping.  It
    # sees only score and frozen constants, never realized labels.
    frozen = 1.0 / (1.0 + np.exp(-np.clip(0.85 * scores - 1.35, -40, 40)))
    if calibration == "overconfident":
        probs = np.clip(calibrated, 1e-6, 1 - 1e-6) ** 2
        probs = probs / (probs + (1 - calibrated) ** 2)
    elif calibration == "underconfident":
        probs = 0.5 + 0.45 * (calibrated - 0.5)
    elif calibration == "wrong_prior":
        probs = posterior_probability(scores, mu, min(0.5, prior * 2.5))
    elif calibration == "temporal_shift":
        probs = calibrated.copy(); probs[n // 2:] = 1 - probs[n // 2:]
    else:
        probs = calibrated

    candidate = np.ones(n, dtype=bool)
    positive_ids = np.flatnonzero(labels)
    if candidate_recall < 1:
        keep = rng.random(len(positive_ids)) < candidate_recall
        candidate[positive_ids[~keep]] = False

    hypothesis = np.full(n, -1, dtype=np.int32)
    next_h = 0
    residual_events = set()
    if suite == "D_EXPLORATION":
        residual_events = {eid for eid, _, _ in intervals if rng.random() < residual_prevalence}
    for eid, start, end in intervals:
        if eid in residual_events:
            continue
        members = np.arange(start, end + 1)
        chunks = np.array_split(members, max(1, min(fragmentation, len(members))))
        for chunk in chunks:
            hypothesis[chunk] = next_h; next_h += 1

    negatives = np.flatnonzero(labels == 0)
    desired_false_h = int(round((false_burden / max(1e-6, 1 - false_burden)) * max(1, next_h)))
    if desired_false_h and len(negatives):
        chosen = rng.choice(negatives, size=min(desired_false_h, len(negatives)), replace=False)
        for uid in chosen:
            hypothesis[uid] = next_h; next_h += 1

    # Every candidate belongs to a deterministic temporal exploration region.
    region = np.arange(n, dtype=np.int32) // max(4, duration * 2)
    public = PublicInstance(
        unit_ids=np.arange(n, dtype=np.int32), scores=scores.astype(float),
        probabilities=np.asarray(probs, float), frozen_probabilities=frozen.astype(float),
        hypothesis_ids=hypothesis, region_ids=region, candidate_mask=candidate,
        support_start=np.arange(n, dtype=float), support_end=np.arange(1, n + 1, dtype=float),
        generator_public={"n": n, "duration": duration, "target_auroc": target_auroc,
                          "candidate_recall": candidate_recall, "false_burden": false_burden,
                          "fragmentation": fragmentation, "suite": suite,
                          "mu": mu, "class_prior": prior, "merge_ambiguity": merge_ambiguity,
                          "calibration": calibration, "seed": seed},
    )
    hidden = HiddenInstance(labels=labels, event_ids=event_ids,
        event_intervals=tuple(intervals), generation_hidden={"seed": seed, "event_count": len(intervals)})
    return public, hidden


def materialize(order: Iterable[int], outcomes: Iterable[int], materializer: str = "k3_bridge_safe") -> list[tuple[int, int]]:
    positives = sorted(uid for uid, y in zip(order, outcomes) if y == 1)
    negatives = {uid for uid, y in zip(order, outcomes) if y == 0}
    if not positives:
        return []
    groups = [[positives[0]]]
    for uid in positives[1:]:
        left = groups[-1][-1]
        between = set(range(left + 1, uid))
        if materializer == "k3_bridge_safe":
            join = uid == left + 1
        elif materializer == "original_k3":
            join = uid - left - 1 <= 1 and not bool(between & negatives)
        else:
            raise ValueError(materializer)
        if join and uid - groups[-1][0] + 1 <= 4:
            groups[-1].append(uid)
        else:
            groups.append([uid])
    return [(g[0], g[-1]) for g in groups]


def structural_risk(public: PublicInstance, order: list[int], outcomes: list[int], materializer: str) -> float:
    """Additive reference-free risk induced by frozen materializer edges.

    Joining adjacent positive anchors owned by different hypotheses costs 1;
    joining anchors from the same hypothesis reduces fragmentation risk by
    0.25.  Under original_k3, an unverified one-unit bridge costs 0.15 until a
    negative barrier is observed.  This additive form permits exact local
    counterfactual updates for every legal action.
    """
    pos = {int(u) for u, y in zip(order, outcomes) if y == 1}
    neg = {int(u) for u, y in zip(order, outcomes) if y == 0}
    risk = 0.0
    for u in pos:
        if u + 1 in pos:
            a, b = int(public.hypothesis_ids[u]), int(public.hypothesis_ids[u + 1])
            risk += -0.25 if a >= 0 and a == b else (1.0 if a >= 0 and b >= 0 else 0.1)
        if materializer == "original_k3" and u + 2 in pos and u + 1 not in neg and u + 1 not in pos:
            risk += 0.15
    return float(risk)


def counterfactual_risk_deltas(public: PublicInstance, remaining: np.ndarray,
                               selected: list[int], outcomes: list[int], materializer: str) -> tuple[np.ndarray, np.ndarray]:
    """Exact local risk changes for binary materializer branches."""
    n = len(public.unit_ids)
    pos = np.zeros(n, dtype=bool); neg = np.zeros(n, dtype=bool)
    if selected:
        ids = np.asarray(selected, int); ys = np.asarray(outcomes, int)
        pos[ids[ys == 1]] = True; neg[ids[ys == 0]] = True
    hp = public.hypothesis_ids
    dpos = np.zeros(len(remaining), float); dneg = np.zeros(len(remaining), float)
    for offset in (-1, 1):
        v = remaining + offset; valid = (v >= 0) & (v < n)
        joined = valid & pos[np.clip(v, 0, n - 1)]
        a = hp[remaining]; b = hp[np.clip(v, 0, n - 1)]
        dpos += joined * np.where((a >= 0) & (a == b), -0.25, np.where((a >= 0) & (b >= 0), 1.0, 0.1))
    if materializer == "original_k3":
        # Positive branch removes any existing unverified bridge through q,
        # then creates new distance-two bridge relations around q.
        left_right = (remaining > 0) & (remaining < n - 1) & pos[np.clip(remaining - 1,0,n-1)] & pos[np.clip(remaining + 1,0,n-1)]
        dpos -= 0.15 * left_right
        for offset in (-2, 2):
            v=remaining+offset; mid=remaining+offset//2;valid=(v>=0)&(v<n)
            dpos += 0.15 * valid * pos[np.clip(v,0,n-1)] * ~neg[np.clip(mid,0,n-1)] * ~pos[np.clip(mid,0,n-1)]
        # A negative branch certifies the barrier between distance-two anchors.
        dneg -= 0.15 * left_right
    return dpos, dneg


def _choose_uniform(remaining: np.ndarray, selected: list[int], n: int) -> int:
    if not selected:
        return int(remaining[len(remaining) // 2])
    targets = np.linspace(0, n - 1, len(selected) + 2)[1:-1]
    dist = np.min(np.abs(remaining[:, None] - targets[None, :]), axis=1) if len(targets) else np.abs(remaining - n / 2)
    return int(remaining[np.argmax(dist)])


def _policy_score(policy: str, public: PublicInstance, remaining: np.ndarray,
                  selected: list[int], outcomes: list[int], materializer: str) -> tuple[np.ndarray, np.ndarray]:
    probs = public.probabilities[remaining]
    hs = public.hypothesis_ids[remaining]
    saturated = {int(public.hypothesis_ids[u]) for u, y in zip(selected, outcomes)
                 if y == 1 and public.hypothesis_ids[u] >= 0}
    base = probs.copy()
    if policy in {"P1_EVENT_SATURATION", "P2_SATURATION_PLUS_EXPLORE", "P3_FROZEN", "P3_GENERATIVE_CALIBRATED"}:
        base = np.where(np.isin(hs, list(saturated)), 0.0, base)
    if policy in {"P2_SATURATION_PLUS_EXPLORE", "P3_FROZEN", "P3_GENERATIVE_CALIBRATED"}:
        queried_regions = {int(public.region_ids[u]) for u in selected}
        uncovered = ~np.isin(public.region_ids[remaining], list(queried_regions))
        no_owner = hs < 0
        # Expected new-event value, not a quota.
        base = base * (1.0 + 0.35 * uncovered + 0.35 * no_owner)
    structure_gain = np.zeros(len(remaining), float)
    if policy in {"P3_FROZEN", "P3_GENERATIVE_CALIBRATED"} and selected:
        weight_p = public.frozen_probabilities if policy == "P3_FROZEN" else public.probabilities
        dpos, dneg = counterfactual_risk_deltas(public, remaining, selected, outcomes, materializer)
        p = weight_p[remaining]
        structure_gain = -(p * dpos + (1 - p) * dneg)
        base = base + 0.8 * structure_gain
    return base, structure_gain


def run_policy(public: PublicInstance, oracle_query: Callable[[int], int], policy: str, budget: int,
               seed: int, materializer: str = "k3_bridge_safe") -> PolicyResult:
    if policy not in POLICIES:
        raise ValueError(policy)
    rng = np.random.default_rng(seed + 99173)
    selected: list[int] = []; outcomes: list[int] = []; actions: list[str] = []
    structure_eligible = 0; structure_selected = 0
    start = perf_counter()
    legal = np.flatnonzero(public.candidate_mask)
    for _ in range(min(budget, len(legal))):
        remaining = np.setdiff1d(legal, np.asarray(selected, int), assume_unique=False)
        if policy == "R0_RANDOM":
            uid = int(rng.choice(remaining)); sg = np.zeros(len(remaining))
        elif policy == "R1_UNIFORM_TEMPORAL":
            uid = _choose_uniform(remaining, selected, len(public.unit_ids)); sg = np.zeros(len(remaining))
        elif policy == "MAP_LIKE":
            score = public.probabilities[remaining].copy()
            if selected:
                distance = np.min(np.abs(remaining[:, None] - np.asarray(selected)[None, :]), axis=1)
                score *= (1.0 + np.minimum(distance, 20) / 20.0)
            uid = int(remaining[np.lexsort((remaining, -score))[0]]); sg = np.zeros(len(remaining))
        else:
            score, sg = _policy_score(policy, public, remaining, selected, outcomes, materializer)
            uid = int(remaining[np.lexsort((remaining, -public.scores[remaining], -score))[0]])
        eligible_count = int(np.sum(np.abs(sg) > 1e-12))
        structure_eligible += eligible_count
        if eligible_count and abs(float(sg[np.where(remaining == uid)[0][0]])) > 1e-12:
            structure_selected += 1; action = "STRUCTURE"
        elif public.hypothesis_ids[uid] < 0:
            action = "EXPLORE"
        else:
            action = "CORE"
        # The policy receives only the selected unit's outcome, never an oracle
        # table or future labels.
        selected.append(uid); outcomes.append(int(oracle_query(uid))); actions.append(action)
    return PolicyResult(policy, selected, outcomes, actions, perf_counter() - start,
                        structure_eligible, structure_selected)


def run_oracle_informed(public: PublicInstance, hidden: HiddenInstance, budget: int,
                        materializer: str = "k3_bridge_safe") -> PolicyResult:
    """Evaluator-only greedy unique-event ordering; never called by policies."""
    selected: list[int] = []; outcomes: list[int] = []; actions: list[str] = []
    found: set[int] = set(); legal = np.flatnonzero(public.candidate_mask)
    start = perf_counter()
    for _ in range(min(budget, len(legal))):
        rem = np.setdiff1d(legal, np.asarray(selected, int), assume_unique=False)
        utility = np.array([1 if hidden.event_ids[u] >= 0 and int(hidden.event_ids[u]) not in found else 0 for u in rem])
        positive = hidden.labels[rem]
        idx = np.lexsort((rem, -public.scores[rem], -positive, -utility))[0]
        uid = int(rem[idx]); y = int(hidden.labels[uid])
        selected.append(uid); outcomes.append(y); actions.append("EVALUATOR_ONLY")
        if hidden.event_ids[uid] >= 0: found.add(int(hidden.event_ids[uid]))
    return PolicyResult("ORACLE_INFORMED", selected, outcomes, actions, perf_counter() - start, 0, 0)


def evaluate_prefix(result: PolicyResult, hidden: HiddenInstance, budget: int,
                    materializer_name: str = "k3_bridge_safe") -> dict:
    order = result.order[:budget]; outcomes = result.outcomes[:budget]
    segs = materialize(order, outcomes, materializer_name)
    refs = [(s, e) for _, s, e in hidden.event_intervals]
    if segs and refs:
        overlap = np.array([[max(0, min(pe, re) - max(ps, rs) + 1) for rs, re in refs] for ps, pe in segs])
        rows, cols = linear_sum_assignment(-overlap)
        matched = int(sum(overlap[r, c] > 0 for r, c in zip(rows, cols)))
    else:
        matched = 0
    precision = matched / len(segs) if segs else 0.0
    recall = matched / len(refs) if refs else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    discovered = {int(hidden.event_ids[u]) for u, y in zip(order, outcomes) if y and hidden.event_ids[u] >= 0}
    duplicate = sum(1 for eid in [int(hidden.event_ids[u]) for u, y in zip(order, outcomes) if y and hidden.event_ids[u] >= 0]
                    if [int(hidden.event_ids[u]) for u, y in zip(order, outcomes) if y and hidden.event_ids[u] >= 0].count(eid) > 1)
    ref_hit_counts = {eid: 0 for eid, _, _ in hidden.event_intervals}
    for ps, pe in segs:
        for eid, rs, re in hidden.event_intervals:
            if min(pe, re) >= max(ps, rs): ref_hit_counts[eid] += 1
    oversplit = sum(max(0, c - 1) for c in ref_hit_counts.values())
    overmerge = sum(max(0, sum(min(pe, re) >= max(ps, rs) for _, rs, re in hidden.event_intervals) - 1) for ps, pe in segs)
    return {"budget": budget, "event_precision": precision, "event_recall": recall, "event_f1": f1,
            "unique_events": len(discovered), "duplicate_positive_queries": duplicate,
            "queries_per_discovered_event": len(order) / max(1, len(discovered)),
            "overmerge": overmerge, "oversplit": oversplit,
            "returned_duration": sum(e - s + 1 for s, e in segs),
            "output_changing_query_rate": sum(outcomes) / max(1, len(outcomes))}


def achieved_auroc(public: PublicInstance, hidden: HiddenInstance) -> float:
    return float(roc_auc_score(hidden.labels, public.scores)) if len(np.unique(hidden.labels)) == 2 else float("nan")
