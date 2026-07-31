from pathlib import Path
import os
import yaml

ROOT = Path(__file__).resolve().parents[3]

def load_contract(path=None):
    p = Path(path or os.environ.get("GARC_RUNTIME_MODELS_CONFIG", ROOT / "configs/runtime_models.yaml"))
    return yaml.safe_load(p.read_text())

def resolve_env_path(section, contract=None):
    section = section if isinstance(section, dict) else load_contract()["models"][section]
    key = section["local_path_env"]
    value = os.environ.get(key)
    return Path(value).expanduser() if value else None
