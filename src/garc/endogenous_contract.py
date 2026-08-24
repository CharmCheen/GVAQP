"""Reference-blind CPU contract for endogenous SCAN/VERIFY experiments.

This module qualifies infrastructure only.  It deliberately contains no video
model, reference labels, adaptive learner, or claim about natural headroom.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Mapping, Protocol, Sequence


class ContractError(ValueError):
    """The frozen action/information contract was violated."""


class InadmissibleAction(RuntimeError):
    """A policy requested an action outside its causal frontier."""


@dataclass(frozen=True)
class Region:
    region_id: str
    start_s: float
    end_s: float

    def __post_init__(self) -> None:
        if not self.region_id or not math.isfinite(self.start_s) or not math.isfinite(self.end_s):
            raise ContractError("region requires a non-empty ID and finite bounds")
        if self.end_s <= self.start_s:
            raise ContractError("region must have positive duration")


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    region_id: str
    start_s: float
    end_s: float
    proxy_score: float
    participant_keys: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.region_id:
            raise ContractError("candidate and region IDs must be non-empty")
        if self.end_s <= self.start_s or not math.isfinite(self.proxy_score):
            raise ContractError("candidate bounds and score must be valid")


@dataclass(frozen=True)
class LocalRelation:
    relation_id: str
    start_s: float
    end_s: float
    participant_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.relation_id or self.end_s <= self.start_s:
            raise ContractError("relation requires an ID and positive duration")
        if not self.participant_keys:
            raise ContractError("relation needs locally observed participant keys")


@dataclass(frozen=True)
class VerificationResult:
    relations: tuple[LocalRelation, ...] = ()
    status: str = "OK"


@dataclass(frozen=True)
class CommittedEvent:
    event_id: str
    start_s: float
    end_s: float
    participant_keys: tuple[str, ...]
    relation_ids: tuple[str, ...]
    first_commit_s: float


@dataclass(frozen=True)
class Action:
    kind: str
    target_id: str | None = None

    @classmethod
    def scan(cls, region_id: str) -> "Action":
        return cls("SCAN", region_id)

    @classmethod
    def verify(cls, candidate_id: str) -> "Action":
        return cls("VERIFY", candidate_id)

    @classmethod
    def direct_verify(cls, region_id: str) -> "Action":
        return cls("DIRECT_VERIFY", region_id)

    @classmethod
    def stop(cls) -> "Action":
        return cls("STOP")


@dataclass(frozen=True)
class PublicState:
    query_id: str
    elapsed_s: float
    deadline_s: float
    regions: tuple[Region, ...]
    scanned_region_ids: tuple[str, ...]
    direct_verified_region_ids: tuple[str, ...]
    exposed_candidates: tuple[Candidate, ...]
    verified_candidate_ids: tuple[str, ...]
    committed_events: tuple[CommittedEvent, ...]


@dataclass(frozen=True)
class TraceEntry:
    step: int
    action: str
    target_id: str | None
    start_s: float
    end_s: float
    cost_s: float
    status: str
    exposed_candidate_ids: tuple[str, ...] = ()
    returned_relation_ids: tuple[str, ...] = ()
    committed_event_count: int = 0


@dataclass(frozen=True)
class RunResult:
    policy_name: str
    query_id: str
    deadline_s: float
    elapsed_s: float
    trace: tuple[TraceEntry, ...]
    committed_events: tuple[CommittedEvent, ...]
    normalized_anytime_event_auc: float
    terminal_event_recall: float


class CandidateGenerator(Protocol):
    def scan(self, query_id: str, region: Region) -> tuple[Candidate, ...]: ...


class Verifier(Protocol):
    def verify_candidate(self, query_id: str, candidate: Candidate) -> VerificationResult: ...
    def direct_verify(self, query_id: str, region: Region) -> VerificationResult: ...


class Policy(Protocol):
    name: str
    def choose_action(self, state: PublicState) -> Action: ...


@dataclass(frozen=True)
class ConstantCosts:
    scan_s: float
    candidate_verify_s: float
    direct_verify_s: float
    scan_overrides: Mapping[str, float] = field(default_factory=dict)
    candidate_overrides: Mapping[str, float] = field(default_factory=dict)
    direct_overrides: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        values = (self.scan_s, self.candidate_verify_s, self.direct_verify_s)
        if any(value < 0 or not math.isfinite(value) for value in values):
            raise ContractError("costs must be finite and non-negative")

    def scan_cost(self, region: Region) -> float:
        return float(self.scan_overrides.get(region.region_id, self.scan_s))

    def candidate_cost(self, candidate: Candidate) -> float:
        return float(self.candidate_overrides.get(candidate.candidate_id, self.candidate_verify_s))

    def direct_cost(self, region: Region) -> float:
        return float(self.direct_overrides.get(region.region_id, self.direct_verify_s))


@dataclass(frozen=True)
class MappingGenerator:
    outputs: Mapping[tuple[str, str], tuple[Candidate, ...]]

    def scan(self, query_id: str, region: Region) -> tuple[Candidate, ...]:
        return tuple(self.outputs.get((query_id, region.region_id), ()))


@dataclass(frozen=True)
class MappingVerifier:
    candidate_results: Mapping[tuple[str, str], VerificationResult] = field(default_factory=dict)
    direct_results: Mapping[tuple[str, str], VerificationResult] = field(default_factory=dict)

    def verify_candidate(self, query_id: str, candidate: Candidate) -> VerificationResult:
        return self.candidate_results.get((query_id, candidate.candidate_id), VerificationResult())

    def direct_verify(self, query_id: str, region: Region) -> VerificationResult:
        return self.direct_results.get((query_id, region.region_id), VerificationResult())


class ScriptedPolicy:
    def __init__(self, actions: Sequence[Action], name: str = "scripted") -> None:
        self.name = name
        self._actions = tuple(actions)
        self._index = 0

    def choose_action(self, state: PublicState) -> Action:
        del state
        if self._index >= len(self._actions):
            return Action.stop()
        action = self._actions[self._index]
        self._index += 1
        return action


class DirectVerifyUniformPolicy:
    name = "direct_verify_uniform"

    def choose_action(self, state: PublicState) -> Action:
        done = set(state.direct_verified_region_ids)
        for region in state.regions:
            if region.region_id not in done:
                return Action.direct_verify(region.region_id)
        return Action.stop()


class ScanThenProxyGreedyPolicy:
    """Simple legal baseline: expose every region, then verify exposed scores."""

    name = "scan_then_proxy_greedy"

    def choose_action(self, state: PublicState) -> Action:
        scanned = set(state.scanned_region_ids)
        for region in state.regions:
            if region.region_id not in scanned:
                return Action.scan(region.region_id)
        verified = set(state.verified_candidate_ids)
        available = [item for item in state.exposed_candidates if item.candidate_id not in verified]
        if not available:
            return Action.stop()
        candidate = max(available, key=lambda item: (item.proxy_score, item.candidate_id))
        return Action.verify(candidate.candidate_id)


class EndogenousExecutor:
    """Owns causal exposure, the common clock, and common materialization."""

    def __init__(
        self,
        regions: Sequence[Region],
        generator: CandidateGenerator,
        verifier: Verifier,
        costs: ConstantCosts,
        deadline_s: float,
        reference_event_count: int,
        merge_gap_s: float = 10.0,
    ) -> None:
        self.regions = tuple(sorted(regions, key=lambda item: (item.start_s, item.region_id)))
        if len({item.region_id for item in self.regions}) != len(self.regions):
            raise ContractError("region IDs must be unique")
        if deadline_s <= 0 or reference_event_count < 0 or merge_gap_s < 0:
            raise ContractError("deadline, reference count, or merge gap is invalid")
        self._region_by_id = {item.region_id: item for item in self.regions}
        self.generator = generator
        self.verifier = verifier
        self.costs = costs
        self.deadline_s = float(deadline_s)
        self.reference_event_count = reference_event_count
        self.merge_gap_s = float(merge_gap_s)

    def run(self, query_id: str, policy: Policy) -> RunResult:
        if not query_id:
            raise ContractError("query ID is public and must be non-empty")
        elapsed = 0.0
        scanned: list[str] = []
        direct_done: list[str] = []
        exposed: dict[str, Candidate] = {}
        verified: list[str] = []
        relations: list[tuple[LocalRelation, float]] = []
        trace: list[TraceEntry] = []

        for step in range(100000):
            events = _materialize(relations, self.merge_gap_s)
            state = PublicState(
                query_id=query_id,
                elapsed_s=elapsed,
                deadline_s=self.deadline_s,
                regions=self.regions,
                scanned_region_ids=tuple(scanned),
                direct_verified_region_ids=tuple(direct_done),
                exposed_candidates=tuple(exposed.values()),
                verified_candidate_ids=tuple(verified),
                committed_events=events,
            )
            action = policy.choose_action(state)
            if action.kind == "STOP":
                break
            cost = self._cost_and_validate(action, scanned, direct_done, exposed, verified)
            if elapsed + cost > self.deadline_s + 1e-12:
                trace.append(TraceEntry(step, action.kind, action.target_id, elapsed, elapsed, cost, "REJECTED_DEADLINE", committed_event_count=len(events)))
                break

            start = elapsed
            elapsed += cost
            new_candidates: tuple[Candidate, ...] = ()
            result = VerificationResult()
            if action.kind == "SCAN":
                region = self._region_by_id[action.target_id or ""]
                new_candidates = tuple(self.generator.scan(query_id, region))
                self._validate_candidates(region, new_candidates, exposed)
                scanned.append(region.region_id)
                exposed.update((item.candidate_id, item) for item in new_candidates)
            elif action.kind == "VERIFY":
                candidate = exposed[action.target_id or ""]
                result = self.verifier.verify_candidate(query_id, candidate)
                self._validate_relations(result, candidate.start_s, candidate.end_s)
                verified.append(candidate.candidate_id)
                relations.extend((item, elapsed) for item in result.relations)
            elif action.kind == "DIRECT_VERIFY":
                region = self._region_by_id[action.target_id or ""]
                result = self.verifier.direct_verify(query_id, region)
                self._validate_relations(result, region.start_s, region.end_s)
                direct_done.append(region.region_id)
                relations.extend((item, elapsed) for item in result.relations)
            events = _materialize(relations, self.merge_gap_s)
            trace.append(TraceEntry(
                step, action.kind, action.target_id, start, elapsed, cost, "COMPLETED",
                tuple(item.candidate_id for item in new_candidates),
                tuple(item.relation_id for item in result.relations), len(events),
            ))
        else:
            raise ContractError("policy did not terminate")

        events = _materialize(relations, self.merge_gap_s)
        recall = min(1.0, len(events) / self.reference_event_count) if self.reference_event_count else 1.0
        auc = _anytime_auc(trace, self.deadline_s, self.reference_event_count)
        return RunResult(policy.name, query_id, self.deadline_s, elapsed, tuple(trace), events, auc, recall)

    def _cost_and_validate(self, action: Action, scanned: list[str], direct_done: list[str], exposed: Mapping[str, Candidate], verified: list[str]) -> float:
        target = action.target_id or ""
        if action.kind == "SCAN":
            if target not in self._region_by_id or target in scanned:
                raise InadmissibleAction("SCAN target is unknown or already scanned")
            return self.costs.scan_cost(self._region_by_id[target])
        if action.kind == "VERIFY":
            if target not in exposed or target in verified:
                raise InadmissibleAction("candidate VERIFY requires a newly exposed candidate")
            return self.costs.candidate_cost(exposed[target])
        if action.kind == "DIRECT_VERIFY":
            if target not in self._region_by_id or target in direct_done:
                raise InadmissibleAction("DirectVerify target is unknown or already verified")
            return self.costs.direct_cost(self._region_by_id[target])
        raise InadmissibleAction(f"unknown action kind: {action.kind}")

    @staticmethod
    def _validate_candidates(region: Region, candidates: tuple[Candidate, ...], exposed: Mapping[str, Candidate]) -> None:
        ids: set[str] = set()
        for item in candidates:
            if item.region_id != region.region_id or item.start_s < region.start_s or item.end_s > region.end_s:
                raise ContractError("generated candidate lies outside its scanned region")
            if item.candidate_id in ids or item.candidate_id in exposed:
                raise ContractError("candidate IDs must be globally unique")
            ids.add(item.candidate_id)

    @staticmethod
    def _validate_relations(result: VerificationResult, start_s: float, end_s: float) -> None:
        if result.status not in {"OK", "FAILURE"}:
            raise ContractError("unknown verifier status")
        if result.status == "FAILURE" and result.relations:
            raise ContractError("failed verification cannot return relations")
        for item in result.relations:
            if item.start_s < start_s or item.end_s > end_s:
                raise ContractError("relation lies outside the verified interval")


def _materialize(relations: Sequence[tuple[LocalRelation, float]], gap_s: float) -> tuple[CommittedEvent, ...]:
    groups: list[dict[str, object]] = []
    ordered = sorted(relations, key=lambda item: (item[0].start_s, item[0].relation_id))
    for relation, commit_s in ordered:
        participants = tuple(sorted(relation.participant_keys))
        match = next((group for group in groups if group["participants"] == participants and relation.start_s - float(group["end_s"]) <= gap_s), None)
        if match is None:
            groups.append({"participants": participants, "start_s": relation.start_s, "end_s": relation.end_s, "relations": [relation.relation_id], "first_commit_s": commit_s})
        else:
            match["end_s"] = max(float(match["end_s"]), relation.end_s)
            cast_relations = match["relations"]
            assert isinstance(cast_relations, list)
            cast_relations.append(relation.relation_id)
            match["first_commit_s"] = min(float(match["first_commit_s"]), commit_s)
    return tuple(CommittedEvent(
        event_id=f"event:{index}", start_s=float(group["start_s"]), end_s=float(group["end_s"]),
        participant_keys=tuple(group["participants"]), relation_ids=tuple(group["relations"]),
        first_commit_s=float(group["first_commit_s"]),
    ) for index, group in enumerate(groups))


def _anytime_auc(trace: Sequence[TraceEntry], deadline_s: float, reference_count: int) -> float:
    if reference_count == 0:
        return 1.0
    area = 0.0
    last_t = 0.0
    last_recall = 0.0
    for entry in trace:
        if entry.status != "COMPLETED":
            continue
        area += (entry.end_s - last_t) * last_recall
        last_t = entry.end_s
        last_recall = min(1.0, entry.committed_event_count / reference_count)
    area += (deadline_s - last_t) * last_recall
    return area / deadline_s


def assert_exact_parity(left: RunResult, right: RunResult) -> None:
    """Assert common-clock/evaluator equality for identical evidence traces."""
    fields = (
        "deadline_s", "elapsed_s", "trace", "committed_events",
        "normalized_anytime_event_auc", "terminal_event_recall",
    )
    mismatches = [name for name in fields if getattr(left, name) != getattr(right, name)]
    if mismatches:
        raise AssertionError(f"replay parity failed: {', '.join(mismatches)}")
