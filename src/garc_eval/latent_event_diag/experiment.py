from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import pandas as pd

from .evaluation import evaluate, returned_seconds
from .materializers import K3AdapterMaterializer, M0SimpleRunMaterializer, MaterializerConfig
from .models import ActionLineage, AtomicUnit, MaterializedEvent, OracleObservation
from .oracles import SyntheticOracleSimulator
from .planners import (
    BasePlanner,
    P0Uniform,
    P1TopPrior,
    P2ComponentFirst,
    P3CoreOnlyGreedy,
    P4RelationAwareHeuristic,
    P5NaiveHardGap,
)
from .synthetic import Regime, SyntheticConfig, SyntheticTimeline, generate_timeline


PLANNERS: tuple[type[BasePlanner], ...] = (
    P0Uniform,
    P1TopPrior,
    P2ComponentFirst,
    P3CoreOnlyGreedy,
    P4RelationAwareHeuristic,
    P5NaiveHardGap,
)


@dataclass(frozen=True)
class EpisodeResult:
    observations: tuple[OracleObservation, ...]
    events: tuple[MaterializedEvent, ...]
    lineage: tuple[ActionLineage, ...]
    metrics: dict[str, float]


def partition(events: Sequence[MaterializedEvent]) -> tuple[dict, ...]:
    return tuple(
        {
            "event_id": event.event_id,
            "start_time": event.start_time,
            "end_time": event.end_time,
            "anchor_ids": list(event.anchor_ids),
        }
        for event in events
    )


def run_episode(
    timeline: SyntheticTimeline,
    planner: BasePlanner,
    materializer,
    budget: float,
    materializer_config: MaterializerConfig | None = None,
) -> EpisodeResult:
    config = materializer_config or MaterializerConfig()
    oracle = SyntheticOracleSimulator(timeline, seed=timeline.config.random_seed + 100003)
    units: Sequence[AtomicUnit] = timeline.public_units()
    observations: list[OracleObservation] = []
    lineage: list[ActionLineage] = []
    events = materializer.materialize(units, observations, config)
    spent = 0.0
    while spent < budget:
        action = planner.choose_action(units, observations, events, budget - spent)
        if action is None:
            break
        actual_cost = oracle.config.costs[action.action_type]
        if actual_cost > budget - spent + 1e-12:
            break
        pre_events = events
        pre_metrics = evaluate(pre_events, timeline.ground_truth_events, observations, units)
        observation = oracle.execute(action)
        observations.append(observation)
        spent += observation.cost
        events = materializer.materialize(units, observations, config)
        post_metrics = evaluate(events, timeline.ground_truth_events, observations, units)
        lineage.append(
            ActionLineage(
                action_id=action.action_id,
                budget_step=len(lineage),
                planner=planner.name,
                action_type=action.action_type,
                target=action.target_ids,
                pre_partition=partition(pre_events),
                outcome=observation.outcome,
                post_partition=partition(events),
                pre_event_count=len(pre_events),
                post_event_count=len(events),
                matched_event_delta=int(post_metrics["matched_event_count"] - pre_metrics["matched_event_count"]),
                returned_seconds_delta=returned_seconds(events) - returned_seconds(pre_events),
                selection_reason=action.selection_reason,
            )
        )
    return EpisodeResult(
        observations=tuple(observations),
        events=tuple(events),
        lineage=tuple(lineage),
        metrics=evaluate(events, timeline.ground_truth_events, observations, units),
    )


def run_smoke(output_dir: Path, seed_count: int = 20, budgets: Sequence[int] = (5, 10, 20, 40)) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_rows = []
    lineage_path = output_dir / "synthetic_action_lineage.jsonl"
    with lineage_path.open("w", encoding="utf-8") as lineage_file:
        for regime in Regime:
            for seed in range(seed_count):
                timeline = generate_timeline(regime, SyntheticConfig(random_seed=seed))
                for budget in budgets:
                    for planner_cls in PLANNERS:
                        for materializer_name, materializer in (
                            ("M0", M0SimpleRunMaterializer()),
                            ("K3_adapter", K3AdapterMaterializer()),
                        ):
                            result = run_episode(timeline, planner_cls(), materializer, budget)
                            sequence = ">".join(obs.action_type.value + ":" + ",".join(obs.target_ids) for obs in result.observations)
                            row = {
                                "regime": regime.value,
                                "seed": seed,
                                "budget": budget,
                                "planner": planner_cls.name,
                                "materializer": materializer_name,
                                "query_sequence": sequence,
                                **result.metrics,
                            }
                            raw_rows.append(row)
                            for item in result.lineage:
                                payload = item.to_dict()
                                payload.update(
                                    {
                                        "regime": regime.value,
                                        "seed": seed,
                                        "budget": budget,
                                        "materializer": materializer_name,
                                    }
                                )
                                lineage_file.write(json.dumps(payload, sort_keys=True) + "\n")
    raw = pd.DataFrame(raw_rows)
    metric_cols = [column for column in raw.columns if column not in {"regime", "seed", "budget", "planner", "materializer", "query_sequence"}]
    summary = raw.groupby(["regime", "budget", "planner", "materializer"], as_index=False)[metric_cols].mean()
    sequence_counts = raw.groupby(["regime", "budget", "planner", "materializer"])["query_sequence"].nunique().rename("distinct_query_sequences").reset_index()
    summary = summary.merge(sequence_counts, on=["regime", "budget", "planner", "materializer"])
    summary["seed_count"] = seed_count
    summary.to_csv(output_dir / "synthetic_smoke_summary.csv", index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run latent-event synthetic diagnostic smoke experiment.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed-count", type=int, default=20)
    parser.add_argument("--budgets", default="5,10,20,40")
    args = parser.parse_args()
    run_smoke(args.output_dir, args.seed_count, tuple(int(value) for value in args.budgets.split(",")))


if __name__ == "__main__":
    main()
