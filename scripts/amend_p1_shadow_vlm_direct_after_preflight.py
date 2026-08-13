#!/usr/bin/env python3
"""One infrastructure-only amendment after cross-family SmolVLM preflight failure."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/p1_shadow_vlm_direct_reference_v1"
MODEL = ROOT / "models/Qwen3-VL-32B-Instruct-FP8"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def tree_hash(path: Path) -> str:
    h = hashlib.sha256()
    for item in sorted(x for x in path.rglob("*") if x.is_file()):
        h.update(str(item.relative_to(path)).encode())
        h.update(str(item.stat().st_size).encode())
        if item.stat().st_size < 4_000_000:
            h.update(bytes.fromhex(sha(item)))
    return h.hexdigest()


def canonical_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def main() -> None:
    protocol_path = OUT / "SHADOW_PROTOCOL.json"
    protocol = json.loads(protocol_path.read_text())
    if protocol.get("amendment_id"):
        raise RuntimeError("shadow protocol already amended")
    archive = OUT / "FAILED_CROSS_FAMILY_PREFLIGHT"
    archive.mkdir(exist_ok=False)
    archived = {}
    for name in ("VLM_A_RAW.jsonl", "VLM_B_RAW.jsonl", "VLM_A_RUN.log", "VLM_B_RUN.log"):
        source = OUT / name
        if source.exists():
            archived[name] = {"rows": sum(1 for _ in source.open()) if source.suffix == ".jsonl" else None, "sha256": sha(source)}
            source.rename(archive / name)
    old_hash = protocol["protocol_hash"]
    old_b = protocol["annotators"]["VLM_B"]
    protocol["annotators"]["VLM_B"] = {
        "model": "Qwen/Qwen3-VL-32B-Instruct-FP8", "family": "Qwen3-VL",
        "path": str(MODEL), "identity_hash": tree_hash(MODEL),
    }
    protocol["independence"] = "distinct 8B and 32B checkpoints in isolated deterministic sessions; same Qwen3-VL family after cross-family judge failed feasibility preflight; VLM_B never reads VLM_A output"
    protocol["amendment_id"] = "SHADOW_INFRASTRUCTURE_AMENDMENT_1"
    protocol["amendment_reason"] = "SmolVLM2-500M exceeded its 8192-token context with the frozen multi-frame input and produced schema-invalid repetitive text in every completed preflight window; it cannot supply a usable temporal reference. No trace, pair, proxy, semantic-unit outcome, C1/K3, or geometry result had been opened. Both annotation streams restart from zero."
    protocol["amended_at_utc"] = datetime.now(timezone.utc).isoformat()
    protocol["prior_protocol_hash"] = old_hash
    protocol["prior_vlm_b"] = old_b
    protocol["failed_preflight_archive"] = archived
    protocol["protocol_hash"] = canonical_hash({k: v for k, v in protocol.items() if k not in {"created_at_utc", "amended_at_utc", "protocol_hash"}})
    protocol_path.write_text(json.dumps(protocol, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    state = json.loads((OUT / "SHADOW_STATE.json").read_text())
    state.update({"status": "AMENDED_PROTOCOL_FROZEN_RESTART_ZERO", "protocol_hash": protocol["protocol_hash"], "vlm_a_complete": False, "vlm_b_complete": False, "cross_family_preflight": "FAILED_INFRASTRUCTURE_SCHEMA_FEASIBILITY", "formal_p1_status": "WAITING_HUMAN_REFERENCE", "p2_authorized": False})
    (OUT / "SHADOW_STATE.json").write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    (OUT / "SHADOW_PROTOCOL_AMENDMENT.md").write_text(f"""# P1 shadow infrastructure amendment 1

The initial cross-family SmolVLM2-500M judge failed before analysis: its 15-frame input exceeded the model's 8192-token context and all completed responses were schema-invalid repetitive text. The partial A/B streams were archived and excluded; both annotators restart from zero.

VLM_B is replaced by the locally frozen Qwen3-VL-32B-FP8 checkpoint. VLM_A remains Qwen3-VL-8B. This sacrifices cross-family independence but preserves distinct checkpoints and isolated sessions. The windowing, prompt, queries, blinding, stitching, pseudo-adjudication and analysis contract are unchanged. No formal P1 file was written or modified.

- Prior protocol: `{old_hash}`
- Amended protocol: `{protocol['protocol_hash']}`
""")
    print(json.dumps({"status": "AMENDED_PROTOCOL_FROZEN_RESTART_ZERO", "protocol_hash": protocol["protocol_hash"], "vlm_b": protocol["annotators"]["VLM_B"]["model"]}, sort_keys=True))


if __name__ == "__main__":
    main()
