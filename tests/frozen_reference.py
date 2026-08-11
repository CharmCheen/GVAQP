"""Literal narrow references transcribed from source commit 5047241b... for parity tests."""


def source_largest_gap(count, scanned):
    remaining = [i for i in range(count) if i not in set(scanned)]
    if not scanned:
        return remaining[len(remaining) // 2]
    return max(remaining, key=lambda i: (min(abs(i - j) for j in scanned), -i))


def source_fixed_ratio(state, scan_time, confirm_time):
    scan = state["estimated_scan_cost_sec"] <= state["remaining_budget_sec"]
    confirm = state["frontier_size"] > 0 and state["estimated_confirm_cost_sec"] <= state["remaining_budget_sec"]
    legal = (["SCAN"] if scan else []) + (["CONFIRM"] if confirm else [])
    if not legal:
        return "STOP"
    rho = scan_time / max(scan_time + confirm_time, 1e-12)
    desired = "SCAN" if rho < .25 or scan_time + confirm_time == 0 else "CONFIRM"
    return desired if desired in legal else legal[0]


def source_frontier_order(rows):
    return sorted(rows, key=lambda row: (-row.score, row.unit_id, row.track_id, row.candidate_id))


class SourceFrozenFrontier:
    """Literal source-commit Frontier adapter used only as a differential oracle."""

    def __init__(self, capacity=10):
        self.capacity = int(capacity)
        self.rows_by_unit = {}
        self.discarded = set()
        self.queried = set()

    def update(self, candidates):
        prior = set(self.rows_by_unit)
        for row in candidates:
            if row.unit_id not in self.queried and row.unit_id not in self.discarded:
                self.rows_by_unit[row.unit_id] = row
        ordered = source_frontier_order(self.rows_by_unit.values())
        dropped = [row.unit_id for row in ordered[self.capacity:]]
        for unit_id in dropped:
            self.rows_by_unit.pop(unit_id, None)
            self.discarded.add(unit_id)
        return len(set(self.rows_by_unit) - prior), dropped

    def best(self):
        return source_frontier_order(self.rows_by_unit.values())[0] if self.rows_by_unit else None

    def terminalize(self, unit_id):
        self.rows_by_unit.pop(int(unit_id), None)
        self.queried.add(int(unit_id))


def source_linear_quantile(values, quantile):
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return float("inf")
    position = (len(ordered) - 1) * quantile
    lower, upper = int(position // 1), int(-(-position // 1))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def source_materialize(candidate):
    return {"candidate_id": candidate.candidate_id, "unit_id": candidate.unit_id,
            "track_id": candidate.track_id, "payload": dict(candidate.payload or {})}


def source_materialize_result(positive, utility_ids):
    return tuple(sorted(set(map(str, utility_ids)))) if positive else ()


def source_final_snapshot(actions, utility_ids, final_result, stop_reason, error=None):
    value = {"status": "FINAL", "actions": actions,
             "distinct_utility_ids": sorted(set(utility_ids)),
             "final_result": final_result, "stop_reason": stop_reason}
    if error is not None:
        value["error"] = error
    return value


def source_admission(estimate, remaining):
    return estimate <= remaining


def source_cumulative_utility(trace):
    total, result = 0, []
    for row in trace:
        if row.get("completed", True):
            total += int(row.get("new_distinct_utility", 0))
        result.append(total)
    return result
