from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass, field


def opaque_id(
    secret: bytes,
    kind: str,
    internal_id: str,
    run_id: str,
    length: int,
) -> str:
    payload = f"{kind}:{run_id}:{internal_id}".encode("utf-8")
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()[:length]


def new_public_run_id() -> str:
    return "r_" + secrets.token_hex(16)


@dataclass
class RunScopedIdMapper:
    run_id: str
    secret: bytes = field(default_factory=lambda: secrets.token_bytes(32), repr=False)
    _unit_forward: dict[str, str] = field(default_factory=dict, init=False, repr=False)
    _unit_reverse: dict[str, str] = field(default_factory=dict, init=False, repr=False)
    _candidate_forward: dict[str, str] = field(default_factory=dict, init=False, repr=False)

    def video(self, internal_id: str) -> str:
        return "v_" + opaque_id(self.secret, "video", internal_id, self.run_id, 16)

    def unit(self, internal_id: str) -> str:
        if internal_id not in self._unit_forward:
            public = "u_" + opaque_id(
                self.secret, "unit", internal_id, self.run_id, 20
            )
            if public in self._unit_reverse:
                raise RuntimeError("opaque unit identifier collision")
            self._unit_forward[internal_id] = public
            self._unit_reverse[public] = internal_id
        return self._unit_forward[internal_id]

    def internal_unit(self, public_id: str) -> str:
        return self._unit_reverse[public_id]

    def candidate(self, internal_id: str) -> str:
        if internal_id not in self._candidate_forward:
            self._candidate_forward[internal_id] = "c_" + opaque_id(
                self.secret, "candidate", internal_id, self.run_id, 20
            )
        return self._candidate_forward[internal_id]

    def candidate_ids(self, internal_ids: list[str]) -> list[str]:
        values = [self.candidate(value) for value in internal_ids]
        if len(values) != len(set(values)):
            raise RuntimeError("opaque candidate identifier collision")
        return sorted(values)
