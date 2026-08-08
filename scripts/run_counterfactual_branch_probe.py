#!/usr/bin/env python3
"""Execute only frozen, isolated one-step exploratory branch actions."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from rc_sem.counterfactual_probe import LogicalSnapshot, canonical_sha256, public_actions
from rc_sem.exploratory_gate_o import event_groups
from rc_sem.exploratory_h0 import RuntimeAction

RUN = ROOT / "outputs/exploratory_temporal_order_guangzhou_v1/exploratory_20260808_8b_300s"
OUT = RUN / "counterfactual_probe_v1"
VIDEO = ROOT / "data/realcam/guangzhou.mp4"
MODEL = ROOT / "models/Qwen3-VL-8B-Instruct"
PROMPT = ROOT / "configs/prompts/confirm_visual.yaml"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def parse_label(raw: str) -> tuple[str, dict]:
    try:
        begin, end = raw.find("{"), raw.rfind("}")
        parsed = json.loads(raw[begin:end + 1]) if begin >= 0 and end >= begin else {}
        label = str(parsed.get("label", "abstain")).lower()
        return (label if label in {"positive", "negative", "abstain"} else "abstain"), parsed
    except (json.JSONDecodeError, TypeError):
        return "abstain", {"parse_error": True}


def unit_frames(unit_id: int, fps: float, *, sample_fps: float = 2.0) -> list[object]:
    import cv2
    import numpy as np
    start, end = unit_id * 10.0, min((unit_id + 1) * 10.0, 4238.25)
    indices = [int(round(second * fps)) for second in np.arange(start, end, 1.0 / sample_fps)]
    capture = cv2.VideoCapture(str(VIDEO)); images: list[np.ndarray] = []
    for wanted in indices:
        capture.set(cv2.CAP_PROP_POS_FRAMES, wanted)
        ok, frame = capture.read()
        if not ok:
            break
        images.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    capture.release()
    if not images:
        raise RuntimeError(f"cannot decode unit {unit_id}")
    return images


def scan_cell(cell_id: int, fps: float) -> dict:
    import cv2
    import numpy as np
    exposed = []
    for unit_id in range(cell_id * 10, min((cell_id + 1) * 10, 424)):
        frames = unit_frames(unit_id, fps, sample_fps=1.0)
        gray = [cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY) for frame in frames]
        differences = [float(cv2.absdiff(left, right).mean() / 255.0) for left, right in zip(gray, gray[1:])]
        score = float(np.mean(differences)) if differences else 0.0
        exposed.append({"unit_id": unit_id, "score": score, "frame_count": len(frames), "mean_frame_difference": score, "max_frame_difference": float(max(differences, default=0.0))})
    return {"exposed": exposed}


class Oracle:
    def __init__(self) -> None:
        import torch
        import yaml
        from qwen_vl_utils import process_vision_info
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
        self.torch, self.process_vision_info = torch, process_vision_info
        self.model = Qwen3VLForConditionalGeneration.from_pretrained(MODEL, dtype=torch.bfloat16, device_map="cuda:0", trust_remote_code=True, local_files_only=True)
        self.processor = AutoProcessor.from_pretrained(MODEL, trust_remote_code=True, local_files_only=True)
        self.model.eval(); torch.cuda.synchronize()
        self.prompt = yaml.safe_load(PROMPT.read_text(encoding="utf-8"))["text"]

    def verify(self, unit_id: int, fps: float) -> dict:
        from PIL import Image
        frames = unit_frames(unit_id, fps)
        started = time.perf_counter(); images = [Image.fromarray(frame) for frame in frames]
        messages = [{"role": "user", "content": [{"type": "video", "video": images, "fps": 2.0}, {"type": "text", "text": self.prompt}]}]
        text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs, video_kwargs = self.process_vision_info(messages, return_video_kwargs=True, return_video_metadata=True)
        tensors, metadata = [item[0] for item in video_inputs], [item[1] for item in video_inputs]
        inputs = self.processor(text=[text], images=image_inputs, videos=tensors, video_metadata=metadata, padding=True, return_tensors="pt", **video_kwargs).to(self.model.device)
        self.torch.cuda.synchronize(); inference_started = time.perf_counter()
        with self.torch.no_grad():
            generated = self.model.generate(**inputs, do_sample=False, max_new_tokens=256)
        self.torch.cuda.synchronize()
        raw = self.processor.batch_decode([output[len(source):] for source, output in zip(inputs.input_ids, generated)], skip_special_tokens=True)[0]
        label, parsed = parse_label(raw)
        return {"unit_id": unit_id, "label": label, "parsed": parsed, "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(), "frame_count": len(frames), "inference_seconds": time.perf_counter() - inference_started, "total_seconds": time.perf_counter() - started}


def snapshot(value: dict) -> LogicalSnapshot:
    raw = dict(value); raw["scan_order"] = tuple(raw["scan_order"]); raw["scanned_cells"] = tuple(raw["scanned_cells"])
    raw["exposed_candidates"] = tuple(raw["exposed_candidates"]); raw["attempted_verify_units"] = tuple(raw["attempted_verify_units"])
    raw["confirmed_positive_units"] = tuple(raw["confirmed_positive_units"]); raw["rejected_units"] = tuple(raw["rejected_units"]); raw["prior_cost_seconds"] = tuple(raw["prior_cost_seconds"])
    raw["parent_action"] = RuntimeAction(**raw["parent_action"])
    return LogicalSnapshot(**raw)


def verify_plan(plan: dict) -> None:
    for state in plan["states"]:
        restored = snapshot(state["state_snapshot"])
        if restored.sha256() != state["state_snapshot_sha256"]:
            raise RuntimeError(f"snapshot hash mismatch: {state['state_id']}")
        legal = [item.__dict__ for item in public_actions(restored)]
        if legal != state["legal_actions"]:
            raise RuntimeError(f"legal action mismatch: {state['state_id']}")
        legal_set = {(item["kind"], item["target"]) for item in legal}
        if not all((item["kind"], item["target"]) in legal_set for item in state["alternatives"]):
            raise RuntimeError(f"inadmissible planned action: {state['state_id']}")


def execute_branch(state: dict, action: dict, oracle: Oracle | None, fps: float) -> dict:
    restored = snapshot(state["state_snapshot"])
    before_events = event_groups(restored.confirmed_positive_units)
    runtime_action = RuntimeAction(**action)
    started = time.perf_counter()
    if runtime_action.kind == "SCAN":
        outcome = scan_cell(int(runtime_action.target), fps)
        after_events = before_events
    else:
        if oracle is None:
            raise RuntimeError("oracle unavailable for planned VERIFY")
        outcome = oracle.verify(int(runtime_action.target), fps)
        positives = set(restored.confirmed_positive_units)
        if outcome["label"] == "positive": positives.add(int(runtime_action.target))
        after_events = event_groups(positives)
    cost = time.perf_counter() - started
    completion = restored.elapsed_seconds + cost
    next_state = {
        "completed_scan_cells": sorted(set(restored.scanned_cells) | ({int(runtime_action.target)} if runtime_action.kind == "SCAN" else set())),
        "attempted_verify_units": sorted(set(restored.attempted_verify_units) | ({int(runtime_action.target)} if runtime_action.kind == "VERIFY" else set())),
        "event_relation": [list(group) for group in after_events],
    }
    return {
        "parent_state_id": state["state_id"], "parent_state_sha256": state["state_snapshot_sha256"],
        "parent_elapsed_seconds": restored.elapsed_seconds, "parent_remaining_seconds": 300.0 - restored.elapsed_seconds,
        "parent_b_action": state["parent_b_action"], "parent_b_transition": state["parent_b_transition"],
        "legal_actions": state["legal_actions"], "counterfactual_action": action,
        "action_admissible": True, "timestamp_semantics": "logical parent elapsed + measured isolated action physical cost",
        "physical_cost_seconds": cost, "completion_seconds": completion, "completed_by_logical_deadline": completion <= 300.0,
        "outcome": outcome, "event_relation_before": [list(group) for group in before_events], "event_relation_after": [list(group) for group in after_events],
        "event_relation_delta": len(after_events) - len(before_events), "next_logical_state": next_state,
        "branch_stopping_rule": "ONE_ACTION_THEN_STOP", "physical_runtime_convention": "NORMALIZED_MODEL_RESIDENT_SESSION",
    }


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--mode", choices=("dry-run", "execute"), required=True)
    args = parser.parse_args()
    contract = json.loads((OUT / "COUNTERFACTUAL_BRANCH_PROBE_CONTRACT.json").read_text())
    plan = json.loads((OUT / "COUNTERFACTUAL_BRANCH_PROBE_PLAN.json").read_text())
    if plan["contract_sha256"] != contract["contract_sha256"] or plan["parent_trace_sha256"] != sha256(RUN / "B_TEMPORAL_BISECTION_FIXED_SCAN1_VERIFY1.trace.json"):
        raise RuntimeError("frozen contract/parent trace mismatch")
    verify_plan(plan)
    if args.mode == "dry-run":
        print(json.dumps({"status": "DRY_RUN_PASS_NO_ORACLE_CALLS", "states": len(plan["states"]), "branches": plan["planned_branch_count"]}, indent=2)); return
    authorization = OUT / "EXECUTION_AUTHORIZATION.json"
    if not authorization.exists() or not json.loads(authorization.read_text()).get("execution_authorized"):
        raise RuntimeError("counterfactual branch execution is fail-closed pending separate authorization")
    if (OUT / "BRANCH_EXECUTION_INDEX.json").exists():
        raise RuntimeError("refusing to overwrite branch execution evidence")
    import cv2
    fps = float(cv2.VideoCapture(str(VIDEO)).get(cv2.CAP_PROP_FPS))
    needs_oracle = any(action["kind"] == "VERIFY" for state in plan["states"] for action in state["alternatives"])
    oracle = Oracle() if needs_oracle else None
    entries = []
    for state in plan["states"]:
        for action in state["alternatives"]:
            result = execute_branch(state, action, oracle, fps)
            path = OUT / "branches" / state["state_id"] / f"{action['kind']}_{action['target']}.json"
            atomic_json(path, result); entries.append({"path": str(path.relative_to(ROOT)), "sha256": sha256(path)})
    atomic_json(OUT / "BRANCH_EXECUTION_INDEX.json", {"contract_sha256": contract["contract_sha256"], "plan_sha256": plan["plan_sha256"], "execution_mode": "FROZEN_ONE_STEP_BRANCHES", "entries": entries, "full_policy_rerun": False, "mab_implemented": False})
    print(json.dumps({"status": "BRANCH_EXECUTION_COMPLETE", "branches": len(entries)}, indent=2))


if __name__ == "__main__":
    main()
