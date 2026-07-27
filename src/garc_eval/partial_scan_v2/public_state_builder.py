from __future__ import annotations

from dataclasses import dataclass, field

from .id_redaction import RunScopedIdMapper
from .protocol import CHOOSE_ACTION, INITIALIZE, POLICY_PROTOCOL_VERSION
from .public_schema import validate_choose_action, validate_initialize


@dataclass
class InternalRunState:
    internal_video_id: str
    duration_sec: float
    units: list[dict]
    budget_sec: float
    scanned_internal_unit_ids: list[str] = field(default_factory=list)
    current_internal_unit_id: str | None = None
    remaining_budget_sec: float = 0.0
    past_action_costs_sec: list[float] = field(default_factory=list)
    visible_internal_candidate_ids: list[str] = field(default_factory=list)
    last_result_class: str = "INITIAL"
    hidden_reference_event_ids: set[str] = field(default_factory=set, repr=False)
    hidden_future_costs: dict[str, float] = field(default_factory=dict, repr=False)
    hidden_output_paths: dict[str, str] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if self.remaining_budget_sec == 0.0:
            self.remaining_budget_sec = float(self.budget_sec)


def build_initialize_message(
    internal: InternalRunState,
    mapper: RunScopedIdMapper,
    public_contract_hash: str,
) -> dict:
    message = {
        "type": INITIALIZE,
        "protocol_version": POLICY_PROTOCOL_VERSION,
        "run_id": mapper.run_id,
        "video": {
            "video_id": mapper.video(internal.internal_video_id),
            "duration_sec": float(internal.duration_sec),
        },
        "units": [
            {
                "unit_id": mapper.unit(str(unit["unit_id"])),
                "start_sec": float(unit["start_sec"]),
                "end_sec": float(unit["end_sec"]),
            }
            for unit in internal.units
        ],
        "budget_sec": float(internal.budget_sec),
        "public_contract_hash": public_contract_hash,
    }
    return validate_initialize(message)


def build_public_state(
    internal: InternalRunState,
    mapper: RunScopedIdMapper,
    step_id: int,
) -> dict:
    scanned = [
        mapper.unit(value) for value in internal.scanned_internal_unit_ids
    ]
    covered = sum(
        float(unit["end_sec"]) - float(unit["start_sec"])
        for unit in internal.units
        if str(unit["unit_id"]) in set(internal.scanned_internal_unit_ids)
    )
    duration = max(float(internal.duration_sec), 1e-12)
    return {
        "step_id": int(step_id),
        "public_protocol_version": POLICY_PROTOCOL_VERSION,
        "scanned_unit_ids": scanned,
        "current_unit_id": (
            None
            if internal.current_internal_unit_id is None
            else mapper.unit(internal.current_internal_unit_id)
        ),
        "remaining_budget_sec": max(0.0, float(internal.remaining_budget_sec)),
        "past_action_costs_sec": [
            float(value) for value in internal.past_action_costs_sec
        ],
        "geometric_coverage": {
            "fraction": min(1.0, covered / duration),
            "covered_duration_sec": covered,
        },
        "revealed_observations": {
            "candidate_ids": mapper.candidate_ids(
                list(internal.visible_internal_candidate_ids)
            ),
            "last_completed_unit_id": (
                None
                if internal.current_internal_unit_id is None
                else mapper.unit(internal.current_internal_unit_id)
            ),
            "result_class": internal.last_result_class,
        },
    }


def build_choose_action_message(
    internal: InternalRunState,
    mapper: RunScopedIdMapper,
    step_id: int,
) -> dict:
    state = build_public_state(internal, mapper, step_id)
    message = {
        "type": CHOOSE_ACTION,
        "step_id": int(step_id),
        "state": state,
    }
    known = {mapper.unit(str(unit["unit_id"])) for unit in internal.units}
    return validate_choose_action(message, known)
