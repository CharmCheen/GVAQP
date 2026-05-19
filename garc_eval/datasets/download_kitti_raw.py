"""Download a KITTI Raw zip and build frame metadata from an image sequence."""

from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import urllib.parse
import urllib.request
import zipfile

import pandas as pd


def _download(url: str, dest: pathlib.Path, force: bool) -> pathlib.Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not force:
        return dest
    tmp = dest.with_suffix(dest.suffix + ".part")
    if tmp.exists():
        tmp.unlink()
    with urllib.request.urlopen(url, timeout=60) as response, tmp.open("wb") as fh:
        shutil.copyfileobj(response, fh)
    tmp.replace(dest)
    return dest


def _extract(zip_path: pathlib.Path, outdir: pathlib.Path, force: bool) -> pathlib.Path:
    extract_dir = outdir / zip_path.stem
    marker = extract_dir / ".extract_complete"
    if marker.exists() and not force:
        return extract_dir
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_dir)
    marker.write_text("ok\n", encoding="utf-8")
    return extract_dir


def _find_images(extract_dir: pathlib.Path, sequence_name: str, camera: str) -> list[pathlib.Path]:
    date = sequence_name.split("_drive_")[0]
    preferred = extract_dir / date / sequence_name / camera / "data"
    if preferred.exists():
        images = sorted(preferred.glob("*.png"))
        if images:
            return images

    candidates = []
    for data_dir in extract_dir.rglob("data"):
        if data_dir.parent.name == camera:
            candidates.extend(data_dir.glob("*.png"))
    return sorted(candidates, key=lambda p: str(p).lower())


def _link_or_copy(src: pathlib.Path, dest: pathlib.Path, force: bool) -> pathlib.Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() or dest.is_symlink():
        if force:
            dest.unlink()
        else:
            return dest
    try:
        dest.symlink_to(src.resolve())
    except OSError:
        shutil.copy2(src, dest)
    return dest


def _write_report(
    *,
    url: str,
    zip_path: pathlib.Path,
    extract_dir: pathlib.Path,
    camera: str,
    total_frames: int,
    selected_frames: int,
    frames_link_dir: pathlib.Path,
    frame_table: pathlib.Path,
    success: bool,
    notes: list[str],
) -> pathlib.Path:
    output_dir = frame_table.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "dataset_download_report.md"
    lines = [
        "# KITTI Raw Dataset Download Report",
        "",
        f"- URL: {url}",
        f"- zip path: {zip_path}",
        f"- zip size bytes: {zip_path.stat().st_size if zip_path.exists() else 'missing'}",
        f"- extract dir: {extract_dir}",
        f"- camera: {camera}",
        f"- total frames found: {total_frames}",
        f"- selected frames: {selected_frames}",
        f"- frames link dir: {frames_link_dir}",
        f"- frame table: {frame_table}",
        f"- timestamp assumption: frame_idx / 10.0 seconds (KITTI Raw nominal 10 FPS)",
        f"- success: {success}",
        "",
        "## Notes",
        "",
    ]
    lines.extend(f"- {note}" for note in notes)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def build_frame_metadata(
    *,
    url: str,
    outdir: str,
    sequence_id: str,
    camera: str,
    max_frames: int,
    output_frame_table: str,
    frames_link_dir: str,
    force: bool,
) -> pathlib.Path:
    outdir_path = pathlib.Path(outdir)
    frames_link_path = pathlib.Path(frames_link_dir)
    frame_table_path = pathlib.Path(output_frame_table)

    filename = pathlib.Path(urllib.parse.urlparse(url).path).name
    if not filename:
        raise ValueError(f"Could not derive filename from URL: {url}")
    zip_path = outdir_path / filename

    notes: list[str] = []
    zip_path = _download(url, zip_path, force)
    notes.append("Downloaded zip or reused existing file")
    extract_dir = _extract(zip_path, outdir_path, force)
    notes.append("Extracted zip or reused existing extraction")

    sequence_name = pathlib.Path(zip_path.stem).name
    images = _find_images(extract_dir, sequence_name, camera)
    total_frames = len(images)
    if total_frames == 0:
        report_path = _write_report(
            url=url,
            zip_path=zip_path,
            extract_dir=extract_dir,
            camera=camera,
            total_frames=0,
            selected_frames=0,
            frames_link_dir=frames_link_path,
            frame_table=frame_table_path,
            success=False,
            notes=notes + [f"No {camera}/data/*.png images found"],
        )
        print(f"Report: {report_path}")
        raise RuntimeError(f"No {camera}/data/*.png images found under {extract_dir}")

    selected = images[:max_frames] if max_frames is not None and max_frames > 0 else images
    rows = []
    for i, src in enumerate(selected):
        dest = frames_link_path / src.name
        linked = _link_or_copy(src, dest, force)
        rows.append(
            {
                "id": i,
                "video_id": sequence_id,
                "frame_idx": int(src.stem),
                "timestamp": round(int(src.stem) / 10.0, 4),
                "image_path": str(linked),
            }
        )

    df = pd.DataFrame(rows)
    frame_table_path.parent.mkdir(parents=True, exist_ok=True)
    if frame_table_path.suffix == ".parquet":
        df.to_parquet(frame_table_path, index=False)
    else:
        df.to_csv(frame_table_path, index=False)

    report_path = _write_report(
        url=url,
        zip_path=zip_path,
        extract_dir=extract_dir,
        camera=camera,
        total_frames=total_frames,
        selected_frames=len(df),
        frames_link_dir=frames_link_path,
        frame_table=frame_table_path,
        success=True,
        notes=notes,
    )
    print(f"Found {total_frames} frames; selected {len(df)}")
    print(f"Saved frame table: {frame_table_path}")
    print(f"Report: {report_path}")
    return frame_table_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Download KITTI Raw and build frame metadata")
    parser.add_argument("--url", required=True)
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--sequence-id", required=True)
    parser.add_argument("--camera", default="image_02")
    parser.add_argument("--max-frames", type=int, default=1000)
    parser.add_argument("--output-frame-table", required=True)
    parser.add_argument("--frames-link-dir", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    build_frame_metadata(
        url=args.url,
        outdir=args.outdir,
        sequence_id=args.sequence_id,
        camera=args.camera,
        max_frames=args.max_frames,
        output_frame_table=args.output_frame_table,
        frames_link_dir=args.frames_link_dir,
        force=args.force,
    )


if __name__ == "__main__":
    main()
