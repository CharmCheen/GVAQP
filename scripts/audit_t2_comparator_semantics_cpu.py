"""CPU-only audit of T2 comparator fairness and policy observability.

This script reads frozen T2 artifacts and replays the already-consumed six
video-query workloads only for diagnostic auditing.  It does not select a new
policy, tune a threshold, or authorize a new algorithm claim.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import statistics

from garc.causal_frontier import (
    CausalFrontierReplay,
    ConstantCostModel,
    DatbSVPolicy,
    ExSampleEndToEndPolicy,
)
import run_h2_synthetic_mechanism_v1 as h2v1
import run_h2_synthetic_mechanism_v3 as h2v3
import run_t2_c1_existing_corpus_replay as t2


EPS = 1e-12
SCHEMA_VERSION = "T2_COMPARATOR_SEMANTICS_CPU_AUDIT_V1"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise RuntimeError(f"refusing to write empty table: {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def key(row: dict[str, str]) -> tuple[str, float, int, int]:
    return (
        row["workload_id"],
        float(row["verify_scan_cost_ratio"]),
        int(row["deadline_level"]),
        int(row["base_seed"]),
    )


def comparator_audit(raw_rows: list[dict[str, str]]) -> tuple[dict, list[dict], list[dict], list[dict]]:
    datb = {
        key(row): float(row["normalized_anytime_event_auc"])
        for row in raw_rows
        if row["policy"] == "datb_sv"
    }
    exsample: dict[int, dict[tuple[str, float, int, int], float]] = {}
    for row in raw_rows:
        if row["policy"] != "exsample_end_to_end_adapted":
            continue
        chunk = int(row["chunk_count"])
        exsample.setdefault(chunk, {})[key(row)] = float(
            row["normalized_anytime_event_auc"]
        )
    if not datb or not exsample:
        raise RuntimeError("missing DATB or ExSample rows")
    if any(set(rows) != set(datb) for rows in exsample.values()):
        raise RuntimeError("comparator key mismatch")

    fixed_rows = []
    for chunk, values in sorted(exsample.items()):
        deltas = [datb[item] - values[item] for item in datb]
        fixed_rows.append(
            {
                "chunk_count": chunk,
                "mean_exsample_auc": statistics.fmean(values.values()),
                "mean_datb_minus_exsample_auc": statistics.fmean(deltas),
                "median_datb_minus_exsample_auc": statistics.median(deltas),
                "positive_pairs": sum(value > EPS for value in deltas),
                "equal_pairs": sum(abs(value) <= EPS for value in deltas),
                "negative_pairs": sum(value < -EPS for value in deltas),
            }
        )
    best_global_chunk = max(
        exsample,
        key=lambda chunk: (statistics.fmean(exsample[chunk].values()), -chunk),
    )
    envelope = {
        item: max(values[item] for values in exsample.values()) for item in datb
    }
    envelope_delta = statistics.fmean(datb[item] - envelope[item] for item in datb)
    oracle_bonus = statistics.fmean(
        envelope[item] - exsample[best_global_chunk][item] for item in datb
    )

    cost_rows = []
    for chunk, values in sorted(exsample.items()):
        for ratio in sorted({item[1] for item in datb}):
            selected = [item for item in datb if item[1] == ratio]
            cost_rows.append(
                {
                    "chunk_count": chunk,
                    "verify_scan_cost_ratio": ratio,
                    "mean_datb_minus_exsample_auc": statistics.fmean(
                        datb[item] - values[item] for item in selected
                    ),
                    "paired_rows": len(selected),
                }
            )

    workloads = sorted({item[0] for item in datb})
    logo_rows = []
    logo_deltas = []
    for held_out in workloads:
        training_keys = [item for item in datb if item[0] != held_out]
        selected_chunk = max(
            exsample,
            key=lambda chunk: (
                statistics.fmean(exsample[chunk][item] for item in training_keys),
                -chunk,
            ),
        )
        held_out_keys = [item for item in datb if item[0] == held_out]
        delta = statistics.fmean(
            datb[item] - exsample[selected_chunk][item] for item in held_out_keys
        )
        logo_deltas.extend(
            datb[item] - exsample[selected_chunk][item] for item in held_out_keys
        )
        logo_rows.append(
            {
                "held_out_workload_id": held_out,
                "selected_chunk_from_other_workloads": selected_chunk,
                "mean_held_out_datb_minus_exsample_auc": delta,
                "paired_rows": len(held_out_keys),
            }
        )

    summary = {
        "best_global_fixed_chunk": best_global_chunk,
        "best_global_fixed_exsample_mean_auc": statistics.fmean(
            exsample[best_global_chunk].values()
        ),
        "datb_mean_auc": statistics.fmean(datb.values()),
        "datb_minus_per_row_oracle_envelope_mean_auc": envelope_delta,
        "oracle_envelope_bonus_over_best_global_fixed_mean_auc": oracle_bonus,
        "oracle_bonus_fraction_of_reported_absolute_gap": (
            oracle_bonus / abs(envelope_delta) if abs(envelope_delta) > EPS else None
        ),
        "leave_one_workload_out_datb_minus_selected_exsample_mean_auc": statistics.fmean(
            logo_deltas
        ),
        "paired_rows": len(datb),
        "workloads": len(workloads),
    }
    return summary, fixed_rows, cost_rows, logo_rows


def action_trace(result) -> tuple[tuple[str, str | None], ...]:
    return tuple(
        (entry.action, entry.target_id)
        for entry in result.trace
        if entry.status == "COMPLETED"
    )


def trace_identity_audit(proxy_root: Path, outcomes_path: Path) -> tuple[dict, list[dict]]:
    proxies = t2.load_proxy(proxy_root)
    outcomes = t2.load_outcomes(outcomes_path)
    query_ids = sorted({query for _, query in outcomes})
    if len(query_ids) != 2:
        raise RuntimeError("trace audit expects exactly two historical queries")

    rows = []
    # One preregistered representative condition is sufficient for this
    # diagnostic because DATB is deterministic and the code audit establishes
    # the degeneracy.  Replaying the full grid would duplicate the 4,214-second
    # T2 workload without adding claim-grade evidence.
    ratio = 10.0
    deadline_level = 0
    fraction = t2.DEADLINE_FRACTIONS[deadline_level]
    seed = h2v3.HOLDOUT_SEEDS[0]
    for video in t2.VIDEOS:
        workloads = {}
        for query in query_ids:
            fixed_proxy, fixed_outcomes, _, _ = t2.select_fixed_windows(
                proxies[video], outcomes[(video, query)]
            )
            workloads[query] = t2.build_workload(fixed_proxy, fixed_outcomes)
        traces = {"datb_sv": {}, "exsample_chunk6": {}}
        for query in query_ids:
            cells, oracle, event_count, _ = workloads[query]
            deadline = len(cells) * (1.0 + ratio) * fraction
            costs = ConstantCostModel(1.0, ratio)
            datb_result = CausalFrontierReplay(
                cells, oracle, costs, deadline, event_count
            ).run(DatbSVPolicy())
            policy_seed = h2v1.stable_seed(6 + deadline_level, seed)
            exsample_result = CausalFrontierReplay(
                cells, oracle, costs, deadline, event_count
            ).run(ExSampleEndToEndPolicy(policy_seed, chunk_count=6))
            traces["datb_sv"][query] = action_trace(datb_result)
            traces["exsample_chunk6"][query] = action_trace(exsample_result)
        rows.append(
            {
                "video_id": video,
                "verify_scan_cost_ratio": ratio,
                "deadline_level": deadline_level,
                "deadline_fraction": fraction,
                "base_seed": seed,
                "datb_trace_identical_across_queries": (
                    traces["datb_sv"][query_ids[0]]
                    == traces["datb_sv"][query_ids[1]]
                ),
                "datb_trace_length_query_1": len(
                    traces["datb_sv"][query_ids[0]]
                ),
                "datb_trace_length_query_2": len(
                    traces["datb_sv"][query_ids[1]]
                ),
                "exsample_chunk6_trace_identical_across_queries": (
                    traces["exsample_chunk6"][query_ids[0]]
                    == traces["exsample_chunk6"][query_ids[1]]
                ),
            }
        )
    summary = {
        "representative_condition": {
            "verify_scan_cost_ratio": ratio,
            "deadline_fraction": fraction,
            "base_seed": seed,
        },
        "query_pair_conditions": len(rows),
        "datb_identical_trace_conditions": sum(
            str(row["datb_trace_identical_across_queries"]).lower() == "true"
            for row in rows
        ),
        "exsample_chunk6_identical_trace_conditions": sum(
            str(row["exsample_chunk6_trace_identical_across_queries"]).lower() == "true"
            for row in rows
        ),
    }
    return summary, rows


def execute(args: argparse.Namespace) -> None:
    if args.output.exists():
        raise RuntimeError(f"refusing to overwrite existing output: {args.output}")
    args.output.mkdir(parents=True)
    raw_rows = read_csv(args.raw_policy_results)
    comparator, fixed_rows, cost_rows, logo_rows = comparator_audit(raw_rows)
    trace_summary, trace_rows = trace_identity_audit(args.proxy_root, args.outcomes)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "classification": "CPU_READ_ONLY_DIAGNOSTIC_CONSUMED_WORKLOADS",
        "comparator": comparator,
        "trace_identity": trace_summary,
        "claim_boundary": (
            "Retires current DATB superiority; does not establish deployable "
            "ExSample superiority or natural adaptive headroom."
        ),
    }
    write_csv(args.output / "fixed_chunk_comparison.csv", fixed_rows)
    write_csv(args.output / "cost_ratio_comparison.csv", cost_rows)
    write_csv(args.output / "leave_one_workload_out.csv", logo_rows)
    write_csv(args.output / "query_trace_identity.csv", trace_rows)
    (args.output / "SUMMARY.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    comparator_lines = "\n".join(
        f"- chunk {row['chunk_count']}: DATB-minus-fixed-ExSample mean AUC "
        f"{float(row['mean_datb_minus_exsample_auc']):+.6f}"
        for row in fixed_rows
    )
    report = f"""# T2 Comparator and Policy-Semantics CPU Audit

## Verdict

`CURRENT_DATB_RETIRED_DEPLOYABLE_EXSAMPLE_SUPERIORITY_NOT_ESTABLISHED`

This is a read-only diagnostic over the six consumed T2 workloads. It is not a
new algorithm comparison and cannot authorize policy tuning.

## Fixed ExSample configurations

{comparator_lines}

- Per-row oracle-envelope DATB delta: {comparator['datb_minus_per_row_oracle_envelope_mean_auc']:+.6f}
- Oracle bonus over best global fixed chunk: {comparator['oracle_envelope_bonus_over_best_global_fixed_mean_auc']:+.6f}
- Oracle bonus fraction of the reported absolute gap: {comparator['oracle_bonus_fraction_of_reported_absolute_gap']:.3f}
- Leave-one-workload-out DATB delta: {comparator['leave_one_workload_out_datb_minus_selected_exsample_mean_auc']:+.6f}

## Query observability diagnostic

- DATB identical action traces across the two queries: {trace_summary['datb_identical_trace_conditions']}/{trace_summary['query_pair_conditions']}
- Fixed-chunk-6 ExSample identical traces: {trace_summary['exsample_chunk6_identical_trace_conditions']}/{trace_summary['query_pair_conditions']}

The DATB result is consistent with the audited adapter: every scanned cell
exposes a candidate, candidate participant IDs are empty, and VERIFY outcomes do
not alter DATB's future value calculation. Human labels cannot repair this
policy-state degeneracy.

## Claim boundary

- Current DATB robust superiority is not supported and the branch remains retired.
- Failure to beat a per-row oracle envelope does not establish that one deployable
  fixed ExSample configuration consistently dominates DATB.
- These consumed workloads cannot be reused to select a new policy.
"""
    (args.output / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-policy-results", type=Path, required=True)
    parser.add_argument("--proxy-root", type=Path, required=True)
    parser.add_argument("--outcomes", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    execute(parser.parse_args())


if __name__ == "__main__":
    main()
