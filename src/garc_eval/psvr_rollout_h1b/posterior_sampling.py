"""Finite approximate-model posterior sampling interface; visible-state input only."""
from __future__ import annotations
from typing import Protocol
from .crn import paired_draw_key, uniform01
from .types import VisibleDecisionState

class PosteriorWorldSamplerAPI(Protocol):
    def support_size(self, state: VisibleDecisionState) -> int: ...

def fixed_posterior_indices(state: VisibleDecisionState, sampler: PosteriorWorldSamplerAPI, h1b_seed: object, action_pair: str, configuration: tuple[int, int], count: int) -> tuple[int, ...]:
    """Fixed-count CRN schedule, with no adaptive resampling or hidden input."""
    size=sampler.support_size(state)
    if size <= 0 or count <= 0: raise ValueError("finite posterior support and count required")
    return tuple(min(size-1, int(uniform01(*paired_draw_key(h1b_seed, state.decision_index, index, 0, action_pair, configuration, 0, "posterior")) * size)) for index in range(count))
