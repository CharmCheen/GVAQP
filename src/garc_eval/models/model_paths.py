"""Resolve model and data paths from environment variables or project defaults."""

import os
from pathlib import Path

_ENV_DEFAULTS = {
    "GARC_HOME": str(Path(__file__).resolve().parents[2]),
    "GARC_MODEL_DIR": str(Path(__file__).resolve().parents[2] / "models"),
    "GARC_DATA_DIR": str(Path(__file__).resolve().parents[2] / "data"),
    "GARC_OUTPUT_DIR": str(Path(__file__).resolve().parents[1] / "outputs"),
}


def get_env(key: str) -> str:
    """Get environment variable with project-level default."""
    return os.environ.get(key, _ENV_DEFAULTS[key])


def resolve_path(path_template: str) -> str:
    """Resolve a path that may contain ${ENV_VAR} references.

    Examples
    --------
    >>> resolve_path("${GARC_MODEL_DIR}/yolo/yolov8n.pt")
    "/abs/path/to/models/yolo/yolov8n.pt"
    """
    result = path_template
    for key, default in _ENV_DEFAULTS.items():
        value = os.environ.get(key, default)
        result = result.replace(f"${{{key}}}", value)
    return result


def check_path_exists(path: str, label: str = "Path") -> None:
    """Raise FileNotFoundError if path does not exist."""
    resolved = resolve_path(path)
    if not Path(resolved).exists():
        raise FileNotFoundError(f"{label} not found: {resolved} ({path})")
