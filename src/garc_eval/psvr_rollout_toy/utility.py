"""D1 metrics, computed only from immutable episode truth and raw trace."""

from __future__ import annotations

from dataclasses import asdict

from .schema import Episode, TraceEntry


def _f1(committed: set[str], truth: set[str]) -> tuple[float, float, float]:
    if not committed:
        return 0.0, 1.0, 1.0 if not truth else 0.0
    tp = len(committed & truth)
    precision = tp / len(committed)
    recall = 1.0 if not truth else tp / len(truth)
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return f1, precision, recall


def metrics_from_trace(episode: Episode, trace: list[TraceEntry] | tuple[TraceEntry, ...]) -> dict:
    truth = {event.event_id for event in episode.events}
    committed: set[str] = set()
    false_positive_ids: set[str] = set()
    f1_value = 0.0
    auc_area = 0.0
    previous_time = 0.0
    first_commit = None
    duplicates = 0
    surrogate = 0.0
    commit_jumps = []
    for entry in trace:
        if entry.outcome == "DUPLICATE":
            duplicates += 1
        if entry.outcome != "NEW_COMMIT":
            continue
        auc_area += f1_value * (entry.completed_at - previous_time)
        previous_time = entry.completed_at
        event_id = entry.witness_event_id
        before = set(committed)
        if event_id is None:
            fp_id = f"fp_{entry.sequence}"
            false_positive_ids.add(fp_id)
            surrogate -= max(episode.horizon - entry.completed_at, 0.0)
        else:
            committed.add(event_id)
            if event_id not in before:
                surrogate += max(episode.horizon - entry.completed_at, 0.0)
                first_commit = entry.completed_at if first_commit is None else first_commit
        new_f1, _, _ = _f1(committed | false_positive_ids, truth)
        commit_jumps.append({"time": entry.completed_at, "delta_f1": new_f1 - f1_value, "event_id": event_id})
        f1_value = new_f1
    auc_area += f1_value * (episode.horizon - previous_time)
    f1_final, precision, recall = _f1(committed | false_positive_ids, truth)
    confirm_count = sum(entry.action.kind == "CONFIRM" for entry in trace)
    return {
        "status": "DEBUG_ONLY_NOT_FOR_SCIENTIFIC_USE" if episode.split != "heldout" else "HELDOUT_SCIENTIFIC_RESULT",
        "episode_id": episode.episode_id,
        "time_weighted_unique_event_utility": surrogate,
        "AnytimeAUC_F1": auc_area / episode.horizon,
        "TTFC": episode.horizon if first_commit is None else first_commit,
        "TTFC_no_commit": first_commit is None,
        "unique_committed_events_at_T": len(committed),
        "event_precision_at_T": precision,
        "event_recall_at_T": recall,
        "event_F1_at_T": f1_final,
        "duplicate_CONFIRM_count": duplicates,
        "duplicate_CONFIRM_rate": 0.0 if confirm_count == 0 else duplicates / confirm_count,
        "commit_jumps": commit_jumps,
        "trace_sha_input": [asdict(entry) for entry in trace],
    }


def jump_identity_auc(episode: Episode, commit_jumps: list[dict]) -> float:
    return sum(row["delta_f1"] * (episode.horizon - row["time"]) for row in commit_jumps) / episode.horizon

