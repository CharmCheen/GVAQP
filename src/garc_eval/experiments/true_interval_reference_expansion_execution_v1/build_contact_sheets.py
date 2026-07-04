#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import pandas as pd

from common_review import OUT, append_progress, write_df, write_text


def run(cmd: list[str]) -> tuple[bool, str]:
    p = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return p.returncode == 0, p.stdout[-800:]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=OUT / "media_manifest.csv")
    args = parser.parse_args()
    if not args.manifest.exists():
        write_text(OUT / "media_export_report.md", "# Media Export Report\n\nNo media manifest exists; contact sheets not generated.")
        return
    manifest = pd.read_csv(args.manifest)
    statuses = []
    for r in manifest.itertuples(index=False):
        if getattr(r, "clip_export_status", "") != "OK" or not Path(str(r.clip_path)).exists():
            statuses.append("CLIP_MISSING")
            continue
        sheet = Path(str(r.sheet_path))
        if sheet.exists() and sheet.stat().st_size > 0:
            statuses.append("OK")
            continue
        ok, msg = run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(r.clip_path), "-vf", "fps=1/2,scale=320:-1,tile=5x4", "-frames:v", "1", "-q:v", "3", str(sheet)])
        statuses.append("OK" if ok else f"FAILED:{msg}")
    manifest["sheet_export_status"] = statuses
    write_df(manifest, OUT / "media_manifest.csv")
    ok_count = int((manifest["sheet_export_status"] == "OK").sum())
    report = OUT / "media_export_report.md"
    previous = report.read_text(encoding="utf-8") if report.exists() else "# Media Export Report\n"
    write_text(report, previous + f"\n\n## Contact Sheets\n\n- Contact sheets exported OK: `{ok_count}` / `{len(manifest)}`.\n")
    append_progress("build_contact_sheets", f"sheets_ok={ok_count}/{len(manifest)}")


if __name__ == "__main__":
    main()
