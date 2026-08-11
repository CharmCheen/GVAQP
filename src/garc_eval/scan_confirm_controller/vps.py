from __future__ import annotations


def bucket(value: float, cuts: tuple[float, float]) -> str:
    if value < cuts[0]:
        return "LOW"
    if value < cuts[1]:
        return "MEDIUM"
    return "HIGH"


def value_per_second(value: float, cost: float, normalize: bool = True) -> float:
    return value / max(cost, 1e-12) if normalize else value

