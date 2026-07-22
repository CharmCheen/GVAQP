"""Finite-horizon SMDP generation and atomic transition engine."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path

from .costs import ToyBounds
from .grouping import assign_hypotheses
from .rng import SplitMix64
from .schema import Action, CommittedEvent, Episode, Event, Region, TraceEntry, VisibleState, Witness
from .serialization import sha256_value

ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS = ROOT / "outputs/psvr_rollout_preimplementation"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _split_config(split: str) -> tuple[dict, str, str]:
    construction_path = ARTIFACTS / "TOY_CONSTRUCTION_SPEC.json"
    parameter_path = ARTIFACTS / "TOY_PARAMETER_DISTRIBUTION.yaml"
    construction = json.loads(construction_path.read_text(encoding="utf-8"))
    return construction["split_parameters"][split], _sha(construction_path), _sha(parameter_path)


def generate_episode(seed: int, split: str, split_index: int) -> Episode:
    if split not in {"development", "heldout"}:
        raise ValueError("generated split must be development or heldout")
    cfg, construction_hash, parameter_hash = _split_config(split)
    rng = SplitMix64(seed)
    process = ["UNIFORM_SPARSE", "UNIFORM_DENSE", "BURSTY_CLUSTERED"][split_index % 3]
    cost_regime = ["SCAN_CHEAP", "BALANCED", "SCAN_EXPENSIVE"][(split_index // 3) % 3]
    m = int(rng.categorical(cfg["M"]["values"], cfg["M"]["weights"]))
    density = rng.log_uniform(*cfg["density_by_process"][process])
    quality = rng.uniform(*cfg["candidate_quality"])
    duplicate_factor = rng.log_uniform(*cfg["duplicate_factor"])
    cost_variance = rng.uniform(*cfg["cost_variance"])
    ratio_ranges = {"SCAN_CHEAP": (0.05, 0.30), "BALANCED": (0.30, 1.50), "SCAN_EXPENSIVE": (1.50, 5.00)}
    ratio = rng.log_uniform(*ratio_ranges[cost_regime])
    under_rate = rng.uniform(*cfg["under_merge_rate"])
    over_rate = rng.uniform(*cfg["over_merge_rate"])
    hard_negative_rate = rng.uniform(*cfg["hard_negative_rate"])
    horizon_units = rng.categorical([1.25, 1.5, 2, 3, 4, 6, 8, 12, 16, 24, 32], [1 / 11] * 11)
    horizon = 5.0 * horizon_units
    event_count = rng.poisson(m * density)
    cluster_centers: list[int] = []
    if process == "BURSTY_CLUSTERED":
        cluster_centers = [int(math.floor(m * rng.uniform01())) for _ in range(1 + rng.poisson(1.0))]
    actor_count = int(rng.categorical([1, 2, 3], [0.75, 0.20, 0.05]))
    media_duration = 10.0 * m
    events: list[Event] = []
    for event_index in range(event_count):
        if process == "BURSTY_CLUSTERED":
            center = cluster_centers[int(math.floor(len(cluster_centers) * rng.uniform01()))]
            offset = int(_clip(math.floor(4 * (rng.uniform01() + rng.uniform01() - 1)), -4, 4))
            region_index = int(_clip(center + offset, 0, m - 1))
        else:
            region_index = min(m - 1, int(math.floor(m * rng.uniform01())))
        start = 10.0 * region_index + 10.0 * rng.uniform01()
        length = min(media_duration - start, rng.log_uniform(0.5, 40.0))
        end = start + length
        region_ids = tuple(f"r{i:04d}" for i in range(m) if 10 * i < end and 10 * (i + 1) > start)
        actor = int(math.floor(actor_count * rng.uniform01()))
        detectability = _clip(quality + 0.25 * (2 * rng.uniform01() - 1), 0.01, 0.99)
        multiplicity = 1 + rng.poisson(duplicate_factor - 1.0)
        events.append(Event(f"e{event_index:04d}", region_ids, start, end, f"actor_{actor:04d}", detectability, multiplicity))

    rows: list[dict] = []
    region_activities: list[float] = []
    scan_core: list[float] = []
    creation = 0
    for region_index in range(m):
        region_id = f"r{region_index:04d}"
        activity = rng.uniform(0.5, 2.0)
        region_activities.append(activity)
        scan_nominal = 5.0 * ratio * (0.75 + 0.5 * activity / 2.0)
        scan_core.append(scan_nominal * (1.0 - cost_variance + 2.0 * cost_variance * int(rng.bernoulli(0.5))))
        for event in events:
            if region_id not in event.region_ids:
                continue
            for _ in range(event.multiplicity):
                if not rng.bernoulli(event.detectability):
                    continue
                start = _clip(event.start + rng.uniform(-1, 1), 0, media_duration)
                end = _clip(event.end + rng.uniform(-1, 1), 0, media_duration)
                start, end = sorted((start, end))
                raw = quality + (1.0 - quality) * rng.uniform01()
                rows.append({"witness_id": f"w_{region_index:04d}_{creation:04d}", "region_id": region_id, "latent_event_id": event.event_id, "interval": (start, end), "raw_score": raw, "proxy_features": (raw, (start + end) / (2 * media_duration), (end - start) / 40.0, activity / 2.0), "creation_order": creation})
                creation += 1
        for _ in range(rng.poisson(hard_negative_rate * activity)):
            start = 10.0 * region_index + 10.0 * rng.uniform01()
            end = min(10.0 * (region_index + 1), start + rng.uniform(0.5, 4.0))
            raw = (1.0 - quality) * rng.uniform01()
            rows.append({"witness_id": f"w_{region_index:04d}_{creation:04d}", "region_id": region_id, "latent_event_id": None, "interval": (start, end), "raw_score": raw, "proxy_features": (raw, (start + end) / (2 * media_duration), (end - start) / 40.0, activity / 2.0), "creation_order": creation})
            creation += 1
    assign_hypotheses(rows, under_rate, over_rate, rng)
    witnesses: list[Witness] = []
    for row in sorted(rows, key=lambda x: x["witness_id"]):
        nominal = 5.0 * (0.5 + rng.uniform01())
        duration = nominal * (1.0 - cost_variance + 2.0 * cost_variance * int(rng.bernoulli(0.5)))
        witnesses.append(Witness(row["witness_id"], row["hypothesis_id"], row["region_id"], "q", row["interval"], row["proxy_features"], row["raw_score"], row["creation_order"], duration, nominal * (1.0 + cost_variance) + 0.25, row["latent_event_id"]))
    by_region = {f"r{i:04d}": [] for i in range(m)}
    for witness in witnesses:
        by_region[witness.region_id].append(witness.witness_id)
    regions = tuple(Region(f"r{i:04d}", 10.0 * i, 10.0 * (i + 1), scan_core[i], 5.0 * ratio * (0.75 + 0.5 * region_activities[i] / 2.0) * (1.0 + cost_variance) + 0.25, tuple(by_region[f"r{i:04d}"])) for i in range(m))
    episode = Episode(f"{split}_{seed}", seed, split, split_index, horizon, "q", process, cost_regime, cost_variance, ToyBounds().standard_confirm_reserve, regions, tuple(events), tuple(witnesses), construction_hash, parameter_hash)
    _validate_episode_support(episode)
    return episode


def load_named_scenario(scenario_id: str) -> Episode:
    path = ARTIFACTS / "TOY_NAMED_SCENARIOS.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    spec = next((row for row in payload["scenarios"] if row["scenario_id"] == scenario_id), None)
    if spec is None:
        raise KeyError(scenario_id)
    group_by_witness = {wid: hid for hid, members in spec["initial_hypothesis_members"].items() for wid in members}
    rows = []
    for row in spec["initial_frontier_witnesses"]:
        rows.append(("__initial__", row))
    for region_id, emitted in spec["scan_emissions"].items():
        rows.extend((region_id, row) for row in emitted)
    witnesses = []
    for order, (region_id, row) in enumerate(rows):
        wid = row["witness_id"]
        interval = tuple(float(x) for x in row["interval"])
        core = float(spec["confirm_cost_seconds_by_witness"].get(wid, 2.0))
        witnesses.append(Witness(wid, group_by_witness.get(wid, f"h_{wid}"), region_id, row["query_id"], interval, (float(row["raw_score"]), 0.0, max(0.0, interval[1]-interval[0])/40.0, 0.5), float(row["raw_score"]), order, core, core + 0.25, row["latent_event_id"]))
    events = tuple(Event(row["event_id"], (row["region_id"],), float(row["interval"][0]), float(row["interval"][1]), row["actor_id"], 1.0, 1) for row in spec["latent_events"])
    ids_by_region = {row["region_id"]: [] for row in spec["regions"]}
    for witness in witnesses:
        if witness.region_id in ids_by_region:
            ids_by_region[witness.region_id].append(witness.witness_id)
    regions = tuple(Region(row["region_id"], float(row["interval"][0]), float(row["interval"][1]), float(row["scan_cost_seconds"]), float(row["scan_cost_seconds"]) + 0.25, tuple(ids_by_region[row["region_id"]])) for row in spec["regions"])
    reserve = max((w.confirm_support_upper for w in witnesses), default=0.25)
    episode = Episode(f"named_{scenario_id}", 0, "named", -1, float(spec["horizon_seconds"]), "q", "NAMED", "NAMED", 0.0, reserve, regions, events, tuple(witnesses), _sha(ARTIFACTS / "TOY_CONSTRUCTION_SPEC.json"), _sha(ARTIFACTS / "TOY_PARAMETER_DISTRIBUTION.yaml"), scenario_id)
    _validate_episode_support(episode)
    return episode


def _validate_episode_support(episode: Episode) -> None:
    bounds = ToyBounds()
    if any(region.scan_core_duration > bounds.scan_core_upper + 1e-12 or region.scan_core_duration < 0 for region in episode.regions):
        raise ValueError("SCAN core duration outside frozen support")
    if any(region.scan_core_duration > region.scan_support_upper + 1e-12 or region.scan_support_upper > bounds.scan + 1e-12 for region in episode.regions):
        raise ValueError("SCAN support binding invalid")
    if any(w.confirm_core_duration > bounds.confirm_core_upper + 1e-12 or w.confirm_core_duration < 0 for w in episode.witnesses):
        raise ValueError("CONFIRM core duration outside frozen support")
    if any(w.confirm_core_duration > w.confirm_support_upper + 1e-12 or w.confirm_support_upper > bounds.confirm + 1e-12 for w in episode.witnesses):
        raise ValueError("CONFIRM support binding invalid")


class ToyEnvironment:
    """Atomic state machine. Policies only receive :meth:`visible_state`."""

    def __init__(self, episode: Episode):
        self.episode = episode
        self.bounds = ToyBounds()
        self.elapsed = 0.0
        self.mode = "INITIAL"
        self.scanned: set[str] = set()
        self.emitted: set[str] = {w.witness_id for w in episode.witnesses if w.region_id == "__initial__"}
        self.terminal_witnesses: set[str] = set()
        self.closed_hypotheses: set[str] = set()
        self.committed: list[CommittedEvent] = []
        self.trace: list[TraceEntry] = []
        self.stopped = False
        self._witness = {w.witness_id: w for w in episode.witnesses}
        self._event = {e.event_id: e for e in episode.events}
        self._region = {r.region_id: r for r in episode.regions}

    def clone(self) -> "ToyEnvironment":
        return copy.deepcopy(self)

    @property
    def remaining(self) -> float:
        return max(0.0, self.episode.horizon - self.elapsed)

    def visible_state(self) -> VisibleState:
        frontier = tuple(sorted((self._witness[wid].visible() for wid in self.emitted if wid not in self.terminal_witnesses and self._witness[wid].hypothesis_id not in self.closed_hypotheses), key=lambda w: (w.creation_order, w.hypothesis_id, w.witness_id)))
        next_region = next((r.region_id for r in self.episode.regions if r.region_id not in self.scanned), None)
        next_scan_bound = self._region[next_region].scan_support_upper if next_region is not None else self.bounds.scan
        return VisibleState(self.elapsed, self.remaining, self.mode, tuple(sorted(self.scanned)), next_region, len(self.episode.regions) - len(self.scanned), frontier, tuple(sorted(self.terminal_witnesses)), tuple(self.committed), next_scan_bound, self.episode.standard_confirm_reserve, self.episode.standard_confirm_reserve, self.episode.query_id)

    def safe_actions(self) -> tuple[Action, ...]:
        state = self.visible_state()
        if self.stopped:
            return (Action.stop(),)
        actions = [Action.confirm(w.hypothesis_id, w.witness_id) for w in state.frontier if w.confirm_support_upper <= state.remaining]
        if state.next_region_id is not None and state.scan_bound + state.confirm_reserve <= state.remaining:
            actions.append(Action.scan(state.next_region_id))
        actions.append(Action.stop())
        return tuple(actions)

    def _duration(self, action: Action) -> float:
        switch = 0.0 if self.mode in {"INITIAL", action.kind} else self.bounds.mode_switch_upper
        if action.kind == "SCAN":
            return self._region[action.region_id].scan_core_duration + switch
        if action.kind == "CONFIRM":
            return self._witness[action.witness_id].confirm_core_duration + switch
        return 0.0

    def execute(self, action: Action) -> TraceEntry:
        if self.stopped and action.kind != "STOP":
            raise RuntimeError("episode already stopped")
        legal = {a.identifier for a in self.safe_actions()}
        if action.identifier not in legal:
            raise ValueError(f"unsafe or invalid action: {action.identifier}")
        start = self.elapsed
        before_mode = self.mode
        before_count = len(self.committed)
        suppressed: tuple[str, ...] = ()
        event_id = None
        outcome = "STOPPED"
        if action.kind == "STOP":
            self.stopped = True
        else:
            duration = self._duration(action)
            support = self._region[action.region_id].scan_support_upper if action.kind == "SCAN" else self._witness[action.witness_id].confirm_support_upper
            if duration > support + 1e-12 or start + duration > self.episode.horizon + 1e-12:
                raise AssertionError("D2-T bound/admission violation")
            self.elapsed = start + duration
            self.mode = action.kind
            if action.kind == "SCAN":
                self.scanned.add(action.region_id)
                self.emitted.update(self._region[action.region_id].witness_ids)
                outcome = "SCANNED"
            else:
                witness = self._witness[action.witness_id]
                if witness.hypothesis_id != action.hypothesis_id:
                    raise ValueError("hypothesis/witness identity mismatch")
                members = tuple(sorted(w.witness_id for w in self.episode.witnesses if w.hypothesis_id == witness.hypothesis_id))
                self.closed_hypotheses.add(witness.hypothesis_id)
                self.terminal_witnesses.update(members)
                suppressed = tuple(wid for wid in members if wid != witness.witness_id)
                event_id = witness.latent_event_id
                if event_id is None:
                    outcome = "ORACLE_NEGATIVE"
                elif any(c.event_id == event_id for c in self.committed):
                    outcome = "DUPLICATE"
                else:
                    event = self._event[event_id]
                    self.committed.append(CommittedEvent(f"commit_{len(self.committed):04d}", event_id, (event.start, event.end), self.elapsed, False))
                    outcome = "NEW_COMMIT"
        snapshot_hash = sha256_value([c for c in self.committed])
        entry = TraceEntry(len(self.trace), action, start, self.elapsed, self.elapsed - start, before_mode, self.mode, before_count, len(self.committed), outcome, event_id, suppressed, snapshot_hash)
        self.trace.append(entry)
        return entry

    def run(self, policy, max_steps: int = 100000) -> None:
        for _ in range(max_steps):
            action = policy.choose(self.visible_state(), self.safe_actions())
            self.execute(action)
            if action.kind == "STOP":
                return
        raise RuntimeError("properness failure: max_steps exceeded")

    def latent_for_evaluator(self) -> Episode:
        return self.episode
