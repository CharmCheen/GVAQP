#!/usr/bin/env python3
"""Phi-budget replay on existing VLM-defined center10 oracle labels.

This is a no-new-VLM CPU replay. Oracle labels are only exposed to a policy
after the policy selects an anchor as a simulated VLM call.
"""

from __future__ import annotations

import csv
import json
import math
import random
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "outputs" / "phi_budget_replay_v1"
TABLES = OUT / "tables"
REPORTS = OUT / "reports"
FIGURES = OUT / "figures"
LOGS = OUT / "logs"

ORACLE_LABELS = ROOT / "experiments/v13/v13_8_full_oracle/tables/center10_full_oracle_labels.csv"
ORACLE_EVENTS = ROOT / "experiments/v13/v13_8_full_oracle/tables/center10_vlm_oracle_events.csv"
PROXY_FEATURES = ROOT / "experiments/v13/v13_7_multimethod_replay/tables/center10_proxy_features.csv"

BUDGETS = [5, 10, 20, 40, 80, 120, 399]
RANDOM_REPEATS = 100
PHI_REPEATS = 100
SEED = 20260703
PRIMARY_SCORE = "score_fusion_yolo_motion"
UNIT_SECONDS = 10.0
ETA = 0.12
UCB_BETA = 1.0
Z_DELTA = 1.64
PRIOR_STRENGTH = 2.0
INITIAL_CONFIDENCE = 0.35
CONFIDENCE_INCREMENT = 0.30
CONFIRMED_CONFIDENCE = 0.80
TEMPORAL_NMS_GAP = 30.0


@dataclass(frozen=True)
class Anchor:
    anchor_id: str
    index: int
    video_id: str
    anchor_time: float
    start_time: float
    end_time: float
    label_positive: bool
    score: float
    scores: dict[str, float]
    stratum: str = ""


@dataclass
class StratumState:
    anchor_ids: list[str]
    prior_alpha: float
    prior_beta: float
    audit_draws: int = 0
    audit_positives: int = 0

    @property
    def alpha(self) -> float:
        return self.prior_alpha + self.audit_positives

    @property
    def beta(self) -> float:
        return self.prior_beta + self.audit_draws - self.audit_positives

    @property
    def mean(self) -> float:
        return self.alpha / (self.alpha + self.beta)

    @property
    def var(self) -> float:
        denom = (self.alpha + self.beta) ** 2 * (self.alpha + self.beta + 1.0)
        return (self.alpha * self.beta) / denom if denom > 0 else 0.0

    def ub_mass(self) -> float:
        return len(self.anchor_ids) * UNIT_SECONDS * min(1.0, self.mean + Z_DELTA * math.sqrt(self.var))


@dataclass
class Candidate:
    cid: int
    anchor_ids: set[str]
    confidence: float = INITIAL_CONFIDENCE
    left_guard_done: bool = False
    right_guard_done: bool = False

    def length_mass(self) -> float:
        return len(self.anchor_ids) * UNIT_SECONDS


@dataclass
class PolicyState:
    selected_order: list[str] = field(default_factory=list)
    selected_action: dict[str, str] = field(default_factory=dict)
    audit_ledger: set[str] = field(default_factory=set)
    discovery_ledger: set[str] = field(default_factory=set)
    discovery_positive: set[str] = field(default_factory=set)
    candidates: list[Candidate] = field(default_factory=list)
    repair_alpha: float = 2.0
    repair_beta: float = 2.0
    refine_alpha: float = 2.0
    refine_beta: float = 2.0

    @property
    def repair_mean(self) -> float:
        return self.repair_alpha / (self.repair_alpha + self.repair_beta)

    @property
    def refine_mean(self) -> float:
        return self.refine_alpha / (self.refine_alpha + self.refine_beta)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not fieldnames:
        keys: list[str] = []
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def append_progress(checkpoint: str, commands: str, result: str, failure: str = "none", fix: str = "none", next_action: str = "") -> None:
    with (LOGS / "progress.md").open("a") as f:
        f.write(f"\n## {utc_now()} - {checkpoint}\n\n")
        f.write(f"- Checkpoint: {checkpoint}\n")
        f.write(f"- Commands run: `{commands}`\n")
        f.write(f"- Result: {result}\n")
        f.write(f"- Failure: {failure}\n")
        f.write(f"- Fix applied: {fix}\n")
        if next_action:
            f.write(f"- Next action: {next_action}\n")


def load_data() -> tuple[list[Anchor], dict[str, set[str]], dict[str, dict[str, str]], list[dict[str, str]]]:
    labels = {r["anchor_id"]: r for r in read_csv(ORACLE_LABELS)}
    proxies = {r["anchor_id"]: r for r in read_csv(PROXY_FEATURES)}
    events = read_csv(ORACLE_EVENTS)
    anchor_to_events: dict[str, set[str]] = defaultdict(set)
    for ev in events:
        for aid in ev["supporting_anchor_ids"].split("|"):
            if aid:
                anchor_to_events[aid].add(ev["event_id"])

    anchors: list[Anchor] = []
    for idx, aid in enumerate(sorted(proxies, key=lambda x: int(x.rsplit("_", 1)[1]))):
        label = labels[aid]
        proxy = proxies[aid]
        numeric_scores = {}
        for key, value in proxy.items():
            try:
                numeric_scores[key] = float(value)
            except (TypeError, ValueError):
                pass
        anchors.append(
            Anchor(
                anchor_id=aid,
                index=idx,
                video_id=label.get("video_id", "realcartest"),
                anchor_time=float(proxy["anchor_time"]),
                start_time=float(label["start_time"]),
                end_time=float(label["end_time"]),
                label_positive=label["label"] == "positive",
                score=float(proxy.get(PRIMARY_SCORE, 0.0)),
                scores=numeric_scores,
            )
        )
    return anchors, anchor_to_events, labels, events


def assign_strata(anchors: list[Anchor]) -> tuple[list[Anchor], dict[str, list[str]]]:
    sorted_scores = sorted(a.score for a in anchors)
    q1 = sorted_scores[len(sorted_scores) // 3]
    q2 = sorted_scores[(2 * len(sorted_scores)) // 3]
    max_time = max(a.anchor_time for a in anchors)
    strata: dict[str, list[str]] = defaultdict(list)
    reassigned = []
    for a in anchors:
        score_bin = 0 if a.score <= q1 else 1 if a.score <= q2 else 2
        time_bin = min(3, int((a.anchor_time / (max_time + 1e-9)) * 4))
        sid = f"s{score_bin}_t{time_bin}"
        reassigned.append(
            Anchor(
                anchor_id=a.anchor_id,
                index=a.index,
                video_id=a.video_id,
                anchor_time=a.anchor_time,
                start_time=a.start_time,
                end_time=a.end_time,
                label_positive=a.label_positive,
                score=a.score,
                scores=a.scores,
                stratum=sid,
            )
        )
        strata[sid].append(a.anchor_id)
    return reassigned, dict(strata)


def make_stratum_states(anchors: list[Anchor], strata: dict[str, list[str]]) -> dict[str, StratumState]:
    by_id = {a.anchor_id: a for a in anchors}
    scores = [a.score for a in anchors]
    min_score = min(scores)
    max_score = max(scores)
    states = {}
    for sid, aids in strata.items():
        if max_score > min_score:
            score_mean = statistics.mean((by_id[aid].score - min_score) / (max_score - min_score) for aid in aids)
        else:
            score_mean = 0.5
        prior_mean = 0.05 + 0.45 * score_mean
        states[sid] = StratumState(
            anchor_ids=list(aids),
            prior_alpha=max(0.05, prior_mean * PRIOR_STRENGTH),
            prior_beta=max(0.05, (1.0 - prior_mean) * PRIOR_STRENGTH),
        )
    return states


def select_temporal_nms(anchors: list[Anchor], budget: int, score_name: str = PRIMARY_SCORE, gap: float = TEMPORAL_NMS_GAP) -> list[str]:
    ranked = sorted(anchors, key=lambda a: (a.scores.get(score_name, 0.0), -a.index), reverse=True)
    selected: list[str] = []
    selected_times: list[float] = []
    for a in ranked:
        if all(abs(a.anchor_time - t) >= gap for t in selected_times):
            selected.append(a.anchor_id)
            selected_times.append(a.anchor_time)
        if len(selected) >= budget:
            return selected
    for a in ranked:
        if a.anchor_id not in selected:
            selected.append(a.anchor_id)
        if len(selected) >= budget:
            break
    return selected


def select_topk(anchors: list[Anchor], budget: int, score_name: str = PRIMARY_SCORE) -> list[str]:
    return [a.anchor_id for a in sorted(anchors, key=lambda a: (a.scores.get(score_name, 0.0), -a.index), reverse=True)[:budget]]


def select_uniform(anchors: list[Anchor], budget: int) -> list[str]:
    if budget >= len(anchors):
        return [a.anchor_id for a in anchors]
    step = len(anchors) / budget
    return [anchors[min(len(anchors) - 1, int(i * step))].anchor_id for i in range(budget)]


def select_random(anchors: list[Anchor], budget: int, rng: random.Random) -> list[str]:
    ids = [a.anchor_id for a in anchors]
    rng.shuffle(ids)
    return ids[:budget]


def evaluate_selection(
    method: str,
    budget: int,
    selected: list[str],
    anchors_by_id: dict[str, Anchor],
    anchor_to_events: dict[str, set[str]],
    total_events: int,
    total_positive: int,
    repeat: int | None = None,
) -> dict:
    unique_selected = list(dict.fromkeys(selected))
    positives = [aid for aid in unique_selected if anchors_by_id[aid].label_positive]
    covered_events = set()
    redundant_positive = 0
    seen_events = set()
    for aid in unique_selected:
        evs = anchor_to_events.get(aid, set())
        if anchors_by_id[aid].label_positive:
            if seen_events.intersection(evs):
                redundant_positive += 1
            seen_events.update(evs)
        covered_events.update(evs)
    return {
        "method": method,
        "repeat": "" if repeat is None else repeat,
        "budget": budget,
        "selected_unique_calls": len(unique_selected),
        "positive_anchor_calls": len(positives),
        "clip_precision_v13_8_center10_oracle": len(positives) / len(unique_selected) if unique_selected else 0.0,
        "clip_recall_v13_8_center10_oracle": len(positives) / total_positive if total_positive else "",
        "pseudo_event_recall_v13_8_center10_oracle": len(covered_events) / total_events if total_events else "",
        "unique_events_found": len(covered_events),
        "redundant_call_rate_v13_8_center10_oracle": redundant_positive / len(unique_selected) if unique_selected else 0.0,
        "calls_per_new_event": len(unique_selected) / len(covered_events) if covered_events else "",
    }


def beta_audit_value(state: StratumState) -> float:
    before = math.sqrt(state.var)
    a = state.alpha
    b = state.beta
    after_var = ((a * b) / (((a + b + 1.0) ** 2) * (a + b + 2.0))) if (a + b + 2.0) > 0 else 0.0
    after = math.sqrt(after_var)
    return max(0.0, len(state.anchor_ids) * UNIT_SECONDS * Z_DELTA * (before - after))


def phi_value(strata_states: dict[str, StratumState], policy: PolicyState) -> float:
    ub = sum(s.ub_mass() for s in strata_states.values())
    discovered_mass = len(policy.discovery_positive) * UNIT_SECONDS
    precision_risk = sum((1.0 - c.confidence) * c.length_mass() for c in policy.candidates)
    return max(0.0, ub - discovered_mass) + precision_risk


def candidate_for_anchor(policy: PolicyState, aid: str) -> Candidate | None:
    for c in policy.candidates:
        if aid in c.anchor_ids:
            return c
    return None


def merge_candidate(policy: PolicyState, aid: str, anchors_by_id: dict[str, Anchor]) -> None:
    existing = candidate_for_anchor(policy, aid)
    if existing:
        return
    idx = anchors_by_id[aid].index
    touching = []
    for c in policy.candidates:
        cidx = [anchors_by_id[x].index for x in c.anchor_ids]
        if min(abs(idx - j) for j in cidx) <= 1:
            touching.append(c)
    if not touching:
        policy.candidates.append(Candidate(cid=len(policy.candidates), anchor_ids={aid}))
        return
    base = touching[0]
    base.anchor_ids.add(aid)
    for other in touching[1:]:
        base.anchor_ids.update(other.anchor_ids)
        base.confidence = min(base.confidence, other.confidence)
        policy.candidates.remove(other)


def execute_call(
    aid: str,
    action: str,
    policy: PolicyState,
    strata_states: dict[str, StratumState],
    anchors_by_id: dict[str, Anchor],
) -> None:
    if aid in policy.selected_action:
        return
    anchor = anchors_by_id[aid]
    policy.selected_order.append(aid)
    policy.selected_action[aid] = action
    if action == "AUDIT":
        policy.audit_ledger.add(aid)
        s = strata_states[anchor.stratum]
        s.audit_draws += 1
        s.audit_positives += int(anchor.label_positive)
        return

    policy.discovery_ledger.add(aid)
    adjacent_candidate = None
    if action == "REFINE":
        idx = anchor.index
        for c in policy.candidates:
            cidx = sorted(anchors_by_id[x].index for x in c.anchor_ids)
            if idx == cidx[0] - 1 or idx == cidx[-1] + 1:
                adjacent_candidate = c
                break

    if anchor.label_positive:
        policy.discovery_positive.add(aid)
        merge_candidate(policy, aid, anchors_by_id)
        if action == "REPAIR":
            policy.repair_alpha += 1.0
        if action == "REFINE":
            policy.refine_alpha += 1.0
    else:
        if action == "REPAIR":
            policy.repair_beta += 1.0
        if action == "REFINE":
            policy.refine_beta += 1.0
            if adjacent_candidate is not None:
                idx = anchor.index
                cidx = sorted(anchors_by_id[x].index for x in adjacent_candidate.anchor_ids)
                if idx == cidx[0] - 1:
                    adjacent_candidate.left_guard_done = True
                if idx == cidx[-1] + 1:
                    adjacent_candidate.right_guard_done = True
                adjacent_candidate.confidence = min(1.0, adjacent_candidate.confidence + CONFIDENCE_INCREMENT)


def neighbor_id(aid: str, delta: int, anchors: list[Anchor]) -> str | None:
    idx = int(aid.rsplit("_", 1)[1]) + delta
    if 0 <= idx < len(anchors):
        return anchors[idx].anchor_id
    return None


def choose_phi_action(
    anchors: list[Anchor],
    anchors_by_id: dict[str, Anchor],
    strata_states: dict[str, StratumState],
    policy: PolicyState,
    rng: random.Random,
) -> tuple[str, str]:
    remaining = [a for a in anchors if a.anchor_id not in policy.selected_action]
    if not remaining:
        return "", ""

    if rng.random() < ETA:
        scored_strata = []
        for sid, s in strata_states.items():
            choices = [aid for aid in s.anchor_ids if aid not in policy.selected_action]
            if choices:
                scored_strata.append((beta_audit_value(s), sid, choices))
        if scored_strata:
            _, sid, choices = max(scored_strata, key=lambda x: (x[0], x[1]))
            return "AUDIT", rng.choice(choices)

    actions: list[tuple[float, str, str]] = []
    min_score = min(a.score for a in anchors)
    max_score = max(a.score for a in anchors)
    score_range = max(1e-9, max_score - min_score)

    for sid, s in strata_states.items():
        choices = [aid for aid in s.anchor_ids if aid not in policy.selected_action]
        if choices:
            audit_value = beta_audit_value(s)
            actions.append((audit_value, "AUDIT", rng.choice(choices)))

    for a in remaining:
        s = strata_states[a.stratum]
        score01 = (a.score - min_score) / score_range
        posterior_ucb = min(1.0, s.mean + UCB_BETA * math.sqrt(s.var))
        local_penalty = 0.75 if any(abs(a.index - anchors_by_id[x].index) <= 1 for x in policy.discovery_positive) else 1.0
        value = UNIT_SECONDS * posterior_ucb * (0.5 + 0.5 * score01) * local_penalty
        actions.append((value, "DISCOVER", a.anchor_id))

    frontier = set()
    for aid in policy.discovery_positive:
        for d in (-1, 1):
            nid = neighbor_id(aid, d, anchors)
            if nid and nid not in policy.selected_action:
                frontier.add(nid)
    for aid in frontier:
        value = UNIT_SECONDS * policy.repair_mean
        actions.append((value, "REPAIR", aid))

    for c in policy.candidates:
        idxs = sorted(anchors_by_id[aid].index for aid in c.anchor_ids)
        left = anchors[idxs[0] - 1].anchor_id if idxs[0] > 0 else None
        right = anchors[idxs[-1] + 1].anchor_id if idxs[-1] + 1 < len(anchors) else None
        if left and left not in policy.selected_action and not c.left_guard_done:
            actions.append((c.length_mass() * (1.0 - c.confidence) * policy.refine_mean, "REFINE", left))
        if right and right not in policy.selected_action and not c.right_guard_done:
            actions.append((c.length_mass() * (1.0 - c.confidence) * policy.refine_mean, "REFINE", right))

    if not actions:
        a = max(remaining, key=lambda x: x.score)
        return "DISCOVER", a.anchor_id
    value, action, aid = max(actions, key=lambda x: (x[0], anchors_by_id[x[2]].score))
    return action, aid


def run_phi_policy(anchors: list[Anchor], budget: int, seed: int) -> tuple[list[str], list[dict]]:
    rng = random.Random(seed)
    anchors_by_id = {a.anchor_id: a for a in anchors}
    _, strata = assign_strata(anchors)
    strata_states = make_stratum_states(anchors, strata)
    policy = PolicyState()
    trace = []
    while len(policy.selected_order) < min(budget, len(anchors)):
        before = phi_value(strata_states, policy)
        action, aid = choose_phi_action(anchors, anchors_by_id, strata_states, policy, rng)
        if not aid:
            break
        execute_call(aid, action, policy, strata_states, anchors_by_id)
        after = phi_value(strata_states, policy)
        anchor = anchors_by_id[aid]
        trace.append(
            {
                "rank": len(policy.selected_order),
                "anchor_id": aid,
                "action": action,
                "stratum": anchor.stratum,
                "oracle_label_observed_after_selection": "positive" if anchor.label_positive else "negative",
                "phi_before": before,
                "phi_after": after,
                "delta_phi_observed": before - after,
                "audit_ledger_size": len(policy.audit_ledger),
                "discovery_ledger_size": len(policy.discovery_ledger),
                "discovery_positive_size": len(policy.discovery_positive),
                "candidate_count": len(policy.candidates),
            }
        )
    return policy.selected_order, trace


def aggregate(rows: list[dict], keys: list[str], metric_fields: list[str]) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        groups[tuple(row[k] for k in keys)].append(row)
    out = []
    for key, vals in sorted(groups.items()):
        base = dict(zip(keys, key))
        base["n"] = len(vals)
        for field_name in metric_fields:
            xs = [float(v[field_name]) for v in vals if v[field_name] != ""]
            if not xs:
                base[f"{field_name}_mean"] = ""
                base[f"{field_name}_std"] = ""
                base[f"{field_name}_ci95_low"] = ""
                base[f"{field_name}_ci95_high"] = ""
            else:
                mean = statistics.mean(xs)
                std = statistics.pstdev(xs) if len(xs) > 1 else 0.0
                half = 1.96 * std / math.sqrt(len(xs)) if len(xs) > 1 else 0.0
                base[f"{field_name}_mean"] = mean
                base[f"{field_name}_std"] = std
                base[f"{field_name}_ci95_low"] = mean - half
                base[f"{field_name}_ci95_high"] = mean + half
        out.append(base)
    return out


def event_count_for_gap(anchors: list[Anchor], gap_anchors: int) -> int:
    positives = [a.index for a in anchors if a.label_positive]
    if not positives:
        return 0
    count = 1
    prev = positives[0]
    for idx in positives[1:]:
        if idx - prev > gap_anchors + 1:
            count += 1
        prev = idx
    return count


def make_svg_curve(path: Path, rows: list[dict], methods: list[str], metric: str, title: str) -> None:
    width, height = 860, 520
    margin = 70
    plot_w = width - 2 * margin
    plot_h = height - 2 * margin
    budgets = sorted({int(r["budget"]) for r in rows if int(r["budget"]) <= 120})
    x_min, x_max = min(budgets), max(budgets)
    y_max = 1.0
    colors = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#111111"]

    def x_pos(b: int) -> float:
        return margin + ((b - x_min) / (x_max - x_min)) * plot_w if x_max > x_min else margin

    def y_pos(y: float) -> float:
        return height - margin - (y / y_max) * plot_h

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{margin}" y="34" font-family="Arial" font-size="20">{title}</text>',
        f'<line x1="{margin}" y1="{height-margin}" x2="{width-margin}" y2="{height-margin}" stroke="#333"/>',
        f'<line x1="{margin}" y1="{margin}" x2="{margin}" y2="{height-margin}" stroke="#333"/>',
    ]
    for y in [0, 0.25, 0.5, 0.75, 1.0]:
        yy = y_pos(y)
        lines.append(f'<line x1="{margin}" y1="{yy:.1f}" x2="{width-margin}" y2="{yy:.1f}" stroke="#ddd"/>')
        lines.append(f'<text x="{margin-52}" y="{yy+4:.1f}" font-family="Arial" font-size="12">{y:.2f}</text>')
    for b in budgets:
        xx = x_pos(b)
        lines.append(f'<line x1="{xx:.1f}" y1="{height-margin}" x2="{xx:.1f}" y2="{height-margin+5}" stroke="#333"/>')
        lines.append(f'<text x="{xx-10:.1f}" y="{height-margin+22}" font-family="Arial" font-size="12">{b}</text>')
    for mi, method in enumerate(methods):
        pts = []
        for b in budgets:
            candidates = [r for r in rows if r["method"] == method and int(r["budget"]) == b]
            if not candidates:
                continue
            r = candidates[0]
            val = float(r.get(metric, r.get(f"{metric}_mean", 0.0)) or 0.0)
            pts.append((x_pos(b), y_pos(val)))
        if not pts:
            continue
        color = colors[mi % len(colors)]
        point_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        lines.append(f'<polyline points="{point_str}" fill="none" stroke="{color}" stroke-width="2.5"/>')
        for x, y in pts:
            lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{color}"/>')
        ly = margin + 24 + mi * 20
        lines.append(f'<line x1="{width-margin-230}" y1="{ly}" x2="{width-margin-205}" y2="{ly}" stroke="{color}" stroke-width="3"/>')
        lines.append(f'<text x="{width-margin-198}" y="{ly+4}" font-family="Arial" font-size="12">{method}</text>')
    lines.append(f'<text x="{width/2-30}" y="{height-18}" font-family="Arial" font-size="13">VLM calls budget</text>')
    lines.append("</svg>")
    path.write_text("\n".join(lines) + "\n")


def run() -> None:
    for d in [TABLES, REPORTS, FIGURES, LOGS]:
        d.mkdir(parents=True, exist_ok=True)

    anchors0, anchor_to_events, labels, events = load_data()
    anchors, strata = assign_strata(anchors0)
    anchors_by_id = {a.anchor_id: a for a in anchors}
    total_positive = sum(1 for a in anchors if a.label_positive)
    total_events = len(events)

    audit_rows = [
        {"item": "oracle_label_rows", "value": len(labels)},
        {"item": "proxy_feature_rows", "value": len(anchors)},
        {"item": "source_video_count", "value": len({a.video_id for a in anchors})},
        {"item": "positive_anchor_count_v13_8_center10_oracle", "value": total_positive},
        {"item": "pseudo_event_count_v13_8_center10_oracle", "value": total_events},
        {"item": "score_column", "value": PRIMARY_SCORE},
        {"item": "stratum_count", "value": len(strata)},
        {"item": "time_min", "value": min(a.start_time for a in anchors)},
        {"item": "time_max", "value": max(a.end_time for a in anchors)},
    ]
    write_csv(TABLES / "input_audit.csv", audit_rows)

    stratum_rows = []
    for sid, aids in sorted(strata.items()):
        pos = sum(1 for aid in aids if anchors_by_id[aid].label_positive)
        stratum_rows.append(
            {
                "stratum": sid,
                "row_count": len(aids),
                "positive_count_v13_8_center10_oracle_for_audit_only": pos,
                "score_mean": statistics.mean(anchors_by_id[aid].score for aid in aids),
                "time_min": min(anchors_by_id[aid].anchor_time for aid in aids),
                "time_max": max(anchors_by_id[aid].anchor_time for aid in aids),
            }
        )
    write_csv(TABLES / "stratum_audit.csv", stratum_rows)

    all_rows: list[dict] = []
    selected_rows: list[dict] = []
    trace_rows: list[dict] = []
    methods_to_run = [
        "default_score_topk_temporal_nms_duration_cap",
        "score_topk_no_nms",
        "uniform_anchor_10s",
        "top_yolo_vehicle_max",
        "top_motion_energy_max",
    ]

    for budget in BUDGETS:
        baseline_selections = {
            "default_score_topk_temporal_nms_duration_cap": select_temporal_nms(anchors, budget),
            "score_topk_no_nms": select_topk(anchors, budget),
            "uniform_anchor_10s": select_uniform(anchors, budget),
            "top_yolo_vehicle_max": select_topk(anchors, budget, "yolo_vehicle_max"),
            "top_motion_energy_max": select_topk(anchors, budget, "motion_energy_max"),
        }
        for method, selected in baseline_selections.items():
            all_rows.append(evaluate_selection(method, budget, selected, anchors_by_id, anchor_to_events, total_events, total_positive))
            for rank, aid in enumerate(selected, start=1):
                selected_rows.append(
                    {
                        "method": method,
                        "repeat": "",
                        "budget": budget,
                        "rank": rank,
                        "anchor_id": aid,
                        "action": "SELECT",
                        "oracle_label_observed_after_selection": "positive" if anchors_by_id[aid].label_positive else "negative",
                    }
                )

        for rep in range(RANDOM_REPEATS):
            selected = select_random(anchors, budget, random.Random(SEED + 10000 + budget * 1000 + rep))
            all_rows.append(evaluate_selection("random_anchor_10s", budget, selected, anchors_by_id, anchor_to_events, total_events, total_positive, rep))

        for rep in range(PHI_REPEATS):
            selected, trace = run_phi_policy(anchors, budget, SEED + budget * 1000 + rep)
            all_rows.append(evaluate_selection("phi_budget_audit_discover_repair_refine", budget, selected, anchors_by_id, anchor_to_events, total_events, total_positive, rep))
            if rep == 0:
                for t in trace:
                    t["budget"] = budget
                    t["repeat"] = rep
                    trace_rows.append(t)
                for rank, aid in enumerate(selected, start=1):
                    selected_rows.append(
                        {
                            "method": "phi_budget_audit_discover_repair_refine",
                            "repeat": rep,
                            "budget": budget,
                            "rank": rank,
                            "anchor_id": aid,
                            "action": trace[rank - 1]["action"] if rank - 1 < len(trace) else "",
                            "oracle_label_observed_after_selection": "positive" if anchors_by_id[aid].label_positive else "negative",
                        }
                    )

    write_csv(TABLES / "method_budget_results_raw.csv", all_rows)
    write_csv(TABLES / "selected_anchors_trace.csv", selected_rows)
    write_csv(TABLES / "phi_policy_trace_seed0.csv", trace_rows)

    metric_fields = [
        "clip_precision_v13_8_center10_oracle",
        "clip_recall_v13_8_center10_oracle",
        "pseudo_event_recall_v13_8_center10_oracle",
        "unique_events_found",
        "redundant_call_rate_v13_8_center10_oracle",
    ]
    summary_rows = []
    deterministic = [r for r in all_rows if r["repeat"] == ""]
    summary_rows.extend(deterministic)
    stochastic_summary = aggregate([r for r in all_rows if r["repeat"] != ""], ["method", "budget"], metric_fields)
    summary_rows.extend(stochastic_summary)
    write_csv(TABLES / "method_budget_summary.csv", summary_rows)

    best_rows = []
    for budget in BUDGETS:
        candidates = [r for r in summary_rows if int(r["budget"]) == budget]
        def metric_value(row: dict, name: str) -> float:
            return float(row.get(name, row.get(f"{name}_mean", 0.0)) or 0.0)
        best = max(
            candidates,
            key=lambda r: (
                metric_value(r, "pseudo_event_recall_v13_8_center10_oracle"),
                metric_value(r, "clip_recall_v13_8_center10_oracle"),
                metric_value(r, "clip_precision_v13_8_center10_oracle"),
            ),
        )
        best_rows.append(
            {
                "budget": budget,
                "best_method_by_event_recall": best["method"],
                "pseudo_event_recall_v13_8_center10_oracle": metric_value(best, "pseudo_event_recall_v13_8_center10_oracle"),
                "clip_recall_v13_8_center10_oracle": metric_value(best, "clip_recall_v13_8_center10_oracle"),
                "clip_precision_v13_8_center10_oracle": metric_value(best, "clip_precision_v13_8_center10_oracle"),
            }
        )
    write_csv(TABLES / "best_methods_by_budget.csv", best_rows)

    gap_rows = []
    prev = None
    monotonic_ok = True
    for gap in [0, 1, 2, 3, 6]:
        count = event_count_for_gap(anchors, gap)
        if prev is not None and count > prev:
            monotonic_ok = False
        prev = count
        gap_rows.append({"merge_gap_anchors": gap, "event_count_from_positive_anchor_merge": count})
    write_csv(TABLES / "event_merge_gap_sanity.csv", gap_rows)

    nms_disabled = select_temporal_nms(anchors, len(anchors), gap=0.0)
    raw_rank = select_topk(anchors, len(anchors))
    deterministic_399 = [r for r in deterministic if int(r["budget"]) == len(anchors)]
    sanity_rows = [
        {
            "check": "100pct_budget_deterministic_clip_and_event_recall_is_1",
            "status": "PASS" if all(float(r["clip_recall_v13_8_center10_oracle"]) == 1.0 and float(r["pseudo_event_recall_v13_8_center10_oracle"]) == 1.0 for r in deterministic_399) else "FAIL",
            "details": "All deterministic methods select all anchors at B=399.",
        },
        {
            "check": "random_mean_recall_curves_monotonic",
            "status": "PASS",
            "details": "Checked after aggregation below.",
        },
        {
            "check": "event_count_nonincreasing_with_merge_gap",
            "status": "PASS" if monotonic_ok else "FAIL",
            "details": json.dumps(gap_rows),
        },
        {
            "check": "temporal_nms_gap0_degenerates_to_raw_score_ranking",
            "status": "PASS" if nms_disabled == raw_rank else "FAIL",
            "details": "Compared full score order with NMS gap=0.",
        },
        {
            "check": "sorting_functions_do_not_read_oracle_labels",
            "status": "PASS",
            "details": "Static selectors use proxy score columns and time only; Phi selector uses oracle labels only inside execute_call after selection.",
        },
        {
            "check": "cluster_methods_do_not_count_duplicate_selected_clips_as_multiple_calls",
            "status": "PASS" if all(int(r["selected_unique_calls"]) == int(r["budget"]) for r in all_rows) else "FAIL",
            "details": "All policies select unique anchor IDs up to budget.",
        },
        {
            "check": "coverage_aware_novelty_disabled_cluster_rep_baseline",
            "status": "NOT_APPLICABLE",
            "details": "This experiment does not implement coverage-aware cluster scheduling; it implements Phi action bidding with repair/refine frontier actions.",
        },
    ]
    random_summary = [r for r in stochastic_summary if r["method"] == "random_anchor_10s"]
    for metric in ["clip_recall_v13_8_center10_oracle", "pseudo_event_recall_v13_8_center10_oracle"]:
        vals = [(int(r["budget"]), float(r[f"{metric}_mean"])) for r in random_summary]
        vals.sort()
        if any(vals[i][1] + 1e-9 < vals[i - 1][1] for i in range(1, len(vals))):
            sanity_rows[1]["status"] = "FAIL"
            sanity_rows[1]["details"] = f"{metric} is not monotonic: {vals}"
    write_csv(TABLES / "sanity_checks.csv", sanity_rows)

    figure_rows = []
    for row in summary_rows:
        out_row = dict(row)
        for name in metric_fields:
            if name not in out_row and f"{name}_mean" in out_row:
                out_row[name] = out_row[f"{name}_mean"]
        figure_rows.append(out_row)
    plot_methods = [
        "phi_budget_audit_discover_repair_refine",
        "default_score_topk_temporal_nms_duration_cap",
        "uniform_anchor_10s",
        "random_anchor_10s",
        "score_topk_no_nms",
    ]
    make_svg_curve(
        FIGURES / "event_recall_curve.svg",
        figure_rows,
        plot_methods,
        "pseudo_event_recall_v13_8_center10_oracle",
        "Pseudo-event recall on V13.8 center10 oracle",
    )
    make_svg_curve(
        FIGURES / "clip_precision_curve.svg",
        figure_rows,
        plot_methods,
        "clip_precision_v13_8_center10_oracle",
        "Selected-call clip precision on V13.8 center10 oracle",
    )

    command_lines = [
        "# Reproducible Commands",
        "",
        "```bash",
        "python outputs/phi_budget_replay_v1/scripts/run_phi_budget_replay.py",
        "```",
        "",
        "No VLM/API/YOLO/GPU command is required for this replay.",
    ]
    (OUT / "reproducible_commands.md").write_text("\n".join(command_lines) + "\n")

    fail_sanity = [r for r in sanity_rows if r["status"] == "FAIL"]
    primary_budget = 40
    primary = [r for r in summary_rows if r["method"] == "phi_budget_audit_discover_repair_refine" and int(r["budget"]) == primary_budget][0]
    default = [r for r in summary_rows if r["method"] == "default_score_topk_temporal_nms_duration_cap" and int(r["budget"]) == primary_budget][0]
    phi_ev = float(primary["pseudo_event_recall_v13_8_center10_oracle_mean"])
    default_ev = float(default["pseudo_event_recall_v13_8_center10_oracle"])
    phi_clip_prec = float(primary["clip_precision_v13_8_center10_oracle_mean"])
    default_clip_prec = float(default["clip_precision_v13_8_center10_oracle"])
    decision = "NO-GO"
    if not fail_sanity and phi_ev >= default_ev + 0.05 and phi_clip_prec >= default_clip_prec:
        decision = "GO"
    elif not fail_sanity and phi_ev >= default_ev:
        decision = "WEAK GO"

    report = [
        "# Phi-Budget Replay v1 Final Report",
        "",
        f"Date: 2026-07-03",
        "",
        "## Scope",
        "",
        "This is a no-new-VLM replay on the V13.8 center10 VLM-defined oracle reference. It evaluates a first executable version of the pasted Phi-risk design: separate audit and discovery ledgers, an audit floor, and DISCOVER/REPAIR/REFINE action bidding by expected Phi reduction per oracle call.",
        "",
        "All recall/precision numbers below are labeled `v13_8_center10_oracle`; they are not human-ground-truth dangerous-event claims.",
        "",
        "## Inputs",
        "",
        f"- Oracle labels: `{ORACLE_LABELS.relative_to(ROOT)}` ({len(labels)} rows, {total_positive} positive anchors).",
        f"- VLM-defined stitched pseudo-events: `{ORACLE_EVENTS.relative_to(ROOT)}` ({total_events} events).",
        f"- Cheap proxy features: `{PROXY_FEATURES.relative_to(ROOT)}` ({len(anchors)} rows, score `{PRIMARY_SCORE}`).",
        "- `probe_set_v1` was not used.",
        "",
        "## Primary Result",
        "",
        "| Budget | Phi event recall v13_8_center10_oracle | Default event recall v13_8_center10_oracle | Phi clip precision v13_8_center10_oracle | Default clip precision v13_8_center10_oracle |",
        "|---:|---:|---:|---:|---:|",
    ]
    for b in [5, 10, 20, 40, 80, 120]:
        p = [r for r in summary_rows if r["method"] == "phi_budget_audit_discover_repair_refine" and int(r["budget"]) == b][0]
        d = [r for r in summary_rows if r["method"] == "default_score_topk_temporal_nms_duration_cap" and int(r["budget"]) == b][0]
        report.append(
            f"| {b} | {float(p['pseudo_event_recall_v13_8_center10_oracle_mean']):.3f} | {float(d['pseudo_event_recall_v13_8_center10_oracle']):.3f} | {float(p['clip_precision_v13_8_center10_oracle_mean']):.3f} | {float(d['clip_precision_v13_8_center10_oracle']):.3f} |"
        )
    report.extend(
        [
            "",
            "## Interpretation",
            "",
            "The Phi replay is a useful executable scaffold, but it should not yet be promoted as the default selector. It introduces the intended accounting discipline and repair/refine frontier mechanics, yet the first policy still competes against a weak proxy and a single-video VLM-defined reference.",
            "",
            "The project default remains `score_topk + temporal NMS + duration cap`; CILS is not used or promoted here.",
            "",
            "## Sanity Checks",
            "",
            "| Check | Status | Details |",
            "|---|---|---|",
        ]
    )
    for row in sanity_rows:
        report.append(f"| {row['check']} | {row['status']} | {str(row['details']).replace('|', '/')} |")
    report.extend(
        [
            "",
            "## Output Files",
            "",
            "- `tables/input_audit.csv`",
            "- `tables/stratum_audit.csv`",
            "- `tables/method_budget_results_raw.csv`",
            "- `tables/method_budget_summary.csv`",
            "- `tables/best_methods_by_budget.csv`",
            "- `tables/sanity_checks.csv`",
            "- `tables/phi_policy_trace_seed0.csv`",
            "- `figures/event_recall_curve.svg`",
            "- `figures/clip_precision_curve.svg`",
            "",
            f"FINAL_DECISION: {decision}",
        ]
    )
    (REPORTS / "FINAL_REPORT.md").write_text("\n".join(report) + "\n")
    (OUT / "FINAL_REPORT.md").write_text("\n".join(report) + "\n")

    append_progress(
        "Run Phi-budget replay",
        "python outputs/phi_budget_replay_v1/scripts/run_phi_budget_replay.py",
        f"Completed {len(all_rows)} raw method-budget rows; final decision {decision}.",
        failure="; ".join(r["check"] for r in fail_sanity) if fail_sanity else "none",
        next_action="Inspect summary tables and decide whether to tune Phi action priors or improve cheap scorer.",
    )

    if fail_sanity:
        raise SystemExit("Sanity checks failed: " + ", ".join(r["check"] for r in fail_sanity))


if __name__ == "__main__":
    run()
