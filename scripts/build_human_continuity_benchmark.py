#!/usr/bin/env python3
"""Build a blinded, frozen human event-continuity sanity benchmark.

This builder is intentionally separated from analysis.  It writes no human
label and the public annotation package never contains method predictions,
model-relative labels, event IDs, selector data, P0 metrics, or strata.

Actions:
  freeze  -- construct population, deterministic primary/reserve samples,
             protocol, public package, and zero-label state.
  clips   -- render blinded context clips after the freeze.
  verify  -- validate clip decoding, markers, ordering, and public leakage.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from garc_eval.accelerated_event_query.k3_unit_event_adapter import K3UnitEventAdapter, K3UnitEventConfig  # noqa: E402
from garc_eval.accelerated_event_query.model_relative_labels import ModelRelativeUnitLabel  # noqa: E402

OUT = ROOT / "outputs/human_continuity_validation_v1"
V10 = ROOT / "outputs/v10_multiseal_reference_v1"
P0 = ROOT / "outputs/p0_materializer_validation_v3"
MECH = ROOT / "outputs/p0_materializer_mechanism_ablation_v1"
UNIT_MANIFEST = ROOT / "outputs/accelerated_event_query_v1/oracle_protocol_v3_model_relative/full_grid_preregistration_staged_v7_review_corrections/FULL_GRID_UNIT_MANIFEST.json"
VIDEO_MANIFEST = ROOT / "outputs/accelerated_event_query_v1/video_manifests/frozen_videos_v1.json"
PROMPT = ROOT / "outputs/accelerated_event_query_v1/oracle_protocol_v3_model_relative/configs/query_prompt_v3_model_relative.txt"
K3_CONFIG = ROOT / "outputs/accelerated_event_query_v1/oracle_protocol_v3_model_relative/k3_eventization/K3_UNIT_EVENT_CONFIG_V3.json"
MECH_SOURCE = ROOT / "scripts/analyze_p0_v3_materializer_mechanisms.py"
QUERY_ID = "Q_DRIVER_RESPONSE_V1"
VIDEOS = ("DALI", "HANGZHOU", "WUHAN")
PRIMARY_N = 40
RESERVE_N = 20
SEED = 20260811
CONTEXT_PRE_SEC = 4.0
CONTEXT_POST_SEC = 4.0
NORMAL_FPS = 5
LONG_CONTEXT_FPS = 1
MAX_NORMAL_CONTEXT_SEC = 75.0
ANCHOR_DETAIL_PRE_SEC = 4.0
ANCHOR_DETAIL_POST_SEC = 4.0
TEMPORAL_DIVERSITY_SEC = 120.0
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def chash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def write_json_once(path: Path, value: Any) -> None:
    text = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise RuntimeError(f"immutable artifact mismatch: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_text_once(path: Path, text: str) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise RuntimeError(f"immutable artifact mismatch: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_csv_once(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    import io
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="raise")
    writer.writeheader(); writer.writerows(rows)
    text = buf.getvalue()
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise RuntimeError(f"immutable artifact mismatch: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_parquet_once(path: Path, data: pd.DataFrame) -> None:
    if path.exists():
        # Compare encoded values, not Parquet writer metadata.
        old = pd.read_parquet(path)
        if list(old.columns) != list(data.columns) or not old.equals(data):
            raise RuntimeError(f"immutable population mismatch: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    data.to_parquet(path, index=False, compression="zstd")


def exact_human_query() -> str:
    """Use only verbatim predicate paragraphs; omit VLM output/operator instructions."""
    text = PROMPT.read_text(encoding="utf-8").strip()
    start = text.index("Inspect this 10-second ego-driving unit")
    cut = text.index("Return unknown rather than guessing")
    predicate = text[start:cut].strip()
    if "K3" in predicate or "model-relative" in predicate:
        raise RuntimeError("human query extraction leaked non-predicate operator text")
    return predicate


def source_artifacts() -> dict[str, Any]:
    ref = read_json(V10 / "REFERENCE_MANIFEST.json")
    if not ref.get("complete") or ref.get("expected_units") != 1475 or ref.get("cross_seal_compatibility") not in {"PASS", "QUALIFIED_PASS"}:
        raise RuntimeError("requires complete compatible V10 reference")
    p0 = read_json(P0 / "EXPERIMENT_PROTOCOL.json")
    if p0.get("protocol_id") != "P0_V3_SELECTOR_X_MATERIALIZER_CONTROLLED_REPLAY_V3":
        raise RuntimeError("requires authoritative P0 V3 protocol")
    if not (MECH / "MECHANISM_PROTOCOL.json").exists():
        raise RuntimeError("requires frozen C1 mechanism-ablation definition")
    paths = [V10 / "FINAL_UNIT_REFERENCE.parquet", V10 / "K3_MODEL_RELATIVE_EVENT_RELATION.parquet", V10 / "REFERENCE_MANIFEST.json", P0 / "EXPERIMENT_PROTOCOL.json", MECH / "MECHANISM_PROTOCOL.json", UNIT_MANIFEST, VIDEO_MANIFEST, PROMPT, K3_CONFIG, MECH_SOURCE, Path(__file__)]
    return {str(p.relative_to(ROOT)): sha(p) for p in paths}


def labels_and_events() -> tuple[pd.DataFrame, dict[str, str]]:
    units = pd.read_parquet(V10 / "FINAL_UNIT_REFERENCE.parquet").sort_values(["video_id", "start_time", "end_time", "unit_id"]).reset_index(drop=True)
    expected = {"unit_id", "video_id", "start_time", "end_time", "authoritative_label"}
    if not expected.issubset(units.columns) or len(units) != 1475:
        raise RuntimeError("unexpected frozen unit-reference schema/count")
    event = pd.read_parquet(V10 / "K3_MODEL_RELATIVE_EVENT_RELATION.parquet")
    mapping: dict[str, str] = {}
    for row in event.to_dict(orient="records"):
        for unit_id in row["source_unit_ids"]:
            if unit_id in mapping:
                raise RuntimeError(f"unit belongs to duplicate reference events: {unit_id}")
            mapping[unit_id] = row["event_id"]
    positive = units[units.authoritative_label.eq("relevant")]
    if set(positive.unit_id) - set(mapping):
        raise RuntimeError("a positive full-grid unit has no K3 reference event")
    return units, mapping


def k3_same_for_pair(anchor_a: str, anchor_b: str, mapping: dict[str, str]) -> int:
    return int(mapping[anchor_a] == mapping[anchor_b])


def c1_same_for_pair(a_end: float, b_start: float) -> int:
    # Exact existing Stage-0 C1 lineage mapped to V3 units: no gap/threshold re-selection.
    return int(max(0.0, b_start - a_end) <= 10.0)


def pair_population() -> pd.DataFrame:
    units, event_map = labels_and_events()
    rows: list[dict[str, Any]] = []
    for video in VIDEOS:
        all_units = units[units.video_id.eq(video)].sort_values(["start_time", "end_time", "unit_id"])
        positive = all_units[all_units.authoritative_label.eq("relevant")].to_dict(orient="records")
        for ordinal, (a, b) in enumerate(zip(positive, positive[1:])):
            between = all_units[(all_units.start_time >= float(a["end_time"])) & (all_units.end_time <= float(b["start_time"])) & (all_units.end_time > float(a["end_time"])) & (all_units.start_time < float(b["start_time"]))]
            counts = Counter(between.authoritative_label.tolist())
            c0, c1, k3 = 1, c1_same_for_pair(float(a["end_time"]), float(b["start_time"])), k3_same_for_pair(a["unit_id"], b["unit_id"], event_map)
            pattern = f"{c0}{c1}{k3}"
            # Fixed opaque ID derived only from source temporal identity, then public case aliases are random.
            hidden_id = "CP_" + chash({"video": video, "a": a["unit_id"], "b": b["unit_id"]})[:16]
            rows.append({
                "case_id": hidden_id, "pair_ordinal_within_video": ordinal, "video_id": video, "query_id": QUERY_ID,
                "anchor_a_unit_id": a["unit_id"], "anchor_b_unit_id": b["unit_id"],
                "anchor_a_start": float(a["start_time"]), "anchor_a_end": float(a["end_time"]),
                "anchor_b_start": float(b["start_time"]), "anchor_b_end": float(b["end_time"]),
                "temporal_gap_sec": max(0.0, float(b["start_time"]) - float(a["end_time"])),
                "intervening_unit_ids": list(between.unit_id), "intervening_positive_count": int(counts["relevant"]),
                "intervening_negative_count": int(counts["not_relevant"]), "intervening_unknown_count": int(counts["unknown"]),
                "intervening_parse_failure_count": int(counts["parse_failure"]),
                "C0_same_event": c0, "C1_same_event": c1, "K3_same_event": k3, "prediction_pattern": pattern,
            })
    frame = pd.DataFrame(rows).sort_values(["video_id", "anchor_a_start", "anchor_b_start", "case_id"]).reset_index(drop=True)
    if len(frame) != 248:
        raise RuntimeError(f"expected 248 consecutive-positive pairs, got {len(frame)}")
    return frame


def category(row: dict[str, Any]) -> str:
    if int(row["C0_same_event"]) != int(row["C1_same_event"]):
        return "C0_C1_DISAGREE"
    if int(row["C1_same_event"]) != int(row["K3_same_event"]):
        return "C1_K3_DISAGREE"
    return "AGREEMENT_CONTROL"


def rank_key(case: dict[str, Any], salt: str) -> str:
    return chash({"seed": SEED, "salt": salt, "case_id": case["case_id"]})


def choose_with_diversity(candidates: list[dict[str, Any]], n: int, chosen_for_video: list[dict[str, Any]], salt: str) -> list[dict[str, Any]]:
    """Outcome-blind structural sampling with a fixed temporal separation if feasible."""
    ordered = sorted(candidates, key=lambda x: (rank_key(x, salt), x["case_id"]))
    picked: list[dict[str, Any]] = []
    def distant(row: dict[str, Any]) -> bool:
        return all(abs(float(row["anchor_a_start"]) - float(old["anchor_a_start"])) >= TEMPORAL_DIVERSITY_SEC for old in chosen_for_video + picked)
    for row in ordered:
        if len(picked) == n: break
        if distant(row): picked.append(row)
    if len(picked) < n:
        for row in ordered:
            if len(picked) == n: break
            if row not in picked: picked.append(row)
    return picked


def sample_per_video(population: pd.DataFrame, total: int, phase: str, excluded: set[str]) -> list[dict[str, Any]]:
    # 13/13/14 (and 7/7/6 reserve) guarantees source coverage while targets
    # maximize diagnostic strata without reading human judgments.
    if total == PRIMARY_N:
        video_quota = {"DALI": 13, "HANGZHOU": 13, "WUHAN": 14}
        desired = {"C0_C1_DISAGREE": [5, 5, 6], "C1_K3_DISAGREE": [3, 3, 2], "AGREEMENT_CONTROL": [5, 5, 6]}
    else:
        # The locked reserve is deliberately source-balanced 7/7/6 rather
        # than relying on a generic integer division of its 20-case total.
        video_quota = {"DALI": 7, "HANGZHOU": 7, "WUHAN": 6}
        desired = {"C0_C1_DISAGREE": [3, 3, 3], "C1_K3_DISAGREE": [1, 1, 1], "AGREEMENT_CONTROL": [3, 3, 2]}
    source_rows = [r for r in population.to_dict(orient="records") if r["case_id"] not in excluded]
    picked: list[dict[str, Any]] = []
    for video_index, video in enumerate(VIDEOS):
        already: list[dict[str, Any]] = []
        avail = [dict(r, sampling_category=category(r)) for r in source_rows if r["video_id"] == video]
        for cat in ("C1_K3_DISAGREE", "C0_C1_DISAGREE", "AGREEMENT_CONTROL"):
            target = desired[cat][video_index]
            options = [r for r in avail if r["sampling_category"] == cat and r not in already]
            take = choose_with_diversity(options, min(target, len(options)), already, f"{phase}:{video}:{cat}")
            already.extend(take)
        if len(already) < video_quota[video]:
            # Predetermined deficit priority: disagreement before controls, then hash order.
            priority = {"C1_K3_DISAGREE": 0, "C0_C1_DISAGREE": 1, "AGREEMENT_CONTROL": 2}
            leftovers = [r for r in avail if r not in already]
            leftovers.sort(key=lambda r: (priority[r["sampling_category"]], rank_key(r, f"{phase}:{video}:fill"), r["case_id"]))
            already.extend(choose_with_diversity(leftovers, video_quota[video] - len(already), already, f"{phase}:{video}:fill"))
        if len(already) != video_quota[video]:
            raise RuntimeError(f"insufficient population for {video} {phase}: {len(already)}/{video_quota[video]}")
        picked.extend(already)
    if len(picked) != total or len({r["case_id"] for r in picked}) != total:
        raise RuntimeError("sampling did not produce a unique fixed-size set")
    return picked


def annotate_sampling(population: pd.DataFrame, primary: list[dict[str, Any]], reserve: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    all_rows = [dict(r, sampling_category=category(r)) for r in population.to_dict(orient="records")]
    size = Counter((r["video_id"], r["prediction_pattern"]) for r in all_rows)
    primary_count = Counter((r["video_id"], r["prediction_pattern"]) for r in primary)
    reserve_count = Counter((r["video_id"], r["prediction_pattern"]) for r in reserve)
    def decorate(rows: list[dict[str, Any]], which: str, counts: Counter) -> list[dict[str, Any]]:
        decorated=[]
        for r in rows:
            key=(r["video_id"],r["prediction_pattern"]); n=size[key]; selected=counts[key]
            decorated.append({**r, "sampling_set": which, "sampling_stratum": f"{r['video_id']}|{r['prediction_pattern']}", "population_stratum_size": n, "sampled_stratum_size": selected, "inclusion_probability": selected/n, "analysis_weight": n/selected})
        return decorated
    return decorate(primary, "PRIMARY", primary_count), decorate(reserve, "RESERVE_LOCKED", reserve_count)


def public_case(row: dict[str, Any], public_case_id: str, video_paths: dict[str, Path]) -> dict[str, Any]:
    start = max(0.0, float(row["anchor_a_start"]) - CONTEXT_PRE_SEC)
    end = float(row["anchor_b_end"]) + CONTEXT_POST_SEC
    span = end - start
    long = span > MAX_NORMAL_CONTEXT_SEC
    clips = [{"kind": "full_context", "path": f"clips/{public_case_id}_context.mp4", "fps": LONG_CONTEXT_FPS if long else NORMAL_FPS, "start_sec": start, "end_sec": end}]
    if long:
        for tag, anchor in (("anchor_a", "a"), ("anchor_b", "b")):
            a_start = max(0.0, float(row[f"anchor_{anchor}_start"]) - ANCHOR_DETAIL_PRE_SEC)
            a_end = float(row[f"anchor_{anchor}_end"]) + ANCHOR_DETAIL_POST_SEC
            clips.append({"kind": f"{tag}_detail", "path": f"clips/{public_case_id}_{tag}.mp4", "fps": NORMAL_FPS, "start_sec": a_start, "end_sec": a_end})
    return {"case_id": public_case_id, "query_id": QUERY_ID, "query_text": exact_human_query(), "clips": clips,
            "display": {"long_context": long, "instruction": "Watch the full context; for long contexts, use the A/B detail clips if needed."}}


def protocol_and_files(population: pd.DataFrame, primary: list[dict[str, Any]], reserve: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    video_manifest = read_json(VIDEO_MANIFEST)
    video_paths={x["video_id"]: ROOT / x["path"] for x in video_manifest["videos"]}
    if any(not p.is_file() for p in video_paths.values()): raise RuntimeError("a frozen source video is missing")
    # Deterministic public aliases and blinded randomized order: no source/pattern ordering.
    primary_order=sorted(primary,key=lambda r:(rank_key(r,"public-primary-order"),r["case_id"]))
    reserve_order=sorted(reserve,key=lambda r:(rank_key(r,"public-reserve-order"),r["case_id"]))
    public_primary=[]; public_reserve=[]
    for n,row in enumerate(primary_order,1): public_primary.append(public_case(row,f"CASE_{n:04d}",video_paths))
    for n,row in enumerate(reserve_order,1): public_reserve.append(public_case(row,f"RESERVE_{n:04d}",video_paths))
    # Store mapping only in the hidden manifests; public package has no prediction/method fields.
    primary_hidden=[]
    for public,row in zip(public_primary,primary_order): primary_hidden.append({**row,"public_case_id":public["case_id"],"public_order":len(primary_hidden)+1})
    reserve_hidden=[]
    for public,row in zip(public_reserve,reserve_order): reserve_hidden.append({**row,"public_case_id":public["case_id"],"public_order":len(reserve_hidden)+1})
    sources=source_artifacts()
    base={
        "protocol_id":"HUMAN_CONTINUITY_VALIDATION_V1", "protocol_type":"POST_P0_INDEPENDENT_HUMAN_VALIDATION", "created_at_utc":datetime.now(timezone.utc).isoformat(),
        "existing_model_relative_P0_results_observed":True, "human_continuity_labels_observed":False, "human_benchmark_tuned_using_labels":False,
        "video_ids":list(VIDEOS), "query_id":QUERY_ID, "query_text_source":{"path":str(PROMPT.relative_to(ROOT)),"sha256":sha(PROMPT)},
        "population":{"definition":"all consecutive full-grid verified-positive anchor pairs within video/query", "size":len(population), "hash":chash(population.to_dict(orient="records"))},
        "methods":{"C0":"P0 V3 naive global-positive baseline; same for every pair in one video", "C1":"existing frozen Stage-0 C1 gap-limited rule: merge only if gap <= 10 seconds", "K3":"current frozen V3 K3; no parameters changed"},
        "sampling":{"type":"FROZEN_STRATIFIED_DIAGNOSTIC_SAMPLING", "seed":SEED, "primary_size":PRIMARY_N, "reserve_size":RESERVE_N, "video_quota_primary":{"DALI":13,"HANGZHOU":13,"WUHAN":14}, "temporal_diversity_seconds":TEMPORAL_DIVERSITY_SEC, "category_order":["C1_K3_DISAGREE","C0_C1_DISAGREE","AGREEMENT_CONTROL"], "primary_sample_hash":chash(primary_hidden), "reserve_sample_hash":chash(reserve_hidden)},
        "clip_contract":{"context_pre_sec":CONTEXT_PRE_SEC,"context_post_sec":CONTEXT_POST_SEC,"max_normal_context_sec":MAX_NORMAL_CONTEXT_SEC,"normal_fps":NORMAL_FPS,"long_context_fps":LONG_CONTEXT_FPS,"long_pair_strategy":"full intervening interval retained at low fps plus normal-fps A/B detail clips","source_video_manifest":{"path":str(VIDEO_MANIFEST.relative_to(ROOT)),"sha256":sha(VIDEO_MANIFEST)}},
        "responses":["SAME_EVENT","DIFFERENT_EVENTS","ANCHOR_INVALID","UNCERTAIN"],
        "analysis_contract":{"eligible_labels":["SAME_EVENT","DIFFERENT_EVENTS"],"primary":"paired human continuity accuracy C1-C0","secondary":"K3-C1; boundary precision/recall/F1; raw and population-weighted descriptive estimates; paired bootstrap CI","reserve_unlock":"only if predefined primary result is INCONCLUSIVE_PRIMARY"},
        "source_artifacts":sources, "source_commit":git("rev-parse","HEAD"), "dirty_worktree":git("status","--short").splitlines(),
        "builder":{"path":str(Path(__file__).relative_to(ROOT)),"sha256":sha(Path(__file__))},
    }
    base["protocol_hash"]=chash({k:v for k,v in base.items() if k not in {"created_at_utc","protocol_hash"}})
    return base, primary_hidden, reserve_hidden


def preregistration_text(protocol: dict[str, Any]) -> str:
    return f"""# Human Event-Continuity Preregistration

Protocol: `{protocol['protocol_hash']}`

This is a **POST-P0 INDEPENDENT HUMAN VALIDATION**, not a pre-P0 preregistration. Existing model-relative P0 results have been observed; human continuity labels observed before this freeze: **NO**; benchmark tuned using human labels: **NO**.

The population is every consecutive pair of frozen full-grid VLM-positive anchors within DALI, HANGZHOU, and WUHAN. The hidden table records C0/C1/K3 predictions only for sampling/analysis. Human participants receive no reference events, method IDs/predictions, selector identity, F1, or P0 results.

The fixed primary workload is `{PRIMARY_N}` blinded cases and the fixed reserve is `{RESERVE_N}` cases. The reserve is locked unless the primary result meets the predeclared `INCONCLUSIVE_PRIMARY` condition. Sampling is seeded `{SEED}`, stratified by actual prediction pattern and source video, and records inclusion probabilities/weights. The clip rule retains the full intervening interval; long intervals use low-FPS full context plus A/B detail clips rather than deleting the middle.

No materializer parameter, selector, VLM label, reference event, or query wording may be changed. The primary contrast is C1−C0 human continuity accuracy; K3−C1 is secondary. `ANCHOR_INVALID` and `UNCERTAIN` are reported separately and are not coerced into a split label.
"""


def amend_analysis_contract() -> None:
    """Freeze a pre-label clarification of analysis/Reserve rules.

    R1 correctly froze semantics, population and samples, but used the phrase
    "predefined INCONCLUSIVE_PRIMARY" without operational precision.  This
    R2 amendment is allowed only at zero human labels and changes neither a
    semantic input nor a sampled case.
    """
    labels=OUT/"HUMAN_LABELS_PRIMARY.jsonl"
    if not labels.exists() or labels.read_text(encoding="utf-8").strip():
        raise RuntimeError("analysis amendment is only legal before any human label")
    r1=read_json(OUT/"HUMAN_CONTINUITY_PROTOCOL.json")
    primary=OUT/"PRIMARY_SAMPLE_MANIFEST.csv"; reserve=OUT/"RESERVE_SAMPLE_MANIFEST.csv"
    rules={
        "analysis_seed": 20260811,
        "paired_bootstrap_resamples": 10000,
        "continuity_eligible_labels": ["SAME_EVENT", "DIFFERENT_EVENTS"],
        "inconclusive_primary_if_any": [
            "eligible_primary_cases < 28",
            "eligible_C0_C1_disagreement_cases < 8",
            "paired_bootstrap_95pct_CI_width_for_C1_minus_C0_accuracy > 0.40",
        ],
        "human_supports_gap_only_if_all": [
            "not INCONCLUSIVE_PRIMARY",
            "C1_minus_C0_raw_accuracy >= 0.10",
            "C1_minus_C0_direction_is_positive_in_at_least_two_videos_with_at_least_five_eligible_cases",
            "K3_minus_C1_raw_accuracy < 0.10",
        ],
        "human_supports_full_K3_if_all": [
            "not INCONCLUSIVE_PRIMARY",
            "K3_minus_C1_raw_accuracy >= 0.10",
            "K3_minus_C1_direction_is_positive_in_at_least_two_videos_with_at_least_five_eligible_cases",
        ],
        "no_human_support_if": "not INCONCLUSIVE_PRIMARY and C1_minus_C0_raw_accuracy < 0.10 and K3_minus_C1_raw_accuracy < 0.10",
        "reserve_unlock": "only if INCONCLUSIVE_PRIMARY under these frozen rules; reserve sample is already locked",
    }
    amendment={
        "amendment_id": "HUMAN_CONTINUITY_ANALYSIS_R2_PRELABEL_CLARIFICATION",
        "protocol_type": "POST_P0_INDEPENDENT_HUMAN_VALIDATION_PRELABEL_AMENDMENT",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "amends_protocol_hash": r1["protocol_hash"],
        "reason": "Clarify reserve-unlock and decision rules before the first human label; no semantic, sampling, video, query, or clip-contract change.",
        "human_labels_observed_before_amendment": 0,
        "semantic_contract_changed": False,
        "population_changed": False,
        "primary_sample_changed": False,
        "reserve_sample_changed": False,
        "clip_contract_changed": False,
        "primary_manifest_sha256": sha(primary),
        "reserve_manifest_sha256": sha(reserve),
        "analysis_contract": rules,
    }
    amendment["amendment_hash"]=chash({k:v for k,v in amendment.items() if k not in {"created_at_utc","amendment_hash"}})
    write_json_once(OUT/"HUMAN_CONTINUITY_PROTOCOL_AMENDMENT_R2.json",amendment)
    write_text_once(OUT/"PROTOCOL_AMENDMENT_R2.md",f"""# Pre-label Analysis Clarification (R2)

Active amendment: `{amendment['amendment_hash']}`\n\nAmends R1 protocol: `{r1['protocol_hash']}`.  This was created while `HUMAN_LABELS_PRIMARY.jsonl` was empty. It does **not** change population, primary or reserve cases, source videos, query, VLM unit labels, C0/C1/K3 definitions, or clips. It only fixes the predeclared analysis seed, bootstrap count, decision thresholds, and the objective reserve-unlock condition.\n\nReserve may be unlocked only if the frozen R2 `INCONCLUSIVE_PRIMARY` condition is met.\n""")
    state=read_json(OUT/"HUMAN_CONTINUITY_STATE.json")
    state.update({"active_analysis_amendment_hash":amendment["amendment_hash"],"human_labels_observed":0})
    (OUT/"HUMAN_CONTINUITY_STATE.json").write_text(json.dumps(state,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"status":"ANALYSIS_CONTRACT_R2_FROZEN","amendment_hash":amendment["amendment_hash"]},sort_keys=True))


def guide_text() -> str:
    return f"""# Annotation Guide: Human Event Continuity

You will see a driving-video context with two neutral temporal markers, **A** and **B**, and the frozen query below. You will not see any model result or method output.

## Frozen query

{exact_human_query()}

## Choose exactly one answer

- **SAME_EVENT** — both marked moments satisfy the query and are part of one continuing semantic episode. A short occlusion, observation gap, or change in intensity can still be one event.
- **DIFFERENT_EVENTS** — both marked moments satisfy the query, but the first episode has clearly ended and B belongs to a new independent episode.
- **ANCHOR_INVALID** — at least one marked anchor does not itself satisfy the query.
- **UNCERTAIN** — the video/context is insufficient for a reliable continuity judgment.

Temporal closeness does not automatically mean SAME_EVENT, and temporal separation does not automatically mean DIFFERENT_EVENTS. Use the visible driving semantics, including the intervening interval. Do not infer hidden motion or events outside the shown video.

An optional comment is available but not required. Your answers are saved immediately. You may go back and revise prior answers until all 40 cases are complete; after the primary set is frozen, corrections require a separately documented revision.
"""


def public_html() -> str:
    return """<!doctype html><html><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>Human Event Continuity</title><style>body{font-family:system-ui,sans-serif;max-width:950px;margin:22px auto;padding:0 14px;color:#18212b}video{width:100%;max-height:530px;background:#111;margin:8px 0}.panel{background:#f4f7fb;padding:14px;border-radius:8px;white-space:pre-wrap}.choices{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:16px 0}button{font-size:18px;padding:16px;border-radius:8px;border:1px solid #8ba0b5;background:white;cursor:pointer}button:hover{background:#e8f2ff}#note{width:100%;min-height:58px}small{color:#51606e}.hidden{display:none}</style></head><body><h1>Event-continuity annotation</h1><div id=\"progress\"></div><div class=\"panel\" id=\"query\"></div><div id=\"videos\"></div><p><b>Question:</b> Considering A, the intervening video, and B, what is the best judgment?</p><div class=\"choices\"><button data-label=\"SAME_EVENT\">1 — SAME EVENT</button><button data-label=\"DIFFERENT_EVENTS\">2 — DIFFERENT EVENTS</button><button data-label=\"ANCHOR_INVALID\">3 — ANCHOR INVALID</button><button data-label=\"UNCERTAIN\">4 — UNCERTAIN</button></div><label>Optional comment (not required)<textarea id=\"note\"></textarea></label><p><button id=\"prev\">← Previous</button> <button id=\"next\">Next →</button> <small>Keyboard: 1/2/3/4 label; left/right navigate.</small></p><p id=\"status\"></p><script src=\"app.js\"></script></body></html>"""


def public_js() -> str:
    return """let data,state,index=0; const labels=['SAME_EVENT','DIFFERENT_EVENTS','ANCHOR_INVALID','UNCERTAIN'];
async function load(){data=await (await fetch('/api/cases')).json();state=await (await fetch('/api/state')).json(); index=Math.min(state.first_unlabeled_index||0,data.cases.length-1); render();}
function esc(s){return s.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
function render(){const c=data.cases[index], old=state.latest[c.case_id]||{};document.querySelector('#progress').textContent=`Case ${index+1} / ${data.cases.length} — completed ${state.completed} / ${data.cases.length}`;document.querySelector('#query').textContent='Frozen query:\n'+c.query_text;document.querySelector('#videos').innerHTML=c.clips.map(x=>`<h3>${x.kind==='full_context'?'Full context':x.kind==='anchor_a_detail'?'Anchor A detail':'Anchor B detail'}</h3><video controls preload=\"metadata\" src=\"${esc(x.path)}\"></video>`).join('');document.querySelector('#note').value=old.optional_comment||'';document.querySelector('#status').textContent=old.label?`Current saved answer: ${old.label}`:'No answer saved for this case.';}
async function save(label){const c=data.cases[index];let r=await fetch('/api/label',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({case_id:c.case_id,label,optional_comment:document.querySelector('#note').value,annotation_session_id:state.session_id})});let x=await r.json();if(!r.ok){alert(x.error||'Save failed');return;}state=await (await fetch('/api/state')).json();document.querySelector('#status').textContent=`Saved: ${label}.`;render();}
document.querySelectorAll('[data-label]').forEach(x=>x.onclick=()=>save(x.dataset.label));document.querySelector('#prev').onclick=()=>{if(index>0){index--;render();}};document.querySelector('#next').onclick=()=>{if(index<data.cases.length-1){index++;render();}};window.onkeydown=e=>{if('1234'.includes(e.key))save(labels[+e.key-1]); if(e.key==='ArrowLeft'&&index>0){index--;render()} if(e.key==='ArrowRight'&&index<data.cases.length-1){index++;render()}};load();"""


def freeze() -> None:
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError(f"refusing to overwrite existing benchmark directory: {OUT}")
    population=pair_population()
    primary0=sample_per_video(population,PRIMARY_N,"PRIMARY",set())
    reserve0=sample_per_video(population,RESERVE_N,"RESERVE",{r["case_id"] for r in primary0})
    primary,reserve=annotate_sampling(population,primary0,reserve0)
    protocol,primary_hidden,reserve_hidden=protocol_and_files(population,primary,reserve)
    OUT.mkdir(parents=True)
    write_parquet_once(OUT / "CONTINUITY_POPULATION.parquet",population)
    write_json_once(OUT / "HUMAN_CONTINUITY_PROTOCOL.json",protocol)
    write_text_once(OUT / "HUMAN_CONTINUITY_PREREGISTRATION.md",preregistration_text(protocol))
    write_text_once(OUT / "ANNOTATION_GUIDE.md",guide_text())
    write_text_once(OUT / "HUMAN_QUERY_TEXT.txt",exact_human_query()+"\n")
    fields=list(primary_hidden[0])
    write_csv_once(OUT / "PRIMARY_SAMPLE_MANIFEST.csv",primary_hidden,fields)
    write_csv_once(OUT / "RESERVE_SAMPLE_MANIFEST.csv",reserve_hidden,fields)
    public_dir=OUT/"annotation_package"; (public_dir/"clips").mkdir(parents=True)
    public_primary=[{"case_id":r["public_case_id"],"query_id":QUERY_ID,"query_text":exact_human_query(),"clips":public_case(r,r["public_case_id"],{})["clips"],"display":public_case(r,r["public_case_id"],{})["display"]} for r in primary_hidden]
    # Do not write reserve case metadata into the public package while locked.
    write_json_once(public_dir/"PRIMARY_BLINDED_CASES.json",{"status":"PRIMARY_BLINDED","case_count":len(public_primary),"cases":public_primary})
    write_text_once(public_dir/"index.html",public_html()); write_text_once(public_dir/"app.js",public_js())
    (OUT/"HUMAN_LABELS_PRIMARY.jsonl").write_text("",encoding="utf-8")
    state={"status":"PROTOCOL_FROZEN","protocol_hash":protocol["protocol_hash"],"primary_cases":PRIMARY_N,"reserve_cases":RESERVE_N,"human_labels_observed":0,"analysis_performed":False,"package_verified":False}
    write_json_once(OUT/"HUMAN_CONTINUITY_STATE.json",state)
    patterns=population.prediction_pattern.value_counts().sort_index().to_dict()
    pervideo=population.groupby("video_id").size().to_dict()
    disagreements={"C0_C1":int((population.C0_same_event!=population.C1_same_event).sum()),"C1_K3":int((population.C1_same_event!=population.K3_same_event).sum()),"all_agree":int(((population.C0_same_event==population.C1_same_event)&(population.C1_same_event==population.K3_same_event)).sum())}
    summary=f"""# Continuity Population Summary

Population definition: every consecutive pair of full-grid `relevant` VLM unit anchors within the same video/query. This is a hidden analysis population; it is never provided to the annotator.

- Total instances: `{len(population)}`.
- Per video: `{pervideo}`.
- Prediction patterns `(C0,C1,K3)`: `{patterns}`.
- C0/C1 disagreements: `{disagreements['C0_C1']}`.
- C1/K3 disagreements: `{disagreements['C1_K3']}`.
- All-method agreements: `{disagreements['all_agree']}`.
- Frozen primary/reserve sizes: `{PRIMARY_N}/{RESERVE_N}`.

The counts are structural/model-prediction metadata only. No human label existed when this population and samples were frozen.
"""
    write_text_once(OUT/"CONTINUITY_POPULATION_SUMMARY.md",summary)
    audit=f"""# Sampling Audit

Protocol: `{protocol['protocol_hash']}`. Seed: `{SEED}`.

Primary is source-balanced 13/13/14 across DALI/HANGZHOU/WUHAN, with predeclared per-video targets favoring C0/C1 disagreement, then C1/K3 disagreement, then agreement controls. Shortfalls are deterministically filled by the same predeclared priority. Reserve is selected from the remaining population only and remains locked.

Sampling uses only video/unit/time metadata and hidden method prediction patterns. It does not use any human preview or label. The manifests retain video×pattern population counts, sample counts, inclusion probability, and inverse-probability descriptive analysis weight. Temporal diversity tries a frozen `{TEMPORAL_DIVERSITY_SEC}`-second separation within video, then deterministically relaxes it only to meet a required quota.
"""
    write_text_once(OUT/"SAMPLING_AUDIT.md",audit)
    print(json.dumps({"status":"PROTOCOL_FROZEN","protocol_hash":protocol["protocol_hash"],"population":len(population),"primary":len(primary_hidden),"reserve":len(reserve_hidden),"patterns":patterns},sort_keys=True))


def video_paths() -> dict[str, Path]:
    d=read_json(VIDEO_MANIFEST)
    result={x["video_id"]:ROOT/x["path"] for x in d["videos"]}
    if set(result)!=set(VIDEOS) or any(not x.is_file() for x in result.values()): raise RuntimeError("frozen source videos unavailable")
    return result


def marker_filter(fps: int, start: float, end: float, anchor_a_start: float, anchor_a_end: float, anchor_b_start: float, anchor_b_end: float) -> str:
    a0=max(0.0,anchor_a_start-start); a1=max(0.0,anchor_a_end-start); b0=max(0.0,anchor_b_start-start); b1=max(0.0,anchor_b_end-start)
    # Marker labels are intentionally neutral A/B, not "positive", "merge", or method names.
    return (
        f"fps={fps},scale=640:-2,drawbox=x=18:y=18:w=42:h=42:color=yellow@0.85:t=fill:enable='between(t,{a0:.3f},{a1:.3f})',"
        f"drawtext=fontfile={FONT}:text='A':x=30:y=22:fontsize=28:fontcolor=black:enable='between(t,{a0:.3f},{a1:.3f})',"
        f"drawbox=x=18:y=18:w=42:h=42:color=cyan@0.85:t=fill:enable='between(t,{b0:.3f},{b1:.3f})',"
        f"drawtext=fontfile={FONT}:text='B':x=30:y=22:fontsize=28:fontcolor=black:enable='between(t,{b0:.3f},{b1:.3f})'"
    )


def render_clip(source: Path, dest: Path, clip: dict[str, Any], row: dict[str, Any]) -> None:
    if dest.exists(): return
    start=float(clip["start_sec"]); end=float(clip["end_sec"]); duration=end-start
    if duration<=0: raise RuntimeError("nonpositive clip duration")
    filt=marker_filter(int(clip["fps"]),start,end,float(row["anchor_a_start"]),float(row["anchor_a_end"]),float(row["anchor_b_start"]),float(row["anchor_b_end"]))
    dest.parent.mkdir(parents=True,exist_ok=True)
    command=["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-ss",f"{start:.3f}","-i",str(source),"-t",f"{duration:.3f}","-an","-vf",filt,"-c:v","libx264","-preset","veryfast","-crf","26","-movflags","+faststart","-y",str(dest)]
    subprocess.run(command,check=True)


def clips() -> None:
    if not (OUT/"HUMAN_CONTINUITY_PROTOCOL.json").exists(): raise RuntimeError("freeze first")
    state=read_json(OUT/"HUMAN_CONTINUITY_STATE.json")
    if state["human_labels_observed"]: raise RuntimeError("cannot generate/replace package after human labels")
    primary=pd.read_csv(OUT/"PRIMARY_SAMPLE_MANIFEST.csv").to_dict(orient="records")
    public=read_json(OUT/"annotation_package/PRIMARY_BLINDED_CASES.json")["cases"]
    hidden={x["public_case_id"]:x for x in primary}; paths=video_paths()
    render_rows=[]
    for case in public:
        row=hidden[case["case_id"]]
        for clip in case["clips"]:
            dest=OUT/"annotation_package"/clip["path"]
            render_clip(paths[row["video_id"]],dest,clip,row)
            render_rows.append({
                "case_id": case["case_id"],
                "blind_clip": dest.name,
                "clip_kind": clip["kind"],
                "source_video_hash": sha(paths[row["video_id"]]),
                "render_contract_hash": chash({
                    "start_sec": clip["start_sec"], "end_sec": clip["end_sec"],
                    "fps": clip["fps"], "anchor_a_start": row["anchor_a_start"],
                    "anchor_a_end": row["anchor_a_end"], "anchor_b_start": row["anchor_b_start"],
                    "anchor_b_end": row["anchor_b_end"], "marker_rule": "neutral_A_B_drawbox_drawtext",
                }),
                "marker_contract": "neutral A/B marker only; A is yellow, B is cyan",
            })
    write_csv_once(OUT/"CLIP_RENDER_MANIFEST.csv",render_rows,list(render_rows[0]))
    state["status"]="CLIPS_GENERATED"; state["clip_count"]=sum(len(x["clips"]) for x in public)
    (OUT/"HUMAN_CONTINUITY_STATE.json").write_text(json.dumps(state,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"status":"CLIPS_GENERATED","clips":state["clip_count"]},sort_keys=True))


def ffprobe(path: Path) -> dict[str, Any]:
    # Files may be read immediately after ffmpeg's MP4 finalization on this
    # shared filesystem.  A bounded retry makes QA robust without accepting a
    # broken clip: all attempts must eventually decode successfully.
    last = None
    for _ in range(3):
        r=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","json",str(path)],text=True,capture_output=True)
        if r.returncode == 0:
            return json.loads(r.stdout)
        last = r.stderr.strip()
        time.sleep(0.25)
    raise RuntimeError(f"ffprobe failed for {path}: {last}")


def verify() -> None:
    protocol=read_json(OUT/"HUMAN_CONTINUITY_PROTOCOL.json")
    public_path=OUT/"annotation_package/PRIMARY_BLINDED_CASES.json"; public=read_json(public_path)
    hidden=Path(OUT/"PRIMARY_SAMPLE_MANIFEST.csv").read_text(encoding="utf-8")
    hidden_rows=list(csv.DictReader(hidden.splitlines()))
    public_text=public_path.read_text(encoding="utf-8")+(OUT/"annotation_package/index.html").read_text(encoding="utf-8")+(OUT/"annotation_package/app.js").read_text(encoding="utf-8")
    # Do not include predicate words such as "relevant" here: they occur in
    # the frozen human query and are not method leakage.  Every listed string
    # below names hidden method/result metadata that a human must never see.
    leak_terms=["C0_same","C1_same","K3_same","prediction_pattern","F1","Delta","overmerge","gap-limited","model-relative","eventrelation","materializer"]
    found=[x for x in leak_terms if x.lower() in public_text.lower()]
    if found: raise RuntimeError(f"method/semantic leakage in public package: {found}")
    if "C1_same_event" not in hidden or "K3_same_event" not in hidden: raise RuntimeError("hidden method metadata absent")
    case_ids=[x["case_id"] for x in public["cases"]]
    if len(case_ids)!=PRIMARY_N or len(set(case_ids))!=PRIMARY_N: raise RuntimeError("public case IDs are not unique")
    visible_source_order=[(x["video_id"], float(x["anchor_a_start"])) for x in sorted(hidden_rows,key=lambda x:int(x["public_order"]))]
    if visible_source_order == sorted(visible_source_order): raise RuntimeError("public case ordering is not shuffled")
    # Pixel-level marker checks complement the render-contract manifest.  The
    # marker box begins at (18,18); its interior keeps a robust 4:2 colour
    # dominance even after H.264 compression (yellow: R/G; cyan: B/G).
    import cv2
    def marker_visible(path: Path, relative_sec: float, expected: str) -> bool:
        cap=cv2.VideoCapture(str(path))
        try:
            cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, relative_sec) * 1000.0)
            ok, frame=cap.read()
            if not ok or frame.shape[0] < 40 or frame.shape[1] < 70: return False
            b,g,r=(float(x) for x in frame[46,22])
            return (r > 110 and g > 110 and b < 120) if expected == "A" else (b > 110 and g > 110 and r < 120)
        finally:
            cap.release()
    check_rows=[]; marker_rows=[]
    for case in public["cases"]:
        for clip in case["clips"]:
            path=OUT/"annotation_package"/clip["path"]
            payload=ffprobe(path)
            duration=float(payload["format"].get("duration",0))
            if duration<=0: raise RuntimeError(f"undecodable clip: {path}")
            if not re.fullmatch(r"(CASE_\d{4})_(context|anchor_a|anchor_b)\.mp4",path.name): raise RuntimeError(f"filename leakage/nonblind name: {path.name}")
            check_rows.append({"case_id":case["case_id"],"clip":path.name,"duration_sec":duration,"decode_pass":True})
            row=next(x for x in hidden_rows if x["public_case_id"] == case["case_id"])
            for tag in ("a", "b"):
                lo=max(float(clip["start_sec"]),float(row[f"anchor_{tag}_start"]))
                hi=min(float(clip["end_sec"]),float(row[f"anchor_{tag}_end"]))
                if hi <= lo: continue
                passed=marker_visible(path,((lo+hi)/2.0)-float(clip["start_sec"]),tag.upper())
                marker_rows.append({"case_id":case["case_id"],"clip":path.name,"marker":tag.upper(),"marker_pass":passed})
                if not passed: raise RuntimeError(f"expected neutral {tag.upper()} marker missing from {path}")
    # Keep the initial decode-only audit immutable; V2 adds the final
    # marker-level QA after the first pre-label engineering correction.
    write_csv_once(OUT/"ANNOTATION_PACKAGE_QA_V2.csv",check_rows,list(check_rows[0]))
    write_csv_once(OUT/"ANNOTATION_MARKER_QA.csv",marker_rows,list(marker_rows[0]))
    state=read_json(OUT/"HUMAN_CONTINUITY_STATE.json"); state.update({"status":"WAITING_FOR_HUMAN","package_verified":True,"human_labels_observed":0,"protocol_hash":protocol["protocol_hash"]})
    (OUT/"HUMAN_CONTINUITY_STATE.json").write_text(json.dumps(state,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"status":"PACKAGE_READY","cases":len(case_ids),"clips":len(check_rows),"protocol_hash":protocol["protocol_hash"]},sort_keys=True))


def main() -> None:
    ap=argparse.ArgumentParser(); ap.add_argument("action",choices=("freeze","clips","verify","amend-analysis")); args=ap.parse_args()
    if args.action=="freeze": freeze()
    elif args.action=="clips": clips()
    elif args.action=="amend-analysis": amend_analysis_contract()
    else: verify()
if __name__=="__main__": main()
