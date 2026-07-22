"""R2 confirmatory-only seed materialization; importable only by its runner."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from .r2_rng import hkdf_sha256


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def generate_confirmatory_universe_once(output_root: Path, count: int) -> dict:
    """Generate a master secret and sealed, non-stdout seed manifest exactly once."""
    if output_root.exists():
        raise FileExistsError("confirmatory output root already exists")
    if count != 512:
        raise ValueError("R2 confirmatory episode count is frozen at 512")
    output_root.mkdir(parents=True)
    master = os.urandom(32)
    seeds = [int.from_bytes(hkdf_sha256(master, f"CONFIRMATORY_EXECUTION_RNG|{i}".encode(), 8), "big") for i in range(count)]
    commitment = hashlib.sha256(b"".join(seed.to_bytes(8, "big") for seed in seeds)).hexdigest()
    # The private values are written only inside the one-way attempt root; callers receive no values.
    _atomic_json(output_root / "sealed_seed_manifest.json", {"algorithm": "HKDF_SHA256_THEN_SPLITMIX64", "master_seed_hex": master.hex(), "episode_seeds": seeds, "commitment_sha256": commitment, "count": count})
    os.chmod(output_root / "sealed_seed_manifest.json", 0o600)
    _atomic_json(output_root / "attempt_ledger.json", {"status": "STARTED", "seed_commitment_sha256": commitment, "count": count, "episodes": {str(i): "NOT_STARTED" for i in range(count)}})
    return {"commitment_sha256": commitment, "count": count}
