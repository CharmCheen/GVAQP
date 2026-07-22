"""Frozen independent R2 RNG namespaces (HKDF-SHA256 then SplitMix64)."""

from __future__ import annotations

import hashlib
import hmac

from .rng import SplitMix64


NAMESPACES = (
    "FIXTURE_RNG", "DEVELOPMENT_EXECUTION_RNG", "DEVELOPMENT_PLANNING_RNG",
    "CONFIRMATORY_EXECUTION_RNG", "CONFIRMATORY_PLANNING_RNG",
)


def hkdf_sha256(ikm: bytes, info: bytes, length: int = 32) -> bytes:
    prk = hmac.new(b"PSVR-R2-HKDF-SALT", ikm, hashlib.sha256).digest()
    output = b""
    previous = b""
    counter = 1
    while len(output) < length:
        previous = hmac.new(prk, previous + info + bytes([counter]), hashlib.sha256).digest()
        output += previous
        counter += 1
    return output[:length]


def stream(master: bytes, namespace: str, *keys: object) -> SplitMix64:
    if namespace not in NAMESPACES:
        raise ValueError(f"unknown R2 RNG namespace: {namespace}")
    info = (namespace + "|" + "|".join(map(str, keys))).encode("utf-8")
    seed = int.from_bytes(hkdf_sha256(master, info, 8), "big")
    return SplitMix64(seed)
