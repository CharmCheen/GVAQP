from pathlib import Path
import hashlib
import yaml

ROOT = Path(__file__).resolve().parents[3]

def load_confirm_prompt(path=None):
    p = Path(path or ROOT / "configs/prompts/confirm_visual.yaml")
    data = yaml.safe_load(p.read_text())
    text = data["text"]
    digest = hashlib.sha256(text.encode()).hexdigest()
    if digest != data["sha256"]:
        raise ValueError(f"confirm prompt hash mismatch: {digest}")
    return text
