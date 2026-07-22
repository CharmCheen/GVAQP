"""Explicit R2 split loaders and contamination guard.

The confirmatory generator deliberately lives in ``r2_confirmatory``.  This
module must remain safe to import from tests and development-only code.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from .r2 import World, finite_world_library


ROOT = Path(__file__).resolve().parents[3]
LEGACY_HELDOUT = ROOT / "outputs/psvr_rollout_preimplementation/TOY_HELDOUT_SEEDS.json"
LEGACY_HELDOUT_SHA256 = "6d9120141ff8dc0d9701e816259e90389fe5cba36226889fe9d39c33774c0c99"
LEGACY_HELDOUT_MIN = 91000
LEGACY_HELDOUT_MAX = 91511
DEVELOPMENT_SEEDS = ROOT / "outputs/psvr_rollout_preimplementation/TOY_DEVELOPMENT_SEEDS.json"


class ContaminatedHeldoutUniverseError(RuntimeError):
    pass


@dataclass(frozen=True)
class DevelopmentEpisode:
    opaque_id: str
    world: World


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reject_contaminated(value: str | Path | int) -> None:
    if isinstance(value, int) and LEGACY_HELDOUT_MIN <= value <= LEGACY_HELDOUT_MAX:
        raise ContaminatedHeldoutUniverseError("contaminated held-out seed identity is permanently forbidden")
    path = Path(value) if not isinstance(value, int) else None
    if path is not None and (path.resolve() == LEGACY_HELDOUT.resolve() or (path.exists() and _sha(path) == LEGACY_HELDOUT_SHA256)):
        raise ContaminatedHeldoutUniverseError("contaminated held-out universe path/hash is permanently forbidden")
    if isinstance(value, str) and value == LEGACY_HELDOUT_SHA256:
        raise ContaminatedHeldoutUniverseError("contaminated held-out universe hash is permanently forbidden")


def load_fixture_universe() -> tuple[World, ...]:
    """Public deterministic fixture worlds; no seed file is read."""
    return finite_world_library()[:3]


def load_development_universe(limit: int | None = None) -> tuple[DevelopmentEpisode, ...]:
    payload = json.loads(DEVELOPMENT_SEEDS.read_text(encoding="utf-8"))
    seeds = tuple(payload["ordered_seeds"])
    worlds = finite_world_library()
    selected = seeds if limit is None else seeds[:limit]
    return tuple(DevelopmentEpisode(f"development-{i:03d}", worlds[seed % len(worlds)]) for i, seed in enumerate(selected))
