from huggingface_hub import list_repo_files, hf_hub_download
from pathlib import Path
import argparse
import csv
import os
import time
import traceback

REPO_ID = "nexar-ai/nexar_collision_prediction"

def is_video(path: str) -> bool:
    return path.lower().endswith((".mp4", ".mov", ".avi", ".mkv"))

def wanted_train(path: str) -> bool:
    return is_video(path) and (
        path.startswith("train/positive/") or
        path.startswith("train/negative/")
    )

def wanted_all(path: str) -> bool:
    return is_video(path)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-dir", required=True)
    parser.add_argument("--manifest-out", required=True)
    parser.add_argument("--mode", choices=["train", "all"], default="train")
    parser.add_argument("--max-files", type=int, default=0, help="0 means no cap")
    parser.add_argument("--sleep", type=float, default=0.0)
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args()

    local_dir = Path(args.local_dir)
    local_dir.mkdir(parents=True, exist_ok=True)

    print(f"[info] listing repo files: {REPO_ID}")
    files = list_repo_files(repo_id=REPO_ID, repo_type="dataset")

    if args.mode == "train":
        targets = [f for f in files if wanted_train(f)]
    else:
        targets = [f for f in files if wanted_all(f)]

    targets = sorted(targets)

    if args.max_files and args.max_files > 0:
        targets = targets[:args.max_files]

    print(f"[info] mode={args.mode}")
    print(f"[info] target video files={len(targets)}")
    print(f"[info] local_dir={local_dir}")

    manifest_path = Path(args.manifest_out)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "idx",
        "hf_path",
        "split",
        "label",
        "local_path",
        "status",
        "file_size_bytes",
        "attempts",
        "error",
    ]

    done = 0
    failed = 0

    with manifest_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for idx, hf_path in enumerate(targets, start=1):
            parts = hf_path.split("/")
            split = parts[0] if len(parts) > 0 else ""
            label = parts[1] if len(parts) > 1 else ""

            local_expected = local_dir / hf_path
            if local_expected.exists() and local_expected.stat().st_size > 0:
                status = "already_exists"
                size = local_expected.stat().st_size
                writer.writerow({
                    "idx": idx,
                    "hf_path": hf_path,
                    "split": split,
                    "label": label,
                    "local_path": str(local_expected),
                    "status": status,
                    "file_size_bytes": size,
                    "attempts": 0,
                    "error": "",
                })
                done += 1
                print(f"[{idx}/{len(targets)}] exists {hf_path} size={size}")
                continue

            last_err = ""
            local_path = ""
            status = "failed"
            size = 0
            attempts = 0

            for attempt in range(1, args.retries + 1):
                attempts = attempt
                try:
                    print(f"[{idx}/{len(targets)}] download attempt {attempt}: {hf_path}")
                    p = hf_hub_download(
                        repo_id=REPO_ID,
                        repo_type="dataset",
                        filename=hf_path,
                        local_dir=str(local_dir),
                        local_dir_use_symlinks=False,
                    )
                    local_path = p
                    pp = Path(p)
                    size = pp.stat().st_size if pp.exists() else 0
                    if size > 0:
                        status = "downloaded"
                        done += 1
                        print(f"  -> ok {p} size={size}")
                        break
                    else:
                        last_err = "downloaded file has zero size"
                except Exception as e:
                    last_err = repr(e)
                    print(f"  -> failed: {last_err}")

                if attempt < args.retries:
                    time.sleep(2.0)

            if status == "failed":
                failed += 1

            writer.writerow({
                "idx": idx,
                "hf_path": hf_path,
                "split": split,
                "label": label,
                "local_path": local_path or str(local_expected),
                "status": status,
                "file_size_bytes": size,
                "attempts": attempts,
                "error": last_err,
            })
            f.flush()

            if args.sleep > 0:
                time.sleep(args.sleep)

    print(f"[done] success_or_exists={done}, failed={failed}, total={len(targets)}")
    print(f"[done] manifest={manifest_path}")

if __name__ == "__main__":
    main()
