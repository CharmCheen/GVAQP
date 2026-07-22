"""Deterministic keyed common-random-number draws, isolated from experiment seeds."""
from __future__ import annotations
import hashlib

def digest(*parts: object) -> bytes:
    key = "|".join(str(part) for part in parts).encode("utf-8")
    return hashlib.sha256(key).digest()

def uniform01(*parts: object) -> float:
    return int.from_bytes(digest(*parts)[:8], "big") / 2**64

def sign(*parts: object) -> int:
    return 1 if digest(*parts)[0] & 1 else -1

def planning_key(episode_public_id: str, decision_index: int, posterior_sample_index: int, transition_index: int, variable_family: str) -> tuple[object, ...]:
    return ("H1B_CRN", episode_public_id, decision_index, posterior_sample_index, transition_index, variable_family)

def paired_draw_key(episode_public_id: str, decision_index: int, posterior_sample_index: int, transition_index: int, action_pair: str, configuration: tuple[int, int], trajectory_index: int, variable_family: str) -> tuple[object, ...]:
    return ("H1B_CRN", episode_public_id, decision_index, posterior_sample_index, transition_index, action_pair, configuration[0], configuration[1], trajectory_index, variable_family)

def error_key(seed: object, decision_index: int, mechanism: str, form: str, trajectory_index: int, target_identity: str, draw_index: int) -> tuple[object, ...]:
    return ("H1B_ERROR", seed, decision_index, mechanism, form, trajectory_index, target_identity, draw_index)
