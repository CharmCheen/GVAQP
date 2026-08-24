"""Shared causal execution contract for CPU-only video-query replay.

The engine owns exposure, cost accounting, verification, materialization,
deadline enforcement, and utility. Policies only choose admissible actions.
This prevents policy-specific evaluators from silently changing the experiment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import random
from typing import Mapping, Protocol, Sequence


EPS = 1e-9


class ContractError(ValueError):
    """Raised when an input violates the frozen replay contract."""


class InadmissibleAction(RuntimeError):
    """Raised when a policy requests information outside its causal frontier."""


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    cell_id: str
    start_s: float
    end_s: float
    score: float
    participant_track_ids: tuple[str, ...] = ()
    is_fallback: bool = False

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.cell_id:
            raise ContractError("candidate and cell IDs must be non-empty")
        if not math.isfinite(self.start_s) or not math.isfinite(self.end_s):
            raise ContractError("candidate timestamps must be finite")
        if self.end_s <= self.start_s:
            raise ContractError("candidate interval must have positive duration")
        if not math.isfinite(self.score):
            raise ContractError("candidate score must be finite")


@dataclass(frozen=True)
class ScanCell:
    cell_id: str
    start_s: float
    end_s: float
    candidates: tuple[Candidate, ...] = ()

    def __post_init__(self) -> None:
        if not self.cell_id:
            raise ContractError("cell ID must be non-empty")
        if self.end_s <= self.start_s:
            raise ContractError("scan cell must have positive duration")
        for candidate in self.candidates:
            if candidate.cell_id != self.cell_id:
                raise ContractError("candidate cell_id does not match parent cell")


@dataclass(frozen=True)
class EventRelation:
    relation_id: str
    start_s: float
    end_s: float
    participant_track_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.relation_id:
            raise ContractError("relation ID must be non-empty")
        if self.end_s <= self.start_s:
            raise ContractError("event relation must have positive duration")
        if not self.participant_track_ids:
            raise ContractError("event relation requires participant track IDs")


@dataclass(frozen=True)
class VerificationResult:
    candidate_id: str
    events: tuple[EventRelation, ...] = ()
    status: str = "OK"


@dataclass(frozen=True)
class DurableEvent:
    event_id: str
    start_s: float
    end_s: float
    participant_track_ids: tuple[str, ...]
    relation_ids: tuple[str, ...]
    first_commit_s: float


@dataclass(frozen=True)
class Action:
    kind: str
    target_id: str | None = None

    @classmethod
    def scan(cls, cell_id: str) -> "Action":
        return cls("SCAN", cell_id)

    @classmethod
    def verify(cls, candidate_id: str) -> "Action":
        return cls("VERIFY", candidate_id)

    @classmethod
    def stop(cls) -> "Action":
        return cls("STOP", None)


@dataclass(frozen=True)
class PolicyState:
    elapsed_s: float
    deadline_s: float
    previous_scan_cell_id: str | None
    scanned_cell_ids: tuple[str, ...]
    scanned_cells: tuple[ScanCell, ...]
    unscanned_cells: tuple[ScanCell, ...]
    available_candidates: tuple[Candidate, ...]
    exposed_candidates: tuple[Candidate, ...]
    verified_candidate_ids: tuple[str, ...]
    scan_costs: tuple[tuple[str, float], ...]
    verify_costs: tuple[tuple[str, float], ...]
    committed_events: tuple[DurableEvent, ...]


@dataclass(frozen=True)
class TraceEntry:
    step: int
    action: str
    target_id: str | None
    start_s: float
    end_s: float
    cost_s: float
    exposed_candidate_ids: tuple[str, ...] = ()
    returned_relation_ids: tuple[str, ...] = ()
    committed_event_count: int = 0
    status: str = "COMPLETED"
    oracle_status: str | None = None


@dataclass(frozen=True)
class ReplayResult:
    policy_name: str
    deadline_s: float
    elapsed_s: float
    trace: tuple[TraceEntry, ...]
    committed_events: tuple[DurableEvent, ...]
    verified_candidate_ids: tuple[str, ...]
    normalized_anytime_event_auc: float
    terminal_event_recall: float


class Policy(Protocol):
    name: str

    def choose_action(self, state: PolicyState) -> Action:
        ...


class CostModel(Protocol):
    def scan_cost(
        self, previous_cell_id: str | None, target_cell: ScanCell
    ) -> float:
        ...

    def verify_cost(self, candidate: Candidate) -> float:
        ...


class VerificationOracle(Protocol):
    def verify(self, candidate: Candidate) -> VerificationResult:
        ...


@dataclass(frozen=True)
class ConstantCostModel:
    scan_cost_s: float
    verify_cost_s: float
    transition_overrides: Mapping[tuple[str | None, str], float] = field(
        default_factory=dict
    )
    verify_overrides: Mapping[str, float] = field(default_factory=dict)

    def scan_cost(
        self, previous_cell_id: str | None, target_cell: ScanCell
    ) -> float:
        return float(
            self.transition_overrides.get(
                (previous_cell_id, target_cell.cell_id), self.scan_cost_s
            )
        )

    def verify_cost(self, candidate: Candidate) -> float:
        return float(self.verify_overrides.get(candidate.candidate_id, self.verify_cost_s))


@dataclass(frozen=True)
class MappingOracle:
    results: Mapping[str, tuple[EventRelation, ...]]
    failure_candidate_ids: frozenset[str] = frozenset()

    def verify(self, candidate: Candidate) -> VerificationResult:
        status = "FAILURE" if candidate.candidate_id in self.failure_candidate_ids else "OK"
        return VerificationResult(
            candidate.candidate_id,
            self.results.get(candidate.candidate_id, ()),
            status,
        )


class ScriptedPolicy:
    """Deterministic policy used for parity audits and frozen replays."""

    def __init__(self, actions: Sequence[Action], name: str = "scripted") -> None:
        self.name = name
        self._actions = tuple(actions)
        self._position = 0

    def choose_action(self, state: PolicyState) -> Action:
        del state
        if self._position >= len(self._actions):
            return Action.stop()
        action = self._actions[self._position]
        self._position += 1
        return action


class SequentialPolicy:
    name = "sequential"

    def choose_action(self, state: PolicyState) -> Action:
        if state.available_candidates:
            candidate = _best_candidate(state.available_candidates)
            if not candidate.is_fallback or not state.unscanned_cells:
                return Action.verify(candidate.candidate_id)
        if state.unscanned_cells:
            cell = min(state.unscanned_cells, key=lambda item: (item.start_s, item.cell_id))
            return Action.scan(cell.cell_id)
        return Action.stop()


class UniformStridePolicy:
    name = "uniform_stride"

    def __init__(self, stride: int = 2) -> None:
        if stride < 1:
            raise ContractError("stride must be positive")
        self.stride = stride

    def choose_action(self, state: PolicyState) -> Action:
        if state.available_candidates:
            candidate = _best_candidate(state.available_candidates)
            if not candidate.is_fallback or not state.unscanned_cells:
                return Action.verify(candidate.candidate_id)
        if not state.unscanned_cells:
            return Action.stop()
        ordered = sorted(state.unscanned_cells, key=lambda item: (item.start_s, item.cell_id))
        scanned = set(state.scanned_cell_ids)
        all_cells = sorted(
            (*state.scanned_cells, *state.unscanned_cells),
            key=lambda item: (item.start_s, item.cell_id),
        )
        preferred = [cell for index, cell in enumerate(all_cells) if index % self.stride == 0]
        target = next((cell for cell in preferred if cell.cell_id not in scanned), ordered[0])
        return Action.scan(target.cell_id)


class RandomTemporalPolicy:
    name = "random_temporal"

    def __init__(self, seed: int) -> None:
        self._rng = random.Random(seed)

    def choose_action(self, state: PolicyState) -> Action:
        if state.available_candidates:
            candidate = _best_candidate(state.available_candidates)
            if not candidate.is_fallback or not state.unscanned_cells:
                return Action.verify(candidate.candidate_id)
        if state.unscanned_cells:
            return Action.scan(self._rng.choice(state.unscanned_cells).cell_id)
        return Action.stop()


class LargestGapPolicy:
    name = "largest_gap"

    def choose_action(self, state: PolicyState) -> Action:
        if state.available_candidates:
            candidate = _best_candidate(state.available_candidates)
            if not candidate.is_fallback or not state.unscanned_cells:
                return Action.verify(candidate.candidate_id)
        return _largest_gap_scan_action(state)


def _largest_gap_scan_action(state: PolicyState) -> Action:
    """Choose temporal exposure without allowing a low-score candidate to preempt it."""

    if not state.unscanned_cells:
        return Action.stop()
    if not state.scanned_cell_ids:
        target = min(state.unscanned_cells, key=lambda item: (item.start_s, item.cell_id))
        return Action.scan(target.cell_id)
    all_cells = sorted(
        (*state.scanned_cells, *state.unscanned_cells),
        key=lambda item: (item.start_s, item.cell_id),
    )
    positions = {cell.cell_id: (cell.start_s + cell.end_s) / 2 for cell in all_cells}
    known_positions = [positions[cell.cell_id] for cell in state.scanned_cells]
    target = max(
        state.unscanned_cells,
        key=lambda cell: (
            min(abs(positions[cell.cell_id] - value) for value in known_positions),
            -cell.start_s,
        ),
    )
    return Action.scan(target.cell_id)


class DatbSVPolicy:
    """Deterministic deadline-aware temporal benefit-rate planner.

    The policy compares two causally available value rates. VERIFY value is the
    proxy score discounted for already committed participant tuples and divided
    by its measured cost. SCAN value is a beta-smoothed observed candidate rate
    times temporal dispersion gain, divided by transition-specific scan cost.
    """

    name = "datb_sv"

    def __init__(self, verify_score_threshold: float = 0.5) -> None:
        self.verify_score_threshold = float(verify_score_threshold)

    def choose_action(self, state: PolicyState) -> Action:
        remaining = state.deadline_s - state.elapsed_s
        scan_costs = dict(state.scan_costs)
        verify_costs = dict(state.verify_costs)
        affordable_scans = [
            cell
            for cell in state.unscanned_cells
            if scan_costs[cell.cell_id] <= remaining + EPS
        ]
        affordable_candidates = [
            candidate
            for candidate in state.available_candidates
            if verify_costs[candidate.candidate_id] <= remaining + EPS
        ]

        best_scan: ScanCell | None = None
        scan_rate = -math.inf
        if affordable_scans:
            positive_cells = len(
                {
                    candidate.cell_id
                    for candidate in state.exposed_candidates
                    if not candidate.is_fallback
                }
            )
            observed_cells = len(state.scanned_cells)
            smoothed_hit_rate = (positive_cells + 1.0) / (observed_cells + 2.0)
            for cell in affordable_scans:
                value = (
                    smoothed_hit_rate
                    * _temporal_dispersion_gain(state, cell)
                    / scan_costs[cell.cell_id]
                )
                if value > scan_rate + EPS or (
                    math.isclose(value, scan_rate, abs_tol=EPS)
                    and best_scan is not None
                    and (cell.start_s, cell.cell_id) < (best_scan.start_s, best_scan.cell_id)
                ):
                    best_scan = cell
                    scan_rate = value

        best_verify: Candidate | None = None
        verify_rate = -math.inf
        committed_participants = {
            event.participant_track_ids for event in state.committed_events
        }
        for candidate in affordable_candidates:
            if candidate.is_fallback and affordable_scans:
                continue
            if not candidate.is_fallback and candidate.score < self.verify_score_threshold:
                continue
            participants = tuple(sorted(candidate.participant_track_ids))
            novelty = 0.25 if participants and participants in committed_participants else 1.0
            proxy_value = 0.0 if candidate.is_fallback else candidate.score
            value = proxy_value * novelty / verify_costs[candidate.candidate_id]
            if value > verify_rate + EPS or (
                math.isclose(value, verify_rate, abs_tol=EPS)
                and best_verify is not None
                and candidate.candidate_id < best_verify.candidate_id
            ):
                best_verify = candidate
                verify_rate = value

        if best_verify is not None and (best_scan is None or verify_rate >= scan_rate - EPS):
            return Action.verify(best_verify.candidate_id)
        if best_scan is not None:
            return Action.scan(best_scan.cell_id)
        if affordable_candidates:
            return Action.verify(_best_candidate(affordable_candidates).candidate_id)
        return Action.stop()


class ExSampleEndToEndPolicy:
    """Event-query adaptation of ExSample's Gamma Thompson chunk sampler.

    Original ExSample applies the expensive detector directly to a sampled frame.
    This adapter preserves its chunk posterior and random+ intent while routing
    every sampled temporal cell through the shared SCAN then VERIFY operators.
    """

    name = "exsample_end_to_end_adapted"

    def __init__(
        self,
        seed: int,
        *,
        chunk_count: int = 6,
        alpha0: float = 0.1,
        beta0: float = 1.0,
    ) -> None:
        if chunk_count < 1 or alpha0 <= 0 or beta0 <= 0:
            raise ContractError("ExSample parameters must be positive")
        self._rng = random.Random(seed)
        self.chunk_count = chunk_count
        self.alpha0 = float(alpha0)
        self.beta0 = float(beta0)
        self._cell_to_chunk: dict[str, int] = {}
        self._chunk_members: dict[int, tuple[str, ...]] = {}
        self._positions: dict[str, float] = {}
        self._sampled_by_chunk: dict[int, list[str]] = {}
        self._n: dict[int, int] = {}
        self._new_events: dict[int, int] = {}
        self._pending_cell_id: str | None = None
        self._pending_candidate_id: str | None = None
        self._event_count_before_verify = 0

    def choose_action(self, state: PolicyState) -> Action:
        if not self._cell_to_chunk:
            self._initialize_chunks(state)

        if self._pending_candidate_id is not None:
            if self._pending_candidate_id not in set(state.verified_candidate_ids):
                costs = dict(state.verify_costs)
                if (
                    self._pending_candidate_id in costs
                    and costs[self._pending_candidate_id]
                    <= state.deadline_s - state.elapsed_s + EPS
                ):
                    return Action.verify(self._pending_candidate_id)
                return Action.stop()
            assert self._pending_cell_id is not None
            chunk = self._cell_to_chunk[self._pending_cell_id]
            gain = max(0, len(state.committed_events) - self._event_count_before_verify)
            self._new_events[chunk] += gain
            self._n[chunk] += 1
            self._sampled_by_chunk[chunk].append(self._pending_cell_id)
            self._pending_cell_id = None
            self._pending_candidate_id = None

        if self._pending_cell_id is not None:
            candidates = [
                candidate
                for candidate in state.available_candidates
                if candidate.cell_id == self._pending_cell_id
            ]
            if not candidates:
                return Action.stop()
            candidate = _best_candidate(candidates)
            self._pending_candidate_id = candidate.candidate_id
            self._event_count_before_verify = len(state.committed_events)
            return Action.verify(candidate.candidate_id)

        scan_costs = dict(state.scan_costs)
        affordable = {
            cell.cell_id: cell
            for cell in state.unscanned_cells
            if scan_costs[cell.cell_id] <= state.deadline_s - state.elapsed_s + EPS
        }
        if not affordable:
            return Action.stop()
        active_chunks = {
            self._cell_to_chunk[cell_id] for cell_id in affordable
        }
        sampled_rates = {
            chunk: self._rng.gammavariate(
                self._new_events[chunk] + self.alpha0,
                1.0 / (self._n[chunk] + self.beta0),
            )
            for chunk in active_chunks
        }
        best_rate = max(sampled_rates.values())
        best_chunks = sorted(
            chunk
            for chunk, value in sampled_rates.items()
            if math.isclose(value, best_rate, rel_tol=0.0, abs_tol=EPS)
        )
        chunk = self._rng.choice(best_chunks)
        members = [
            affordable[cell_id]
            for cell_id in self._chunk_members[chunk]
            if cell_id in affordable
        ]
        sampled_positions = [
            self._positions[cell_id] for cell_id in self._sampled_by_chunk[chunk]
        ]
        if sampled_positions:
            distance = {
                cell.cell_id: min(
                    abs(self._positions[cell.cell_id] - value)
                    for value in sampled_positions
                )
                for cell in members
            }
            maximum = max(distance.values())
            choices = sorted(
                [
                    cell
                    for cell in members
                    if math.isclose(distance[cell.cell_id], maximum, abs_tol=EPS)
                ],
                key=lambda item: (item.start_s, item.cell_id),
            )
        else:
            choices = sorted(members, key=lambda item: (item.start_s, item.cell_id))
        target = self._rng.choice(choices)
        self._pending_cell_id = target.cell_id
        return Action.scan(target.cell_id)

    def _initialize_chunks(self, state: PolicyState) -> None:
        cells = sorted(
            (*state.scanned_cells, *state.unscanned_cells),
            key=lambda item: (item.start_s, item.cell_id),
        )
        actual_chunks = min(self.chunk_count, len(cells))
        members: dict[int, list[str]] = {chunk: [] for chunk in range(actual_chunks)}
        for index, cell in enumerate(cells):
            chunk = min(actual_chunks - 1, index * actual_chunks // len(cells))
            self._cell_to_chunk[cell.cell_id] = chunk
            self._positions[cell.cell_id] = (cell.start_s + cell.end_s) / 2.0
            members[chunk].append(cell.cell_id)
        self._chunk_members = {chunk: tuple(ids) for chunk, ids in members.items()}
        self._sampled_by_chunk = {chunk: [] for chunk in members}
        self._n = {chunk: 0 for chunk in members}
        self._new_events = {chunk: 0 for chunk in members}


def _best_candidate(candidates: Sequence[Candidate]) -> Candidate:
    return max(
        candidates,
        key=lambda item: (not item.is_fallback, item.score, -item.start_s, item.candidate_id),
    )


def _temporal_dispersion_gain(state: PolicyState, target: ScanCell) -> float:
    all_cells = (*state.scanned_cells, *state.unscanned_cells)
    left = min(cell.start_s for cell in all_cells)
    right = max(cell.end_s for cell in all_cells)
    span = max(right - left, EPS)
    target_position = (target.start_s + target.end_s) / 2.0
    anchors = [left, right]
    anchors.extend((cell.start_s + cell.end_s) / 2.0 for cell in state.scanned_cells)
    return min(abs(target_position - anchor) for anchor in anchors) / span


def _temporal_gap(
    left_start: float, left_end: float, right_start: float, right_end: float
) -> float:
    if left_end >= right_start and right_end >= left_start:
        return 0.0
    return max(right_start - left_end, left_start - right_end)


class CausalFrontierReplay:
    """Policy-neutral executor for one video-query workload."""

    def __init__(
        self,
        cells: Sequence[ScanCell],
        oracle: VerificationOracle,
        cost_model: CostModel,
        deadline_s: float,
        reference_event_count: int,
        *,
        verify_window_s: float = 10.0,
        merge_gap_s: float = 10.0,
        fallback_score: float = -1e12,
    ) -> None:
        if deadline_s <= 0 or not math.isfinite(deadline_s):
            raise ContractError("deadline must be finite and positive")
        if reference_event_count <= 0:
            raise ContractError("reference_event_count must be positive")
        if verify_window_s <= 0 or merge_gap_s < 0:
            raise ContractError("window and merge gap must be valid")
        self._cells = tuple(sorted(cells, key=lambda item: (item.start_s, item.cell_id)))
        if len({cell.cell_id for cell in self._cells}) != len(self._cells):
            raise ContractError("cell IDs must be unique")
        candidate_ids: set[str] = set()
        for cell in self._cells:
            if not math.isclose(cell.end_s - cell.start_s, verify_window_s, abs_tol=EPS):
                raise ContractError("primary replay requires fixed VERIFY windows")
            for candidate in cell.candidates:
                if not math.isclose(
                    candidate.end_s - candidate.start_s, verify_window_s, abs_tol=EPS
                ):
                    raise ContractError("candidate does not use the frozen VERIFY window")
                if candidate.candidate_id in candidate_ids:
                    raise ContractError("candidate IDs must be globally unique")
                candidate_ids.add(candidate.candidate_id)
        self._oracle = oracle
        self._cost_model = cost_model
        self.deadline_s = float(deadline_s)
        self.reference_event_count = int(reference_event_count)
        self.verify_window_s = float(verify_window_s)
        self.merge_gap_s = float(merge_gap_s)
        self.fallback_score = float(fallback_score)

    def run(self, policy: Policy, *, max_steps: int = 100000) -> ReplayResult:
        elapsed = 0.0
        previous_scan: str | None = None
        scanned: dict[str, ScanCell] = {}
        exposed: dict[str, Candidate] = {}
        verified: list[str] = []
        committed: list[DurableEvent] = []
        trace: list[TraceEntry] = []
        utility_points: list[tuple[float, int]] = [(0.0, 0)]
        cell_by_id = {cell.cell_id: cell for cell in self._cells}

        for step in range(max_steps):
            available = tuple(
                candidate
                for candidate_id, candidate in sorted(exposed.items())
                if candidate_id not in set(verified)
            )
            unscanned = tuple(
                cell for cell in self._cells if cell.cell_id not in scanned
            )
            scan_costs = tuple(
                (
                    cell.cell_id,
                    float(self._cost_model.scan_cost(previous_scan, cell)),
                )
                for cell in unscanned
            )
            verify_costs = tuple(
                (
                    candidate.candidate_id,
                    float(self._cost_model.verify_cost(candidate)),
                )
                for candidate in available
            )
            state = PolicyState(
                elapsed_s=elapsed,
                deadline_s=self.deadline_s,
                previous_scan_cell_id=previous_scan,
                scanned_cell_ids=tuple(scanned),
                scanned_cells=tuple(scanned.values()),
                unscanned_cells=unscanned,
                available_candidates=available,
                exposed_candidates=tuple(exposed.values()),
                verified_candidate_ids=tuple(verified),
                scan_costs=scan_costs,
                verify_costs=verify_costs,
                committed_events=tuple(committed),
            )
            action = policy.choose_action(state)
            if action.kind == "STOP":
                break
            if action.kind == "SCAN":
                if action.target_id not in cell_by_id or action.target_id in scanned:
                    raise InadmissibleAction("SCAN target is missing or already exposed")
                target = cell_by_id[action.target_id]
                cost = float(self._cost_model.scan_cost(previous_scan, target))
            elif action.kind == "VERIFY":
                if action.target_id not in exposed or action.target_id in verified:
                    raise InadmissibleAction("VERIFY target is outside the causal frontier")
                target = exposed[action.target_id]
                cost = float(self._cost_model.verify_cost(target))
            else:
                raise InadmissibleAction(f"unknown action kind: {action.kind}")
            if not math.isfinite(cost) or cost <= 0:
                raise ContractError("every action must have finite positive cost")
            if elapsed + cost > self.deadline_s + EPS:
                trace.append(
                    TraceEntry(
                        step=step,
                        action=action.kind,
                        target_id=action.target_id,
                        start_s=elapsed,
                        end_s=elapsed,
                        cost_s=cost,
                        committed_event_count=len(committed),
                        status="REJECTED_DEADLINE",
                    )
                )
                break

            start = elapsed
            elapsed += cost
            exposed_ids: tuple[str, ...] = ()
            relation_ids: tuple[str, ...] = ()
            oracle_status: str | None = None
            if action.kind == "SCAN":
                assert isinstance(target, ScanCell)
                scanned[target.cell_id] = target
                previous_scan = target.cell_id
                new_candidates = list(target.candidates)
                fallback = Candidate(
                    candidate_id=f"fallback:{target.cell_id}",
                    cell_id=target.cell_id,
                    start_s=target.start_s,
                    end_s=target.end_s,
                    score=self.fallback_score,
                    is_fallback=True,
                )
                if fallback.candidate_id in exposed:
                    raise ContractError("generated fallback candidate ID collision")
                new_candidates.append(fallback)
                for candidate in new_candidates:
                    if candidate.candidate_id in exposed:
                        raise ContractError("candidate exposed by multiple cells")
                    exposed[candidate.candidate_id] = candidate
                exposed_ids = tuple(candidate.candidate_id for candidate in new_candidates)
            else:
                assert isinstance(target, Candidate)
                result = self._oracle.verify(target)
                if result.candidate_id != target.candidate_id:
                    raise ContractError("oracle returned a mismatched candidate ID")
                if result.status not in {"OK", "FAILURE"}:
                    raise ContractError("oracle returned an unknown status")
                if result.status == "FAILURE" and result.events:
                    raise ContractError("failed oracle result cannot contain events")
                verified.append(target.candidate_id)
                oracle_status = result.status
                relation_ids = tuple(event.relation_id for event in result.events)
                for event in result.events if result.status == "OK" else ():
                    if event.start_s < target.start_s - EPS or event.end_s > target.end_s + EPS:
                        raise ContractError("oracle event lies outside the verified window")
                    self._materialize(committed, event, elapsed)

            trace.append(
                TraceEntry(
                    step=step,
                    action=action.kind,
                    target_id=action.target_id,
                    start_s=start,
                    end_s=elapsed,
                    cost_s=cost,
                    exposed_candidate_ids=exposed_ids,
                    returned_relation_ids=relation_ids,
                    committed_event_count=len(committed),
                    oracle_status=oracle_status,
                )
            )
            utility_points.append((elapsed, len(committed)))
        else:
            raise RuntimeError("policy exceeded max_steps without stopping")

        auc = self._normalized_auc(utility_points)
        terminal = min(len(committed), self.reference_event_count) / self.reference_event_count
        return ReplayResult(
            policy_name=policy.name,
            deadline_s=self.deadline_s,
            elapsed_s=elapsed,
            trace=tuple(trace),
            committed_events=tuple(committed),
            verified_candidate_ids=tuple(verified),
            normalized_anytime_event_auc=auc,
            terminal_event_recall=terminal,
        )

    def _materialize(
        self, committed: list[DurableEvent], relation: EventRelation, commit_s: float
    ) -> None:
        participants = tuple(sorted(relation.participant_track_ids))
        matches = [
            (index, event)
            for index, event in enumerate(committed)
            if event.participant_track_ids == participants
            and _temporal_gap(event.start_s, event.end_s, relation.start_s, relation.end_s)
            <= self.merge_gap_s + EPS
        ]
        if not matches:
            committed.append(
                DurableEvent(
                    event_id=f"event:{len(committed):06d}",
                    start_s=relation.start_s,
                    end_s=relation.end_s,
                    participant_track_ids=participants,
                    relation_ids=(relation.relation_id,),
                    first_commit_s=commit_s,
                )
            )
            return
        index, event = min(
            matches,
            key=lambda item: (
                _temporal_gap(
                    item[1].start_s,
                    item[1].end_s,
                    relation.start_s,
                    relation.end_s,
                ),
                item[1].first_commit_s,
                item[1].event_id,
            ),
        )
        committed[index] = DurableEvent(
            event_id=event.event_id,
            start_s=min(event.start_s, relation.start_s),
            end_s=max(event.end_s, relation.end_s),
            participant_track_ids=participants,
            relation_ids=event.relation_ids + (relation.relation_id,),
            first_commit_s=event.first_commit_s,
        )

    def _normalized_auc(self, points: Sequence[tuple[float, int]]) -> float:
        area = 0.0
        previous_time = 0.0
        previous_utility = 0.0
        for timestamp, count in points[1:]:
            area += (timestamp - previous_time) * previous_utility
            previous_time = timestamp
            previous_utility = min(count, self.reference_event_count) / self.reference_event_count
        area += (self.deadline_s - previous_time) * previous_utility
        return area / self.deadline_s


def assert_replay_parity(left: ReplayResult, right: ReplayResult) -> None:
    """Require exact shared-evaluator parity for identical action traces."""

    comparable_left = (
        left.deadline_s,
        left.elapsed_s,
        left.trace,
        left.committed_events,
        left.verified_candidate_ids,
        left.normalized_anytime_event_auc,
        left.terminal_event_recall,
    )
    comparable_right = (
        right.deadline_s,
        right.elapsed_s,
        right.trace,
        right.committed_events,
        right.verified_candidate_ids,
        right.normalized_anytime_event_auc,
        right.terminal_event_recall,
    )
    if comparable_left != comparable_right:
        raise AssertionError("identical action traces did not produce identical replay results")
