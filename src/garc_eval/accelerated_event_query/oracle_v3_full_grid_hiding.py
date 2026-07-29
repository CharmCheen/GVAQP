"""Capability boundaries between exhaustive evaluator labels and runtime state."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .model_relative_labels import ModelRelativeUnitLabel
from .oracle_v3_manifest import canonical_hash


@dataclass(frozen=True)
class EvaluatorCapability:
    """Opaque in-process capability retained by the evaluator owner."""

    nonce_sha256: str


@dataclass(frozen=True)
class SignedVerifyResult:
    unit_id: str
    action_id: str
    completed_at_seconds: float
    authoritative_label: str
    payload_sha256: str
    signature_hex: str

    def unsigned(self) -> dict:
        return {
            "unit_id": self.unit_id,
            "action_id": self.action_id,
            "completed_at_seconds": self.completed_at_seconds,
            "authoritative_label": self.authoritative_label,
            "payload_sha256": self.payload_sha256,
        }


class VerifyCompletionAuthority:
    """Mint causally completed VERIFY results; the controller never gets the key."""

    def __init__(self, private_key_seed: bytes):
        if len(private_key_seed) != 32:
            raise ValueError("Ed25519 private-key seed must contain exactly 32 bytes")
        self.__private_key = Ed25519PrivateKey.from_private_bytes(private_key_seed)

    def issue(
        self,
        *,
        unit_id: str,
        action_id: str,
        completed_at_seconds: float,
        authoritative_label: str,
        payload_sha256: str,
    ) -> SignedVerifyResult:
        if authoritative_label not in {"relevant", "not_relevant", "unknown", "parse_failure"}:
            raise ValueError("invalid VERIFY outcome")
        if not unit_id or not action_id or completed_at_seconds < 0:
            raise ValueError("invalid VERIFY completion identity")
        unsigned = {
            "unit_id": unit_id,
            "action_id": action_id,
            "completed_at_seconds": completed_at_seconds,
            "authoritative_label": authoritative_label,
            "payload_sha256": payload_sha256,
        }
        signature = self.__private_key.sign(
            json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
        ).hex()
        return SignedVerifyResult(**unsigned, signature_hex=signature)

    def public_verification_key(self) -> bytes:
        """Return a verification-only key that cannot mint controller-visible results."""
        return self.__private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )


class RuntimeVerifyHistory:
    """Public controller state containing only authenticated, past VERIFY results."""

    def __init__(self, public_verification_key: bytes):
        self.__verification_key = Ed25519PublicKey.from_public_bytes(
            public_verification_key
        )
        self.__revealed: dict[str, SignedVerifyResult] = {}

    def accept(self, result: SignedVerifyResult, *, current_time_seconds: float) -> None:
        unsigned = result.unsigned()
        try:
            self.__verification_key.verify(
                bytes.fromhex(result.signature_hex),
                json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode(),
            )
        except (InvalidSignature, ValueError) as exc:
            raise PermissionError("unauthenticated VERIFY result") from exc
        if result.completed_at_seconds > current_time_seconds:
            raise PermissionError("future VERIFY result cannot enter public state")
        prior = self.__revealed.get(result.unit_id)
        if prior is not None and prior != result:
            raise RuntimeError("revealed VERIFY result changed")
        self.__revealed[result.unit_id] = result

    def public_rows(self) -> tuple[dict, ...]:
        return tuple(
            result.unsigned()
            for result in sorted(
                self.__revealed.values(), key=lambda row: (
                    row.completed_at_seconds, row.unit_id, row.action_id
                )
            )
        )

    def public_state_hash(self, public_observations: Mapping) -> str:
        return canonical_hash({
            "public_observations": dict(public_observations),
            "revealed_verify_results": list(self.public_rows()),
        })


class EvaluatorOnlyLabelStore:
    """Full reference labels with no controller-facing lookup method."""

    def __init__(
        self,
        labels: Iterable[ModelRelativeUnitLabel],
        capability: EvaluatorCapability,
    ):
        rows = list(labels)
        if len({row.unit_id for row in rows}) != len(rows):
            raise ValueError("duplicate unit identifier")
        self.__labels = {row.unit_id: row for row in rows}
        self.__capability_hash = canonical_hash(asdict(capability))

    def evaluator_rows(
        self, capability: EvaluatorCapability
    ) -> tuple[ModelRelativeUnitLabel, ...]:
        if canonical_hash(asdict(capability)) != self.__capability_hash:
            raise PermissionError("evaluator capability required")
        return tuple(self.__labels[key] for key in sorted(self.__labels))

    def controller_view(self, *_args, **_kwargs):
        raise PermissionError(
            "full-grid labels are evaluator-only; runtime labels arrive only as signed VERIFY results"
        )


def assert_runtime_path_isolation(
    *, runtime_import_roots: Iterable[Path], evaluator_output_root: Path
) -> None:
    """Fail closed if evaluator artifacts are importable from a runtime root."""

    evaluator = evaluator_output_root.resolve()
    for root in runtime_import_roots:
        resolved = root.resolve()
        if resolved == evaluator or resolved.is_relative_to(evaluator) or evaluator.is_relative_to(resolved):
            raise RuntimeError("runtime import root overlaps evaluator-only output root")
