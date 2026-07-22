"""Frozen SplitMix64 implementation; no dependency on library RNG versions."""

from __future__ import annotations

import math

MASK64 = (1 << 64) - 1


class SplitMix64:
    def __init__(self, seed: int):
        self.state = int(seed) & MASK64

    def next_uint64(self) -> int:
        self.state = (self.state + 0x9E3779B97F4A7C15) & MASK64
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
        return (z ^ (z >> 31)) & MASK64

    def uniform01(self) -> float:
        return (self.next_uint64() + 0.5) / float(1 << 64)

    def uniform(self, low: float, high: float) -> float:
        return low + (high - low) * self.uniform01()

    def log_uniform(self, low: float, high: float) -> float:
        return math.exp(math.log(low) + (math.log(high) - math.log(low)) * self.uniform01())

    def bernoulli(self, probability: float) -> bool:
        return self.uniform01() < probability

    def categorical(self, values, probabilities):
        u = self.uniform01()
        cumulative = 0.0
        for value, probability in zip(values, probabilities):
            cumulative += probability
            if u <= cumulative:
                return value
        return values[-1]

    def poisson(self, rate: float) -> int:
        if rate < 0 or not math.isfinite(rate):
            raise ValueError("Poisson rate must be finite and nonnegative")
        u = self.uniform01()
        k = 0
        probability = math.exp(-rate)
        cumulative = probability
        while u > cumulative:
            k += 1
            probability *= rate / k
            cumulative += probability
            if k > 100000:
                raise ArithmeticError("Poisson inversion failed to converge")
        return k


FIXTURE_SEED_1 = [
    10451216379200822465, 13757245211066428519, 17911839290282890590,
    8196980753821780235, 8195237237126968761, 14072917602864530048,
    16184226688143867045, 9648886400068060533,
]

