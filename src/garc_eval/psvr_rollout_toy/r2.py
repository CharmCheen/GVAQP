"""R2 finite-support, exact visible-history toy environment.

This module intentionally does not import the legacy held-out seed universe.
An R2 world is a fully materialized finite latent state.  Policies receive only
``VisibleHistory`` and legal actions; the exact posterior is a filter over the
fixed, result-blind finite world library.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable


HORIZON_TICKS = 1600  # 160 seconds: the frozen top horizon-grid point.
SCAN_SUPPORT_TICKS = 565  # D2-T 56.5 seconds on a 0.1-second representation.
CONFIRM_SUPPORT_TICKS = 138  # D2-T 13.75 seconds on a 0.1-second representation.


@dataclass(frozen=True)
class Candidate:
    witness_id: str
    hypothesis_id: str
    score_bin: int
    actor_bin: int


@dataclass(frozen=True)
class RegionLatent:
    region_id: str
    scan_ticks: int
    candidates: tuple[Candidate, ...]
    confirm_ticks: tuple[int, ...]
    positive: tuple[bool, ...]
    event_tokens: tuple[str | None, ...]


@dataclass(frozen=True)
class World:
    world_id: str  # evaluator/planner-private; never placed in VisibleHistory
    process: str
    cost_regime: str
    quality_bin: int
    duplicate_bin: int
    grouping_bin: int
    density_bin: int
    cost_variance_bin: int
    regions: tuple[RegionLatent, ...]


@dataclass(frozen=True)
class ActionR2:
    kind: str
    region_id: str | None = None
    witness_id: str | None = None
    hypothesis_id: str | None = None

    @property
    def identifier(self) -> str:
        return f"{self.kind}:{self.region_id or ''}:{self.hypothesis_id or ''}:{self.witness_id or ''}"

    @classmethod
    def scan(cls, region_id: str) -> "ActionR2":
        return cls("SCAN", region_id=region_id)

    @classmethod
    def confirm(cls, hypothesis_id: str, witness_id: str) -> "ActionR2":
        return cls("CONFIRM", hypothesis_id=hypothesis_id, witness_id=witness_id)

    @classmethod
    def stop(cls) -> "ActionR2":
        return cls("STOP")


@dataclass(frozen=True)
class Observation:
    kind: str
    duration_ticks: int
    region_id: str | None
    witness_id: str | None
    hypothesis_id: str | None
    emitted: tuple[Candidate, ...]
    outcome: str
    committed_token: str | None


@dataclass(frozen=True)
class VisibleHistory:
    query_id: str
    horizon_ticks: int
    actions: tuple[ActionR2, ...] = ()
    observations: tuple[Observation, ...] = ()

    def append(self, action: ActionR2, observation: Observation) -> "VisibleHistory":
        return VisibleHistory(self.query_id, self.horizon_ticks, self.actions + (action,), self.observations + (observation,))

    @property
    def digest(self) -> str:
        return sha256(repr(self).encode()).hexdigest()


@dataclass(frozen=True)
class VisibleStateR2:
    elapsed_ticks: int
    remaining_ticks: int
    mode: str
    scanned_region_ids: tuple[str, ...]
    next_region_id: str | None
    frontier: tuple[Candidate, ...]
    committed_tokens: tuple[str, ...]
    stopped: bool


def _world(index: int) -> World:
    """Result-blind 288-cell quadrature over workload/cost/density/variance."""
    processes = ("UNIFORM_SPARSE", "UNIFORM_DENSE", "BURSTY_CLUSTERED")
    costs = ("SCAN_CHEAP", "BALANCED", "SCAN_EXPENSIVE")
    process = processes[index % 3]
    cost = costs[(index // 3) % 3]
    density_bin = (index // 9) % 8
    variance_bin = (index // 72) % 4
    scan_base = {"SCAN_CHEAP": 2, "BALANCED": 4, "SCAN_EXPENSIVE": 7}[cost]
    regions: list[RegionLatent] = []
    for r in range(16):
        # Sparse has fewer positives; dense and bursty retain their relative regimes.
        divisor = (13 - density_bin if process == "UNIFORM_SPARSE" else 9 - density_bin if process == "UNIFORM_DENSE" else 11 - density_bin)
        hit = ((r * 5 + index * 3) % divisor) == 0
        burst = process == "BURSTY_CLUSTERED" and r in {(index * 3) % 16, (index * 3 + 1) % 16}
        positive_count = 1 if hit or burst else 0
        duplicate = positive_count and ((index + r) % 3 == 0)
        hard_negative = (index + 2 * r) % 7 == 0
        kinds = (["positive"] * (positive_count + int(duplicate))) + (["negative"] if hard_negative else [])
        candidates = []
        positive = []
        tokens = []
        confirm = []
        for j, kind in enumerate(kinds):
            # grouping_bin changes visible grouping and can suppress same-group candidates.
            group = j // 2 if index % 4 in {0, 3} else j
            candidates.append(Candidate(f"w{r:02d}_{j}", f"h{r:02d}_{group}", (index + r + j) % 4, (r + index) % 3))
            positive.append(kind == "positive")
            tokens.append(f"commit-event-{r:02d}" if kind == "positive" else None)
            confirm.append(2 + ((index + r + j) % 3))
        candidates = tuple(candidates)
        positive = tuple(positive)
        tokens = tuple(tokens)
        confirm = tuple(confirm)
        regions.append(RegionLatent(f"r{r:02d}", scan_base + ((index + r) % 2), candidates, confirm, positive, tokens))
    return World(f"world-{index:03d}", process, cost, index % 4, index % 3, index % 4, density_bin, variance_bin, tuple(regions))


def finite_world_library() -> tuple[World, ...]:
    return tuple(_world(i) for i in range(288))


class R2Environment:
    """Deterministic transition system for one evaluator-private latent world."""

    def __init__(self, world: World):
        self._world = world
        self._elapsed = 0
        self._mode = "INITIAL"
        self._scanned: set[str] = set()
        self._frontier: dict[str, Candidate] = {}
        self._committed: set[str] = set()
        self._closed: set[str] = set()
        self._stopped = False
        self._history = VisibleHistory("q", HORIZON_TICKS)

    @property
    def history(self) -> VisibleHistory:
        return self._history

    def visible_state(self) -> VisibleStateR2:
        next_region = next((r.region_id for r in self._world.regions if r.region_id not in self._scanned), None)
        return VisibleStateR2(self._elapsed, HORIZON_TICKS - self._elapsed, self._mode, tuple(sorted(self._scanned)), next_region, tuple(sorted(self._frontier.values(), key=lambda x: x.witness_id)), tuple(sorted(self._committed)), self._stopped)

    def safe_actions(self) -> tuple[ActionR2, ...]:
        state = self.visible_state()
        if state.stopped:
            return (ActionR2.stop(),)
        # Admission is against the frozen D2-T complete-action support, never
        # the realized world duration or a profile-local empirical maximum.
        actions = [ActionR2.confirm(c.hypothesis_id, c.witness_id) for c in state.frontier if CONFIRM_SUPPORT_TICKS <= state.remaining_ticks]
        if state.next_region_id is not None and SCAN_SUPPORT_TICKS + CONFIRM_SUPPORT_TICKS <= state.remaining_ticks:
            actions.append(ActionR2.scan(state.next_region_id))
        return tuple(actions + [ActionR2.stop()])

    def _region(self, region_id: str) -> RegionLatent:
        return next(r for r in self._world.regions if r.region_id == region_id)

    def execute(self, action: ActionR2) -> Observation:
        if action.identifier not in {a.identifier for a in self.safe_actions()}:
            raise ValueError(f"illegal R2 action: {action.identifier}")
        if action.kind == "STOP":
            self._stopped = True
            obs = Observation("STOP", 0, None, None, None, (), "STOPPED", None)
        elif action.kind == "SCAN":
            region = self._region(action.region_id or "")
            if region.scan_ticks > SCAN_SUPPORT_TICKS or self._elapsed + region.scan_ticks > HORIZON_TICKS:
                raise AssertionError("D2-T SCAN admission violation")
            self._elapsed += region.scan_ticks
            self._mode = "SCAN"
            self._scanned.add(region.region_id)
            for candidate in region.candidates:
                self._frontier[candidate.witness_id] = candidate
            obs = Observation("SCAN", region.scan_ticks, region.region_id, None, None, region.candidates, "SCANNED", None)
        else:
            found = next(((r, i, c) for r in self._world.regions for i, c in enumerate(r.candidates) if c.witness_id == action.witness_id and c.hypothesis_id == action.hypothesis_id), None)
            if found is None:
                raise ValueError("unknown candidate")
            region, i, candidate = found
            duration = region.confirm_ticks[i]
            if duration > CONFIRM_SUPPORT_TICKS or self._elapsed + duration > HORIZON_TICKS:
                raise AssertionError("D2-T CONFIRM admission violation")
            self._elapsed += duration
            self._mode = "CONFIRM"
            self._closed.add(candidate.hypothesis_id)
            for wid, c in list(self._frontier.items()):
                if c.hypothesis_id == candidate.hypothesis_id:
                    del self._frontier[wid]
            token = region.event_tokens[i] if region.positive[i] else None
            if token is None:
                outcome = "ORACLE_NEGATIVE"
            elif token in self._committed:
                outcome = "DUPLICATE"
            else:
                self._committed.add(token)
                outcome = "NEW_COMMIT"
            obs = Observation("CONFIRM", duration, None, candidate.witness_id, candidate.hypothesis_id, (), outcome, token if outcome == "NEW_COMMIT" else None)
        self._history = self._history.append(action, obs)
        return obs

    def utility(self) -> int:
        total = 0
        completed = 0
        for obs in self._history.observations:
            completed += obs.duration_ticks
            if obs.outcome == "NEW_COMMIT":
                total += HORIZON_TICKS - completed
        return total

    def metrics(self) -> dict[str, float | int | bool]:
        completed = 0
        committed: set[str] = set()
        truth = {token for region in self._world.regions for token in region.event_tokens if token is not None}
        auc = 0.0
        previous = 0
        f1 = 0.0
        ttfc = HORIZON_TICKS
        duplicates = 0
        for observation in self._history.observations:
            completed += observation.duration_ticks
            if observation.outcome == "DUPLICATE":
                duplicates += 1
            if observation.outcome == "NEW_COMMIT" and observation.committed_token is not None:
                auc += f1 * (completed - previous)
                previous = completed
                committed.add(observation.committed_token)
                recall = len(committed) / len(truth) if truth else 1.0
                f1 = recall  # perfect H-ROLLOUT1A Oracle/materialization means precision is one.
                ttfc = min(ttfc, completed)
        auc += f1 * (HORIZON_TICKS - previous)
        return {
            "primary_utility": self.utility(),
            "AnytimeAUC_F1": auc / HORIZON_TICKS,
            "TTFC": ttfc,
            "TTFC_no_commit": ttfc == HORIZON_TICKS,
            "unique_committed_events_at_T": len(committed),
            "event_recall_at_T": len(committed) / len(truth) if truth else 1.0,
            "duplicate_CONFIRM_count": duplicates,
        }


class ShieldedPi0R2:
    policy_id = "B1_SHIELDED_PI0"

    def choose(self, history: VisibleHistory, actions: Iterable[ActionR2]) -> ActionR2:
        options = tuple(actions)
        confirms = sorted((a for a in options if a.kind == "CONFIRM"), key=lambda a: (a.hypothesis_id or "", a.witness_id or ""))
        if confirms:
            return confirms[0]
        scans = sorted((a for a in options if a.kind == "SCAN"), key=lambda a: a.region_id or "")
        return scans[0] if scans else ActionR2.stop()


class ScanThenConfirmR2:
    policy_id = "B0_SCAN_THEN_CONFIRM"

    def choose(self, history: VisibleHistory, actions: Iterable[ActionR2]) -> ActionR2:
        options = tuple(actions)
        scans = sorted((a for a in options if a.kind == "SCAN"), key=lambda a: a.region_id or "")
        if scans:
            return scans[0]
        return ShieldedPi0R2().choose(history, options)


class FixedPeriodicR2:
    def __init__(self, period: int):
        self.period = period
        self.policy_id = f"B2_FIXED_PERIODIC_K{period}"

    def choose(self, history: VisibleHistory, actions: Iterable[ActionR2]) -> ActionR2:
        options = tuple(actions)
        scans_done = sum(action.kind == "SCAN" for action in history.actions)
        confirms = [a for a in options if a.kind == "CONFIRM"]
        if confirms and scans_done and scans_done % self.period == 0:
            return ShieldedPi0R2().choose(history, options)
        scans = [a for a in options if a.kind == "SCAN"]
        return sorted(scans, key=lambda a: a.region_id or "")[0] if scans else ShieldedPi0R2().choose(history, options)


class CapacityMatchingR2:
    policy_id = "B3_CAPACITY_MATCHING"

    def choose(self, history: VisibleHistory, actions: Iterable[ActionR2]) -> ActionR2:
        options = tuple(actions)
        confirms = [a for a in options if a.kind == "CONFIRM"]
        if len(confirms) >= 2:
            return ShieldedPi0R2().choose(history, options)
        scans = [a for a in options if a.kind == "SCAN"]
        return sorted(scans, key=lambda a: a.region_id or "")[0] if scans else ShieldedPi0R2().choose(history, options)


class RatioPSVRR2:
    policy_id = "B4_RATIO_PSVR"

    def choose(self, history: VisibleHistory, actions: Iterable[ActionR2]) -> ActionR2:
        options = tuple(actions)
        confirms = [a for a in options if a.kind == "CONFIRM"]
        visible = {candidate.witness_id: candidate.score_bin for observation in history.observations for candidate in observation.emitted}
        return max(confirms, key=lambda a: (visible.get(a.witness_id or "", -1), a.witness_id or "")) if confirms else ShieldedPi0R2().choose(history, options)


def replay(world: World, history: VisibleHistory) -> R2Environment | None:
    env = R2Environment(world)
    for action, expected in zip(history.actions, history.observations):
        try:
            observed = env.execute(action)
        except (ValueError, AssertionError):
            return None
        if observed != expected:
            return None
    return env


def independent_likelihood(world: World, history: VisibleHistory) -> int:
    """Second, deliberately separate brute-force observation-kernel oracle."""
    elapsed, mode, stopped = 0, "INITIAL", False
    scanned: set[str] = set()
    frontier: dict[str, Candidate] = {}
    committed: set[str] = set()
    closed: set[str] = set()
    regions = {region.region_id: region for region in world.regions}
    for action, expected in zip(history.actions, history.observations):
        next_region = next((region.region_id for region in world.regions if region.region_id not in scanned), None)
        legal_confirms = {candidate.witness_id: candidate for candidate in frontier.values()} if not stopped and CONFIRM_SUPPORT_TICKS <= HORIZON_TICKS - elapsed else {}
        legal_scan = next_region is not None and SCAN_SUPPORT_TICKS + CONFIRM_SUPPORT_TICKS <= HORIZON_TICKS - elapsed and not stopped
        if action.kind == "STOP":
            observed = Observation("STOP", 0, None, None, None, (), "STOPPED", None)
            stopped = True
        elif action.kind == "SCAN" and legal_scan and action.region_id == next_region:
            region = regions[action.region_id]
            elapsed += region.scan_ticks
            mode = "SCAN"
            scanned.add(region.region_id)
            for candidate in region.candidates:
                frontier[candidate.witness_id] = candidate
            observed = Observation("SCAN", region.scan_ticks, region.region_id, None, None, region.candidates, "SCANNED", None)
        elif action.kind == "CONFIRM" and action.witness_id in legal_confirms:
            candidate = legal_confirms[action.witness_id]
            if candidate.hypothesis_id != action.hypothesis_id:
                return 0
            located = next(((region, i) for region in world.regions for i, item in enumerate(region.candidates) if item.witness_id == candidate.witness_id), None)
            if located is None:
                return 0
            region, i = located
            elapsed += region.confirm_ticks[i]
            mode = "CONFIRM"
            closed.add(candidate.hypothesis_id)
            for witness_id, item in list(frontier.items()):
                if item.hypothesis_id == candidate.hypothesis_id:
                    del frontier[witness_id]
            token = region.event_tokens[i] if region.positive[i] else None
            outcome = "ORACLE_NEGATIVE" if token is None else "DUPLICATE" if token in committed else "NEW_COMMIT"
            if outcome == "NEW_COMMIT":
                committed.add(token)
            observed = Observation("CONFIRM", region.confirm_ticks[i], None, candidate.witness_id, candidate.hypothesis_id, (), outcome, token if outcome == "NEW_COMMIT" else None)
        else:
            return 0
        if observed != expected or elapsed > HORIZON_TICKS:
            return 0
    return 1


class ExactPosterior:
    def __init__(self, worlds: Iterable[World]):
        self.worlds = tuple(worlds)
        if not self.worlds:
            raise ValueError("finite world library must be nonempty")

    def weights(self, history: VisibleHistory) -> dict[str, float]:
        consistent = [world for world in self.worlds if replay(world, history) is not None]
        if not consistent:
            raise ValueError("visible history has zero prior probability")
        mass = 1.0 / len(consistent)
        return {world.world_id: (mass if world in consistent else 0.0) for world in self.worlds}

    def incremental_weights(self, history: VisibleHistory, action: ActionR2, observation: Observation) -> dict[str, float]:
        prior = self.weights(history)
        successor = history.append(action, observation)
        raw = {world.world_id: prior[world.world_id] * independent_likelihood(world, successor) for world in self.worlds}
        normalizer = sum(raw.values())
        if normalizer == 0:
            raise ValueError("zero-mass Bayes update")
        return {key: value / normalizer for key, value in raw.items()}

    def supported(self, history: VisibleHistory) -> tuple[World, ...]:
        weights = self.weights(history)
        return tuple(w for w in self.worlds if weights[w.world_id] > 0.0)

    def verify(self, history: VisibleHistory) -> dict[str, object]:
        weights = self.weights(history)
        support = self.supported(history)
        return {
            "mass": sum(weights.values()),
            "supported_worlds": len(support),
            "all_supported_reproduce_history": all(independent_likelihood(w, history) == 1 for w in support),
            "inconsistent_mass_zero": all(weights[w.world_id] == 0.0 for w in self.worlds if w not in support),
            "independent_kernel_agrees_with_replay": all((independent_likelihood(w, history) == 1) == (replay(w, history) is not None) for w in self.worlds),
        }


class ExactConditionalRollout:
    """Exact finite sum; it never receives the actual execution environment."""

    def __init__(self, posterior: ExactPosterior, continuation: ShieldedPi0R2 | None = None):
        self.posterior = posterior
        self.continuation = continuation or ShieldedPi0R2()
        self.last_diagnostics: dict[str, object] = {}

    def value(self, history: VisibleHistory, action: ActionR2) -> float:
        weights = self.posterior.weights(history)
        total = 0.0
        for world in self.posterior.worlds:
            weight = weights[world.world_id]
            if not weight:
                continue
            env = replay(world, history)
            assert env is not None
            env.execute(action)
            while not env.visible_state().stopped:
                env.execute(self.continuation.choose(env.history, env.safe_actions()))
            total += weight * env.utility()
        return total

    def choose(self, history: VisibleHistory, actions: Iterable[ActionR2]) -> ActionR2:
        candidates = tuple(actions)
        values = {a.identifier: self.value(history, a) for a in candidates}
        self.last_diagnostics = {"posterior_digest": history.digest, "full_horizon": True, "continuation": self.continuation.policy_id, "values": values}
        return max(candidates, key=lambda a: (values[a.identifier], a.identifier == ActionR2.stop().identifier, a.identifier))
