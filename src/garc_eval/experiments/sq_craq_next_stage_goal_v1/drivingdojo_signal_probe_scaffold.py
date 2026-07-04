from __future__ import annotations

import os
from pathlib import Path

from common_io import OUT, ROOT, md_table, script_stub, write_text

PART = OUT / "drivingdojo_signal_probe_v1"


def local_inventory() -> list[Path]:
    env = os.environ.get("DRIVINGDOJO_ROOT")
    candidates = [
        ROOT / "data/DrivingDojo",
        ROOT / "datasets/DrivingDojo",
        ROOT / "DrivingDojo",
        ROOT / "DrivingDojo-mini",
        ROOT / "datasets/DrivingDojo-mini",
    ]
    if env:
        candidates.insert(0, Path(env))
    rows = []
    found = []
    for p in candidates:
        exists = p.exists()
        if exists:
            found.append(p)
        nfiles = sum(1 for _ in p.rglob("*")) if exists and p.is_dir() else 0
        rows.append({"path": str(p), "exists": exists, "shallow_file_count": nfiles, "role": "local DrivingDojo candidate root"})
    import pandas as pd

    df = pd.DataFrame(rows)
    write_text(PART / "local_drivingdojo_inventory.md", "# Local DrivingDojo Inventory\n\nNo downloads were attempted.\n\n" + md_table(df, 20))
    return found


def docs(found: list[Path]) -> None:
    write_text(
        PART / "signal_requirements.md",
        """# Signal Requirements

DrivingDojo should be used as a signal-design corpus, not as the final AQP benchmark. The needed signal is answer-compatible: it must separate intervals that answer `O_enter_ego_path_v0` from high-score hard negatives inside the same candidate bin.

Candidate signal families:
- track-level interaction
- lateral displacement
- bbox center trajectory
- bbox area expansion
- object enters ego-center region
- multi-object proximity
- temporal consistency
- inside-outside contrast
- boundary sharpness
- hard-negative suppression
""",
    )
    scripts = PART / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    script_stub(scripts / "prepare_drivingdojo_manifest.py", "Prepare DrivingDojo manifest", "Scan local metadata and produce a clip manifest. No downloads.")
    script_stub(scripts / "extract_yolo_tracking_features.py", "Extract YOLO/tracking features", "Dry-run scaffold only; future execution must explicitly authorize model inference.")
    script_stub(scripts / "build_interval_signal_features.py", "Build interval signal features", "Aggregate existing per-frame/track features into interval-level cheap signals.")
    script_stub(scripts / "evaluate_signal_qualification.py", "Evaluate signal qualification", "Evaluate AUC/AP/top-k enrichment against a supplied reference; no label fabrication.")
    write_text(
        PART / "pipeline_scaffold_report.md",
        f"""# Pipeline Scaffold Report

Generated dry-run scaffold scripts under `{scripts.relative_to(ROOT)}`.

Local data roots found: `{len(found)}`. No model inference or downloads were run.
""",
    )
    write_text(
        PART / "DRIVINGDOJO_SIGNAL_PROBE_README.md",
        """# DrivingDojo Signal Probe

Default mode is dry-run. The probe should start with 200-500 clips only after data access is explicit. Use existing local YOLO/track outputs if present; otherwise do not run heavy models from this scaffold.
""",
    )


def final_report(found: list[Path]) -> None:
    write_text(
        PART / "FINAL_REPORT.md",
        f"""# DrivingDojo Signal Probe V1

## Answers

1. DrivingDojo's role is signal-design support for SQ-CRAQ, not the final AQP benchmark.
2. It is not a final benchmark because current claims remain VLM-oracle-relative and interval-reference limited; DrivingDojo should help design answer-compatible cheap signals.
3. Needed fields/labels: video id, clip boundaries, object tracks, bbox center/area trajectories, interaction labels or reviewable event intervals, and grouped source-video metadata.
4. Next probe: 200-500 clips, dry-run manifest first, then use existing local features if available.
5. Do not directly full-download or full-run YOLO because the current bottleneck is method/reference qualification, and heavy perception runs need explicit authorization.

Local DrivingDojo roots found: `{len(found)}`.
""",
    )


def main() -> None:
    PART.mkdir(parents=True, exist_ok=True)
    found = local_inventory()
    docs(found)
    final_report(found)


if __name__ == "__main__":
    main()
