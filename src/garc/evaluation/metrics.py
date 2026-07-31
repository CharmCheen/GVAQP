from __future__ import annotations


def cumulative_utility(trace: list[dict]) -> list[int]:
    total = 0
    result = []
    for row in trace:
        if row.get("completed", True):
            total += int(row.get("new_distinct_utility", 0))
        result.append(total)
    return result


def utility_at_deadline(trace: list[dict], budget_sec: float) -> int:
    values = cumulative_utility(trace)
    return max((value for value, row in zip(values, trace) if float(row.get("elapsed_sec", 0)) <= budget_sec), default=0)
