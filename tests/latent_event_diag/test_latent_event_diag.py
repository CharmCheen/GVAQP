from __future__ import annotations

import inspect
from pathlib import Path

from garc_eval.latent_event_diag.experiment import run_episode
from garc_eval.latent_event_diag.materializers import K3AdapterMaterializer, M0SimpleRunMaterializer, MaterializerConfig
from garc_eval.latent_event_diag.models import (
    ActionType,
    ObservationOutcome,
    OracleObservation,
    PlannerAction,
    read_csv,
    read_json,
    write_csv,
    write_json,
)
from garc_eval.latent_event_diag.oracles import SyntheticOracleSimulator
from garc_eval.latent_event_diag.planners import (
    P0Uniform,
    P1TopPrior,
    P2ComponentFirst,
    P3CoreOnlyGreedy,
    P4RelationAwareHeuristic,
    P5NaiveHardGap,
)
from garc_eval.latent_event_diag.synthetic import Regime, SyntheticConfig, generate_timeline


def obs(action_id, action_type, targets, outcome):
    return OracleObservation(action_id, action_type, tuple(targets), outcome, 1.0, 1.0, 0.0, "TEST")


def test_reproducible_generator():
    config = SyntheticConfig(random_seed=991)
    assert generate_timeline(Regime.R6_MODEL_MISSPECIFICATION, config) == generate_timeline(
        Regime.R6_MODEL_MISSPECIFICATION, config
    )


def test_adjacent_distinct_events():
    timeline = generate_timeline(Regime.R2_ADJACENT_DISTINCT, SyntheticConfig(random_seed=3))
    left, right = timeline.ground_truth_events[:2]
    assert left.end_time == right.start_time
    assert left.event_id != right.event_id
    assert any(len(event_ids) > 1 for event_ids in timeline.latent_unit_event_ids.values())


def test_unit_multiplicity_recorded():
    multi = generate_timeline(Regime.R2_ADJACENT_DISTINCT, SyntheticConfig(random_seed=3, unit_multiplicity=2))
    single = generate_timeline(Regime.R2_ADJACENT_DISTINCT, SyntheticConfig(random_seed=3, unit_multiplicity=1))
    assert max(map(len, multi.latent_unit_event_ids.values())) == 2
    assert max(map(len, single.latent_unit_event_ids.values())) == 1


def test_internal_negative_not_hard_separator():
    timeline = generate_timeline(Regime.R3_INTERNAL_WEAK_GAP, SyntheticConfig(random_seed=2))
    observations = [
        obs("p1", ActionType.PROBE_CORE, ["u0014"], ObservationOutcome.POSITIVE),
        obs("n1", ActionType.PROBE_CORE, ["u0018"], ObservationOutcome.NEGATIVE),
        obs("p2", ActionType.PROBE_CORE, ["u0022"], ObservationOutcome.POSITIVE),
    ]
    events = M0SimpleRunMaterializer().materialize(timeline.units, observations, MaterializerConfig())
    assert len(events) == 1
    assert set(events[0].anchor_ids) == {"u0014", "u0022"}


def test_relation_distinct_changes_partition():
    timeline = generate_timeline(Regime.R2_ADJACENT_DISTINCT, SyntheticConfig(random_seed=0))
    materializer = M0SimpleRunMaterializer()
    observations = [
        obs("p1", ActionType.PROBE_CORE, ["u0012"], ObservationOutcome.POSITIVE),
        obs("p2", ActionType.PROBE_CORE, ["u0021"], ObservationOutcome.POSITIVE),
    ]
    assert len(materializer.materialize(timeline.units, observations, MaterializerConfig())) == 1
    observations.append(obs("r1", ActionType.PROBE_RELATION, ["u0012", "u0021"], ObservationOutcome.DISTINCT))
    assert len(materializer.materialize(timeline.units, observations, MaterializerConfig())) == 2


def test_relation_same_prevents_oversplit():
    timeline = generate_timeline(Regime.R3_INTERNAL_WEAK_GAP, SyntheticConfig(random_seed=0))
    observations = [
        obs("p1", ActionType.PROBE_CORE, ["u0014"], ObservationOutcome.POSITIVE),
        obs("p2", ActionType.PROBE_CORE, ["u0022"], ObservationOutcome.POSITIVE),
        obs("g1", ActionType.HARD_NEGATIVE_GAP, ["u0018"], ObservationOutcome.NEGATIVE),
    ]
    materializer = M0SimpleRunMaterializer()
    assert len(materializer.materialize(timeline.units, observations, MaterializerConfig())) == 2
    observations.append(obs("r1", ActionType.PROBE_RELATION, ["u0014", "u0022"], ObservationOutcome.SAME))
    assert len(materializer.materialize(timeline.units, observations, MaterializerConfig())) == 1


def test_proxy_zero_event_remains_reachable():
    timeline = generate_timeline(Regime.R4_PROXY_INVISIBLE, SyntheticConfig(random_seed=0))
    result = run_episode(timeline, P0Uniform(), M0SimpleRunMaterializer(), budget=1)
    observation = result.observations[0]
    unit = {unit.unit_id: unit for unit in timeline.units}[observation.target_ids[0]]
    assert observation.action_type == ActionType.EXPLORE_CELL
    assert observation.outcome == ObservationOutcome.POSITIVE
    assert unit.cheap_score == 0.0


def test_materializer_interface():
    timeline = generate_timeline(Regime.R1_ISOLATED_EVENTS, SyntheticConfig(random_seed=0))
    observations = [obs("p1", ActionType.PROBE_CORE, [timeline.positive_evidence_unit_ids[0]], ObservationOutcome.POSITIVE)]
    for materializer in (M0SimpleRunMaterializer(), K3AdapterMaterializer()):
        events = materializer.materialize(timeline.units, observations, MaterializerConfig())
        assert isinstance(events, list)
        assert len(events) == 1


def test_serialization_round_trip(tmp_path: Path):
    original = obs("r1", ActionType.PROBE_RELATION, ["left", "right"], ObservationOutcome.DISTINCT)
    json_path = tmp_path / "observations.json"
    csv_path = tmp_path / "observations.csv"
    write_json(json_path, [original])
    write_csv(csv_path, [original])
    assert read_json(json_path, OracleObservation) == [original]
    assert read_csv(csv_path, OracleObservation) == [original]


def test_k3_adapter_matches_existing_behavior():
    timeline = generate_timeline(Regime.R1_ISOLATED_EVENTS, SyntheticConfig(random_seed=0))
    observations = [
        obs("p1", ActionType.PROBE_CORE, ["u0005"], ObservationOutcome.POSITIVE),
        obs("n1", ActionType.PROBE_CORE, ["u0006"], ObservationOutcome.NEGATIVE),
        obs("p2", ActionType.PROBE_CORE, ["u0007"], ObservationOutcome.POSITIVE),
    ]
    adapter = K3AdapterMaterializer()
    events = adapter.materialize(timeline.units, observations, MaterializerConfig())
    assert adapter.implementation_path.exists()
    assert len(events) == 2
    assert [event.anchor_ids for event in events] == [("u0005",), ("u0007",)]


def test_action_lineage_complete():
    timeline = generate_timeline(Regime.R2_ADJACENT_DISTINCT, SyntheticConfig(random_seed=0))
    result = run_episode(timeline, P4RelationAwareHeuristic(), M0SimpleRunMaterializer(), budget=5)
    relation = next(item for item in result.lineage if item.action_type == ActionType.PROBE_RELATION)
    assert relation.outcome == ObservationOutcome.DISTINCT
    assert relation.pre_event_count + 1 == relation.post_event_count
    assert relation.matched_event_delta == 1
    assert relation.pre_partition and relation.post_partition
    assert relation.selection_reason


def test_no_gt_access_during_planning():
    planners = [P0Uniform, P1TopPrior, P2ComponentFirst, P3CoreOnlyGreedy, P4RelationAwareHeuristic, P5NaiveHardGap]
    forbidden = ("ground_truth", "latent_unit_event_ids", "_timeline")
    for planner_cls in planners:
        signature = inspect.signature(planner_cls.choose_action)
        assert set(signature.parameters) == {"self", "units", "observations", "events", "remaining_budget"}
        source = inspect.getsource(planner_cls)
        assert not any(token in source for token in forbidden)
