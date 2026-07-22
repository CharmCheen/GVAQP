"""Independent trace/state invariant checks used by tests and smoke audit."""

from __future__ import annotations

from dataclasses import asdict

from .environment import ToyEnvironment
from .evaluator import evaluate


def audit_environment(env: ToyEnvironment) -> dict:
    failures: list[str] = []
    scanned = [entry.action.region_id for entry in env.trace if entry.action.kind == "SCAN"]
    confirmed = [entry.action.witness_id for entry in env.trace if entry.action.kind == "CONFIRM"]
    if len(scanned) != len(set(scanned)):
        failures.append("region_scanned_more_than_once")
    if len(confirmed) != len(set(confirmed)):
        failures.append("witness_confirmed_more_than_once")
    for entry in env.trace:
        if entry.completed_at > env.episode.horizon + 1e-12:
            failures.append("deadline_crossing")
        if entry.action.kind == "SCAN" and entry.committed_after != entry.committed_before:
            failures.append("scan_changed_committed_set")
        if entry.outcome != "NEW_COMMIT" and entry.committed_after != entry.committed_before:
            failures.append("failed_or_duplicate_confirm_committed")
        if entry.outcome == "NEW_COMMIT" and entry.committed_after != entry.committed_before + 1:
            failures.append("successful_confirm_not_exactly_one_commit")
        if entry.duration < -1e-12:
            failures.append("negative_duration")
    metrics = evaluate(env)
    if not metrics["auc_identity_match"]:
        failures.append("auc_identity_mismatch")
    if not env.stopped:
        failures.append("episode_not_stopped")
    visible = asdict(env.visible_state())
    forbidden = {"latent_event_id", "latent_events", "future_cost_draws", "future_oracle_draws", "cost_realizations"}
    def keys(value):
        if isinstance(value, dict):
            return set(value) | set().union(*(keys(v) for v in value.values()))
        if isinstance(value, list):
            return set().union(*(keys(v) for v in value)) if value else set()
        return set()
    if forbidden & keys(visible):
        failures.append("latent_visibility_leak")
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": sorted(set(failures)),
        "trace_entries": len(env.trace),
        "trace_recomputation": "PASS" if metrics["auc_identity_match"] else "FAIL",
    }
