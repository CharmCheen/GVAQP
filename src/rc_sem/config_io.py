from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

from .algorithm import RCSEMConfig
from .controller import ControllerConfig
from .materialization import MaterializationConfig
from .types import Action


SCHEMA_VERSION = "RC_SEM_CONFIG_V1"
TOP_LEVEL_KEYS = frozenset({"schema_version", "status", "materialization", "controller"})
MATERIALIZATION_KEYS = frozenset(MaterializationConfig.__dataclass_fields__)
CONTROLLER_KEYS = frozenset(ControllerConfig.__dataclass_fields__)


def config_to_dict(config: RCSEMConfig, *, status: str = "STAGING_NOT_CONFIRMATORY") -> dict[str, Any]:
    controller = asdict(config.controller)
    controller["fallback_action"] = config.controller.fallback_action.value
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "materialization": asdict(config.materialization),
        "controller": controller,
    }


def config_sha256(config: RCSEMConfig, *, status: str = "STAGING_NOT_CONFIRMATORY") -> str:
    encoded = json.dumps(
        config_to_dict(config, status=status),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_config(path: str | Path) -> tuple[RCSEMConfig, str]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping) or set(payload) != TOP_LEVEL_KEYS:
        raise ValueError("RC-SEM config top-level key mismatch")
    if payload["schema_version"] != SCHEMA_VERSION:
        raise ValueError("RC-SEM config schema version mismatch")
    materialization = payload["materialization"]
    controller = payload["controller"]
    if not isinstance(materialization, Mapping) or set(materialization) != MATERIALIZATION_KEYS:
        raise ValueError("RC-SEM materialization config key mismatch")
    if not isinstance(controller, Mapping) or set(controller) != CONTROLLER_KEYS:
        raise ValueError("RC-SEM controller config key mismatch")
    return (
        RCSEMConfig(
            materialization=MaterializationConfig(**materialization),
            controller=ControllerConfig(
                **{
                    **controller,
                    "fallback_action": Action(controller["fallback_action"]),
                }
            ),
        ),
        str(payload["status"]),
    )
