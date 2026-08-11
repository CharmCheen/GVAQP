from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GammaPoisson:
    alpha: float = 1.0
    beta: float = 1.0
    n: int = 0
    total: int = 0

    @property
    def mean(self) -> float:
        return (self.alpha + self.total) / (self.beta + self.n)

    def update(self, count: int) -> None:
        self.n += 1
        self.total += int(count)


@dataclass
class BetaBernoulli:
    alpha: float = 1.0
    beta: float = 1.0
    n: int = 0
    successes: int = 0

    @property
    def mean(self) -> float:
        return (self.alpha + self.successes) / (self.alpha + self.beta + self.n)

    def update(self, success: int) -> None:
        self.n += 1
        self.successes += int(bool(success))

