"""Unfrozen information-firewall interfaces for a future Branch-A kernel.

This module does not define the missing scientific posterior.  It defines the
boundary that an authorized posterior implementation must satisfy: M1 receives
only an immutable visible history and fresh conditional model worlds.  It can
never retain or clone the realized evaluation environment.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

from .environment import ToyEnvironment
from .policies import ShieldedPi0
from .schema import Action, TraceEntry, VisibleState
from .serialization import sha256_value
from .utility import metrics_from_trace


@dataclass(frozen=True)
class VisibleHistory:
    """Canonical policy information at one decision boundary."""

    decision_index: int
    state: VisibleState
    visible_trace: tuple[TraceEntry, ...]

    @property
    def digest(self) -> str:
        return sha256_value(self)


class ConditionalWorldSampler(Protocol):
    """Authorized model posterior, deliberately separated from actual truth."""

    kernel_id: str
    realized_episode_access: bool

    def sample(self, history: VisibleHistory, action: Action, sample_index: int) -> ToyEnvironment:
        """Return a fresh model world at exactly ``history.state``."""


@dataclass(frozen=True)
class ConditionalEstimate:
    action_id: str
    mean: float
    samples: int
    ci99_half_width: float
    converged: bool
    continuation_policy: str = "B1_SHIELDED_PI0"
    full_horizon: bool = True
    primary_planning_cost: float = 0.0


class SymmetricConditionalRolloutEvaluator:
    """Estimate candidate value without a reference to the realized Episode.

    The scientific kernel remains blocked.  This evaluator is usable only with
    a separately authorized ``ConditionalWorldSampler``.  All candidates use
    the same continuation rule and full horizon.
    """

    Z99 = 2.5758293035489004

    def __init__(
        self,
        sampler: ConditionalWorldSampler,
        history: VisibleHistory,
        absolute_tolerance: float,
        max_samples: int = 100_000_000,
        min_samples: int = 2,
    ) -> None:
        if sampler.realized_episode_access:
            raise ValueError("conditional sampler must not access realized episode truth")
        if absolute_tolerance <= 0 or min_samples < 2 or max_samples < min_samples:
            raise ValueError("invalid frozen MC controls")
        self.sampler = sampler
        self.history = history
        self.absolute_tolerance = absolute_tolerance
        self.max_samples = max_samples
        self.min_samples = min_samples
        self.estimates: dict[str, ConditionalEstimate] = {}

    def __call__(self, action: Action, visible_state: VisibleState) -> float:
        if visible_state != self.history.state:
            raise ValueError("stale or foreign visible state")
        n = 0
        mean = 0.0
        m2 = 0.0
        half_width = math.inf
        while n < self.max_samples:
            world = self.sampler.sample(self.history, action, n)
            if world.visible_state() != visible_state:
                raise ValueError("conditional model world does not match visible history")
            if world is getattr(self.sampler, "realized_environment", None):
                raise ValueError("sampler returned realized environment object")
            branch = world.clone()
            branch.execute(action)
            if action.kind != "STOP":
                branch.run(ShieldedPi0())
            value = metrics_from_trace(branch.episode, branch.trace)["time_weighted_unique_event_utility"]
            n += 1
            delta = value - mean
            mean += delta / n
            m2 += delta * (value - mean)
            if n >= self.min_samples:
                variance = m2 / (n - 1)
                half_width = self.Z99 * math.sqrt(variance / n)
                if half_width <= self.absolute_tolerance:
                    break
        estimate = ConditionalEstimate(
            action.identifier, mean, n, half_width, half_width <= self.absolute_tolerance
        )
        self.estimates[action.identifier] = estimate
        if not estimate.converged:
            raise RuntimeError("NUMERICAL_BLOCK: frozen 99% CI tolerance not reached")
        return mean

