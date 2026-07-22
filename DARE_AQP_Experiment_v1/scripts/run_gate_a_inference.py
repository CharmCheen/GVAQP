#!/usr/bin/env python3
"""Label-blind, resumable frozen CLIP/X-CLIP Gate A inference."""

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import subprocess
import tempfile
import time
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parent


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                     delete=False) as handle:
        handle.write(text); handle.flush(); os.fsync(handle.fileno())
        temporary = handle.name
    os.replace(temporary, path)


def atomic_json(path, value):
    atomic_text(path, json.dumps(value, sort_keys=True, indent=2) + "\n")


def atomic_csv(path, rows, fields=None):
    if not rows:
        raise ValueError(f"refusing empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or list(rows[0])
    with tempfile.NamedTemporaryFile("w", newline="", encoding="utf-8",
                                     dir=path.parent, delete=False) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)
        handle.flush(); os.fsync(handle.fileno()); temporary = handle.name
    os.replace(temporary, path)


def extract_rgb_frames(video_path, timestamps):
    import cv2
    started = time.perf_counter()
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"cannot open video: {video_path}")
    frames = []
    try:
        for timestamp in timestamps:
            capture.set(cv2.CAP_PROP_POS_MSEC, 1000.0 * timestamp)
            ok, bgr = capture.read()
            if not ok:
                raise RuntimeError(f"failed to decode frame at {timestamp:.3f}s")
            frames.append(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    finally:
        capture.release()
    return frames, time.perf_counter() - started


def synchronize(device):
    if device == "cuda":
        import torch
        torch.cuda.synchronize()


def energy_mj():
    try:
        value = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=total_energy_consumption",
             "--format=csv,noheader,nounits", "-i", "0"], text=True,
            stderr=subprocess.DEVNULL, timeout=5).strip().splitlines()[0]
        return float(value)
    except Exception:
        return None


def checkpoint_path(output, method, unit_id):
    return output / "checkpoints" / method / f"unit_{unit_id:04d}.json"


def load_checkpoint(path, method, revision, unit_id):
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if (value.get("signal_id"), value.get("model_revision"), value.get("unit_id")) != (method, revision, unit_id):
        raise RuntimeError(f"checkpoint identity mismatch: {path}")
    embedding = value.get("embedding")
    if not embedding or not all(math.isfinite(float(x)) for x in embedding):
        raise RuntimeError(f"invalid embedding checkpoint: {path}")
    return value


def unit_timestamps(method, unit):
    start, end = float(unit["start_time"]), float(unit["end_time"])
    if method == "image_text":
        return [(start + end) / 2.0]
    return [start + (index + 0.5) * (end - start) / 8.0 for index in range(8)]


def load_model(method, spec, device):
    from transformers import AutoProcessor, CLIPModel, XCLIPModel, XCLIPProcessor
    started = time.perf_counter()
    if method == "image_text":
        processor = AutoProcessor.from_pretrained(spec["model_id"], revision=spec["revision"], local_files_only=True)
        model = CLIPModel.from_pretrained(spec["model_id"], revision=spec["revision"], local_files_only=True)
    else:
        processor = XCLIPProcessor.from_pretrained(spec["model_id"], revision=spec["revision"], local_files_only=True)
        model = XCLIPModel.from_pretrained(spec["model_id"], revision=spec["revision"], local_files_only=True)
    model = model.to(device).eval()
    synchronize(device)
    return processor, model, time.perf_counter() - started


def embed_unit(method, processor, model, frames, device):
    import torch
    preprocess_start = time.perf_counter()
    if method == "image_text":
        inputs = processor(images=frames, return_tensors="pt")
    else:
        inputs = processor(videos=frames, return_tensors="pt")
    inputs = {key: value.to(device) for key, value in inputs.items()}
    preprocess_seconds = time.perf_counter() - preprocess_start
    synchronize(device); forward_start = time.perf_counter()
    with torch.inference_mode():
        if method == "image_text":
            outputs = model.get_image_features(pixel_values=inputs["pixel_values"])
            feature = outputs.pooler_output if hasattr(outputs, "pooler_output") else outputs
            prompt_visual = None
        else:
            pixel_values = inputs["pixel_values"]
            batch_size, num_frames, channels, height, width = pixel_values.shape
            vision = model.vision_model(pixel_values=pixel_values.reshape(-1, channels, height, width))
            projected = model.visual_projection(vision.pooler_output)
            integrated = model.mit(projected.view(batch_size, num_frames, -1))
            feature = integrated.pooler_output
            prompt_visual = model.prompts_visual_layernorm(vision.last_hidden_state[:, 1:, :])
            prompt_visual = prompt_visual @ model.prompts_visual_projection
            prompt_visual = prompt_visual.view(batch_size, num_frames, -1, feature.shape[-1]).mean(dim=1)
    synchronize(device); forward_seconds = time.perf_counter() - forward_start
    feature = feature[0] / feature[0].norm(p=2)
    extra = None if prompt_visual is None else prompt_visual[0].detach().cpu().tolist()
    return [float(x) for x in feature.detach().cpu()], extra, preprocess_seconds, forward_seconds


def score_index(method, processor, model, query, embeddings, unit_ids, device):
    import torch
    prep_start = time.perf_counter()
    text_inputs = processor(text=[query], return_tensors="pt", padding=True)
    text_inputs = {key: value.to(device) for key, value in text_inputs.items()}
    text_preprocess = time.perf_counter() - prep_start
    synchronize(device); text_start = time.perf_counter()
    with torch.inference_mode():
        if method == "image_text":
            outputs = model.get_text_features(
                input_ids=text_inputs["input_ids"], attention_mask=text_inputs.get("attention_mask"))
            text_feature = outputs.pooler_output if hasattr(outputs, "pooler_output") else outputs
        else:
            outputs = model.text_model(input_ids=text_inputs["input_ids"], attention_mask=text_inputs.get("attention_mask"))
            text_feature = model.text_projection(outputs.pooler_output)
    synchronize(device); text_forward = time.perf_counter() - text_start
    matrix = torch.tensor([embeddings[uid] for uid in unit_ids], device=device)
    synchronize(device); similarity_start = time.perf_counter()
    with torch.inference_mode():
        if method == "image_text":
            text_feature = text_feature[0] / text_feature[0].norm(p=2)
            scores = model.logit_scale.exp() * (matrix @ text_feature)
        else:
            prompt_visual = torch.tensor([embeddings[(uid, "prompt_visual")] for uid in unit_ids], device=device)
            conditioned = text_feature.unsqueeze(0).expand(len(unit_ids), -1, -1)
            conditioned = conditioned + model.prompts_generator(conditioned, prompt_visual)
            conditioned = conditioned / conditioned.norm(p=2, dim=-1, keepdim=True)
            scores = torch.einsum("bd,bkd->bk", matrix, model.logit_scale.exp() * conditioned)[:, 0]
    synchronize(device); similarity_seconds = time.perf_counter() - similarity_start
    ranking_start = time.perf_counter()
    values = [float(x) for x in scores.detach().cpu()]
    sorted(range(len(values)), key=lambda index: (-values[index], unit_ids[index]))
    ranking_seconds = time.perf_counter() - ranking_start
    return values, text_preprocess, text_forward, similarity_seconds, ranking_seconds


def run_method(method, config, units, video_path, output, device):
    import torch
    spec = config["methods"][method]
    unit_ids = [int(row["unit_id"]) for row in units]
    torch.cuda.reset_peak_memory_stats() if device == "cuda" else None
    cpu_start, wall_start, energy_start = time.process_time(), time.perf_counter(), energy_mj()
    processor, model, model_load_seconds = load_model(method, spec, device)
    attention = str(getattr(model.config, "_attn_implementation", "default"))
    embeddings, checkpoints, cache_hits, retries = {}, [], 0, 0
    for index, unit in enumerate(units, 1):
        uid = int(unit["unit_id"]); path = checkpoint_path(output, method, uid)
        record = load_checkpoint(path, method, spec["revision"], uid)
        if record is not None:
            cache_hits += 1
        else:
            try:
                frames, loading = extract_rgb_frames(video_path, unit_timestamps(method, unit))
                embedding, prompt_visual, preprocessing, forward = embed_unit(method, processor, model, frames, device)
                record = {"signal_id": method, "model_id": spec["model_id"],
                          "model_revision": spec["revision"], "unit_id": uid,
                          "frames": len(frames), "data_loading_seconds": loading,
                          "preprocessing_cpu_seconds": preprocessing,
                          "model_forward_seconds": forward, "embedding": embedding,
                          "prompt_visual_features": prompt_visual}
                atomic_json(path, record)
            except Exception as error:
                retries += 1
                atomic_json(output / "FAILED_UNIT.json", {"signal_id": method, "unit_id": uid, "error": repr(error)})
                raise
        embeddings[uid] = record["embedding"]
        if method == "video_text":
            if record.get("prompt_visual_features") is None: raise RuntimeError(f"missing X-CLIP prompt features: {path}")
            embeddings[(uid, "prompt_visual")] = record["prompt_visual_features"]
        checkpoints.append(record)
        if index == 1 or index % 25 == 0 or index == len(units):
            print(f"{method}: {index}/{len(units)} cache_hits={cache_hits}", flush=True)
    values, text_prep, text_forward, similarity, ranking = score_index(
        method, processor, model, config["query_text"], embeddings, unit_ids, device)
    energy_end = energy_mj(); wall = time.perf_counter() - wall_start
    load_s = sum(float(x["data_loading_seconds"]) for x in checkpoints)
    prep_s = sum(float(x["preprocessing_cpu_seconds"]) for x in checkpoints)
    forward_s = sum(float(x["model_forward_seconds"]) for x in checkpoints)
    warm_query = text_prep + text_forward + similarity + ranking
    latencies = [float(x["data_loading_seconds"]) + float(x["preprocessing_cpu_seconds"]) + float(x["model_forward_seconds"]) for x in checkpoints]
    latencies.sort()
    def quantile(q):
        return latencies[round(q * (len(latencies) - 1))]
    runtime = {
        "signal_id": method, "model_id": spec["model_id"], "model_revision": spec["revision"],
        "model_load_seconds": model_load_seconds, "cold_total_inference_seconds": wall,
        "warm_index_query_seconds": warm_query,
        "one_time_model_index_seconds": model_load_seconds + load_s + prep_s + forward_s,
        "reusable_video_embedding_seconds": load_s + prep_s + forward_s,
        "query_text_preprocessing_seconds": text_prep, "query_text_encoding_seconds": text_forward,
        "query_similarity_seconds": similarity, "ranking_seconds": ranking,
        "data_loading_seconds": load_s, "preprocessing_cpu_seconds": prep_s,
        "model_forward_seconds": forward_s, "cpu_process_seconds": time.process_time() - cpu_start,
        "gpu_seconds": forward_s + text_forward + similarity if device == "cuda" else 0.0,
        "per_unit_latency_p50_seconds": quantile(.5), "per_unit_latency_p90_seconds": quantile(.9),
        "per_unit_latency_p95_seconds": quantile(.95), "per_unit_latency_max_seconds": max(latencies),
        "peak_gpu_memory_mb": torch.cuda.max_memory_allocated() / 2**20 if device == "cuda" else 0.0,
        "frames_processed": sum(int(x["frames"]) for x in checkpoints), "synchronization_method": "torch.cuda.synchronize around timed GPU regions",
        "batch_size": 1, "dtype": str(next(model.parameters()).dtype), "attention_implementation": attention,
        "failed_units": retries, "retried_units": retries, "unit_checkpoint_cache_hits": cache_hits,
        "model_files_cached": True, "energy_start_mj": "" if energy_start is None else energy_start,
        "energy_end_mj": "" if energy_end is None else energy_end,
        "energy_consumed_mj": "" if energy_start is None or energy_end is None else energy_end - energy_start,
        "device": device, "software_versions": f"python={platform.python_version()};torch={torch.__version__}",
    }
    checkpoint_rows = [{"signal_id": method, "unit_id": x["unit_id"],
                        "path": str(checkpoint_path(output, method, x["unit_id"])),
                        "sha256": sha256(checkpoint_path(output, method, x["unit_id"]))} for x in checkpoints]
    del model, processor
    if device == "cuda": torch.cuda.empty_cache()
    return values, runtime, checkpoint_rows


def percentile_ranks(values, unit_ids):
    order = sorted(range(len(values)), key=lambda index: (-values[index], unit_ids[index]))
    result, denominator = [0.0] * len(values), max(1, len(values) - 1)
    for rank, index in enumerate(order): result[index] = 1.0 - rank / denominator
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=PACKAGE / "config/gate_a_frozen.json")
    parser.add_argument("--output", type=Path, default=PACKAGE / "outputs/gate_a_final")
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cuda")
    parser.add_argument("--methods", nargs="+", choices=["image_text", "video_text"], default=["image_text", "video_text"])
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    units_path, proxy_path, video_path = (REPO / config["inputs"]["units"], REPO / config["inputs"]["public_proxy"], REPO / config["video"])
    units = read_csv(units_path); unit_ids = [int(x["unit_id"]) for x in units]
    audit = {"status": "DRY_RUN_ONLY" if not args.execute else "EXECUTING", "video": str(video_path),
             "video_exists": video_path.is_file(), "video_sha256": sha256(video_path) if video_path.is_file() else None,
             "units": len(units), "unit_ids_contiguous": unit_ids == list(range(len(units))),
             "methods": args.methods, "device": args.device, "downloads_allowed": False,
             "forbidden_inputs_opened": [], "config_sha256": sha256(args.config)}
    print(json.dumps(audit, indent=2), flush=True)
    if not args.execute: return
    import torch, transformers
    if args.device == "cuda" and not torch.cuda.is_available(): raise RuntimeError("CUDA unavailable")
    if len(units) != 347 or unit_ids != list(range(347)) or not video_path.is_file(): raise RuntimeError("frozen input audit failed")
    execution = {**audit, "status": "SEALED_INFERENCE_CONFIG", "query_text": config["query_text"],
                 "sampling": {m: config["methods"][m]["sampling"] for m in args.methods},
                 "batch_size": 1, "dtype": "float32", "transformers": transformers.__version__,
                 "torch": torch.__version__, "cuda_runtime": torch.version.cuda,
                 "gpu": torch.cuda.get_device_name(0) if args.device == "cuda" else "none"}
    atomic_json(args.output / "inference_configuration.json", execution)
    proxy_rows = read_csv(proxy_path); proxy = {int(x["frame_idx"]): float(x["proxy_score"]) for x in proxy_rows}
    if set(proxy) != set(unit_ids): raise RuntimeError("public proxy coverage mismatch")
    signals, runtime_rows, checkpoint_rows = {"current_proxy": [proxy[x] for x in unit_ids]}, [], []
    for method in args.methods:
        values, runtime, checkpoints = run_method(method, config, units, video_path, args.output, args.device)
        signals[method] = values; runtime_rows.append(runtime); checkpoint_rows.extend(checkpoints)
    if set(args.methods) == {"image_text", "video_text"}:
        left, right = percentile_ranks(signals["image_text"], unit_ids), percentile_ranks(signals["video_text"], unit_ids)
        signals["rank_fusion"] = [(a + b) / 2 for a, b in zip(left, right)]
    score_rows, ranking_manifest = [], []
    for signal, values in signals.items():
        spec = config["methods"][signal]
        for uid, value in zip(unit_ids, values):
            score_rows.append({"signal_id": signal, "unit_id": uid, "score": repr(value),
                               "model_id": spec["model_id"], "model_revision": spec["revision"], "prompt_id": spec["prompt_id"]})
        order = sorted(unit_ids, key=lambda uid: (-values[uid], uid))
        ranking_path = args.output / "sealed_rankings" / f"{signal}.csv"
        atomic_csv(ranking_path, [{"signal_id": signal, "rank": i, "unit_id": uid, "score": repr(values[uid])} for i, uid in enumerate(order, 1)])
        ranking_manifest.append({"signal_id": signal, "path": str(ranking_path), "rows": len(order), "sha256": sha256(ranking_path)})
    atomic_csv(args.output / "raw_scores.csv", score_rows)
    atomic_csv(args.output / "runtime_ledger.csv", runtime_rows)
    atomic_csv(args.output / "unit_checkpoint_manifest.csv", checkpoint_rows)
    atomic_csv(args.output / "sealed_ranking_manifest.csv", ranking_manifest)
    atomic_json(args.output / "INFERENCE_COMPLETE.json", {"status": "COMPLETE", "units_per_signal": 347,
                "signals": sorted(signals), "scores_sha256": sha256(args.output / "raw_scores.csv"),
                "ranking_manifest_sha256": sha256(args.output / "sealed_ranking_manifest.csv"),
                "physical_exact_oracle_vlm_calls": 0})
    print(args.output / "INFERENCE_COMPLETE.json", flush=True)


if __name__ == "__main__": main()
