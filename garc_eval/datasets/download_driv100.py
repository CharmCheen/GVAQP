"""Download a small DRIV100 video sample from Zenodo.

This script uses Zenodo record metadata to choose a real video file when one is
available, or the smallest supported archive otherwise.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import tarfile
import urllib.request
import zipfile
from dataclasses import dataclass
from typing import Any


RECORD_API_URL = "https://zenodo.org/api/records/4389243"
VIDEO_SUFFIXES = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
ARCHIVE_SUFFIXES = {".zip", ".tar", ".tgz", ".gz", ".bz2", ".xz"}


@dataclass(frozen=True)
class ZenodoFile:
    name: str
    size: int
    url: str

    @property
    def suffix(self) -> str:
        return pathlib.Path(self.name).suffix.lower()

    @property
    def is_video(self) -> bool:
        return self.suffix in VIDEO_SUFFIXES

    @property
    def is_archive(self) -> bool:
        name = self.name.lower()
        return self.suffix in ARCHIVE_SUFFIXES or name.endswith((".tar.gz", ".tar.bz2", ".tar.xz"))


def fetch_metadata() -> dict[str, Any]:
    with urllib.request.urlopen(RECORD_API_URL, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_files(metadata: dict[str, Any]) -> list[ZenodoFile]:
    files = []
    for item in metadata.get("files", []):
        name = item.get("key") or item.get("filename") or item.get("name")
        size = int(item.get("size") or 0)
        links = item.get("links") or {}
        url = links.get("download") or links.get("self")
        if name and url:
            files.append(ZenodoFile(name=name, size=size, url=url))
    return files


def gb(size: int) -> float:
    return size / (1024**3)


def report_lines(files: list[ZenodoFile], selected: ZenodoFile | None, downloaded: pathlib.Path | None,
                 video_path: pathlib.Path | None, success: bool, notes: list[str]) -> list[str]:
    lines = [
        "# DRIV100 Dataset Download Report",
        "",
        f"- Zenodo API: {RECORD_API_URL}",
        f"- success: {success}",
        "",
        "## Zenodo Files",
        "",
        "| filename | size_gb | download_url |",
        "| --- | ---: | --- |",
    ]
    for f in files:
        lines.append(f"| {f.name} | {gb(f.size):.3f} | {f.url} |")
    lines.extend(["", "## Selection", ""])
    if selected:
        lines.append(f"- selected file: {selected.name}")
        lines.append(f"- selected size: {selected.size} bytes ({gb(selected.size):.3f} GB)")
    else:
        lines.append("- selected file: none")
    lines.append(f"- downloaded path: {downloaded if downloaded else 'none'}")
    lines.append(f"- video path: {video_path if video_path else 'none'}")
    if video_path and video_path.exists():
        lines.append(f"- video size: {video_path.stat().st_size} bytes ({gb(video_path.stat().st_size):.3f} GB)")
    lines.extend(["", "## Notes", ""])
    if notes:
        lines.extend(f"- {note}" for note in notes)
    else:
        lines.append("- none")
    return lines


def write_report(outdir: pathlib.Path, files: list[ZenodoFile], selected: ZenodoFile | None,
                 downloaded: pathlib.Path | None, video_path: pathlib.Path | None,
                 success: bool, notes: list[str]) -> pathlib.Path:
    report_path = pathlib.Path(os.environ.get("GARC_OUTPUT_DIR", "garc_eval/outputs")) / "driv100_smoke" / "dataset_download_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report_lines(files, selected, downloaded, video_path, success, notes)) + "\n", encoding="utf-8")
    return report_path


def download_file(file: ZenodoFile, outdir: pathlib.Path) -> pathlib.Path:
    outdir.mkdir(parents=True, exist_ok=True)
    dest = outdir / file.name
    if dest.exists() and dest.stat().st_size == file.size:
        return dest
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(file.url, timeout=60) as response, tmp.open("wb") as fh:
        shutil.copyfileobj(response, fh)
    tmp.replace(dest)
    return dest


def extract_archive(path: pathlib.Path, outdir: pathlib.Path) -> pathlib.Path:
    extract_dir = outdir / (path.name + ".extracted")
    extract_dir.mkdir(parents=True, exist_ok=True)
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as zf:
            zf.extractall(extract_dir)
    elif tarfile.is_tarfile(path):
        with tarfile.open(path) as tf:
            tf.extractall(extract_dir)
    else:
        raise RuntimeError(f"Unsupported archive format: {path}")
    return extract_dir


def find_first_video(root: pathlib.Path) -> pathlib.Path | None:
    videos = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_SUFFIXES]
    return sorted(videos, key=lambda p: str(p).lower())[0] if videos else None


def link_or_copy_video(src: pathlib.Path) -> pathlib.Path:
    garc_home = pathlib.Path(os.environ.get("GARC_HOME", pathlib.Path.cwd()))
    video_dir = pathlib.Path(os.environ.get("GARC_DATA_DIR", garc_home / "data")) / "videos"
    video_dir.mkdir(parents=True, exist_ok=True)
    dest = video_dir / "driv100_sample.mp4"
    if dest.exists() or dest.is_symlink():
        dest.unlink()
    try:
        dest.symlink_to(src.resolve())
    except OSError:
        shutil.copy2(src, dest)
    return dest


def select_file(files: list[ZenodoFile]) -> ZenodoFile | None:
    videos = [f for f in files if f.is_video]
    if videos:
        return videos[0]
    archives = sorted([f for f in files if f.is_archive], key=lambda f: f.size)
    return archives[0] if archives else None


def main() -> None:
    parser = argparse.ArgumentParser(description="List or download a DRIV100 sample video from Zenodo")
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--list-only", action="store_true")
    parser.add_argument("--download-first-video", action="store_true")
    parser.add_argument("--max-download-gb", type=float, default=5.0)
    args = parser.parse_args()

    outdir = pathlib.Path(args.outdir)
    metadata = fetch_metadata()
    files = parse_files(metadata)
    notes: list[str] = []
    selected: ZenodoFile | None = None
    downloaded: pathlib.Path | None = None
    video_path: pathlib.Path | None = None
    success = False

    print("Zenodo files:")
    for f in files:
        print(f"{f.name}\t{f.size}\t{f.url}")

    if args.list_only:
        notes.append("list-only mode; no file downloaded")
        report_path = write_report(outdir, files, None, None, None, True, notes)
        print(f"Report: {report_path}")
        return

    if args.download_first_video:
        selected = select_file(files)
        if selected is None:
            notes.append("No video or supported archive found in Zenodo file list")
        elif gb(selected.size) > args.max_download_gb:
            notes.append(
                f"Selected file exceeds max-download-gb: {gb(selected.size):.3f} GB > {args.max_download_gb:.3f} GB"
            )
        else:
            downloaded = download_file(selected, outdir)
            if selected.is_video:
                video_path = downloaded
                notes.append("Downloaded direct video file")
            else:
                extract_dir = extract_archive(downloaded, outdir)
                video_path = find_first_video(extract_dir)
                notes.append(f"Downloaded archive and extracted to {extract_dir}")
            if video_path is not None:
                video_path = link_or_copy_video(video_path)
                success = True
            else:
                notes.append("Could not automatically find a video after download/extraction")
    else:
        notes.append("No download action requested")

    report_path = write_report(outdir, files, selected, downloaded, video_path, success, notes)
    print(f"Report: {report_path}")
    if success:
        print(f"Video: {video_path}")
    else:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
