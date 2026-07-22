"""Evaluator-only access to latent truth and trace recomputation."""

from __future__ import annotations

from .environment import ToyEnvironment
from .utility import jump_identity_auc, metrics_from_trace


def evaluate(environment: ToyEnvironment) -> dict:
    metrics = metrics_from_trace(environment.latent_for_evaluator(), environment.trace)
    identity = jump_identity_auc(environment.episode, metrics["commit_jumps"])
    metrics["auc_jump_identity"] = identity
    metrics["auc_identity_match"] = abs(identity - metrics["AnytimeAUC_F1"]) <= 1e-12
    return metrics

