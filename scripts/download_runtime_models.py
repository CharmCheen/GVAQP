"""Download only the frozen runtime identities; supports --dry-run."""
import argparse, json, os, shutil, urllib.request
from pathlib import Path
import yaml

ROOT = Path(__file__).parents[1]
OUT = ROOT / "outputs/runtime_model_contract_v1/models"
OUT.mkdir(parents=True, exist_ok=True)
CONTRACT = yaml.safe_load((ROOT / "configs/runtime_models.yaml").read_text())["models"]
MIN_FREE = 50 * 1024**3

def hf_sizes(repo, revision):
    with urllib.request.urlopen("https://huggingface.co/api/models/" + repo, timeout=60) as f: data = json.load(f)
    total = 0; rows = []
    for item in data["siblings"]:
        name = item["rfilename"]
        req = urllib.request.Request(f"https://huggingface.co/{repo}/resolve/{revision}/{name}", method="HEAD")
        with urllib.request.urlopen(req, timeout=60) as r:
            size = int(r.headers.get("X-Linked-Size") or r.headers.get("Content-Length") or 0)
        total += size; rows.append({"file": name, "size_bytes": size})
    return total, rows

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--component", choices=["yolo", "vlm", "all"], default="all"); args = ap.parse_args(); rows = {}
    y, v = CONTRACT["yolo"], CONTRACT["vlm"]
    if args.component in {"yolo", "all"}:
        p = Path(os.environ.get(y["local_path_env"], Path(os.environ.get("GARC_MODEL_CACHE", "~/.cache/garc/models")).expanduser() / "yolo/yolov8n.pt"))
        rows["yolo"] = {"model_id": y["model_id"], "path": str(p), "required_bytes": 6549796, "sha256": y["sha256"], "source": "Ultralytics GitHub release auto-download"}
        if not args.dry_run:
            from ultralytics import YOLO
            p.parent.mkdir(parents=True, exist_ok=True); os.chdir(p.parent); YOLO(str(p))
    if args.component in {"vlm", "all"}:
        if args.dry_run:
            total, files = int(v["resolved_snapshot_bytes"]), [{"file_count": v["resolved_file_count"], "source": "fixed revision HEAD validation"}]
        else:
            total, files = hf_sizes(v["model_id"], v["revision"])
        cache = Path(os.environ.get("GARC_MODEL_CACHE", "~/.cache/garc/models")).expanduser(); p = Path(os.environ.get(v["local_path_env"], cache / "vlm/Qwen3-VL-32B-Instruct")); free = shutil.disk_usage(p.parent if p.parent.exists() else cache).free
        rows["vlm"] = {"model_id": v["model_id"], "revision": v["revision"], "path": str(p), "required_bytes": total, "file_count": len(files), "free_bytes_before": free, "free_bytes_after_estimate": free-total, "files": files}
        if free-total < MIN_FREE: raise SystemExit(f"BLOCKED_DISK: free after download {free-total} < {MIN_FREE}")
        if not args.dry_run:
            from huggingface_hub import snapshot_download
            snapshot_download(repo_id=v["model_id"], revision=v["revision"], local_dir=str(p), cache_dir=os.environ.get("HUGGINGFACE_HUB_CACHE"))
    print(json.dumps(rows, indent=2)); (OUT / ("download_dry_run.json" if args.dry_run else "download_resolution.json")).write_text(json.dumps(rows, indent=2) + "\n")

if __name__ == "__main__": main()
