#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import pandas as pd

from local_candidate_common import KIN_CLIPS, KIN_HUMAN, KIN_LABELS, KIN_PROXY, OUT, ROOT, append_progress, ensure_dirs, parse_clip_times_from_name, video_meta


def main() -> int:
    ensure_dirs()
    clips = pd.read_csv(KIN_CLIPS)
    labels = pd.read_csv(KIN_LABELS)
    proxy = pd.read_csv(KIN_PROXY)
    human = pd.read_csv(KIN_HUMAN) if KIN_HUMAN.exists() else pd.DataFrame()
    human_by_clip = {row.clip_id: row for row in human.itertuples(index=False)} if not human.empty else {}
    labels_by_clip = {row.clip_id: row for row in labels.itertuples(index=False)}
    proxy_by_clip = {row.clip_id: row for row in proxy.itertuples(index=False)}

    rows = []
    for row in clips.itertuples(index=False):
        lab = labels_by_clip.get(row.clip_id)
        prox = proxy_by_clip.get(row.clip_id)
        hum = human_by_clip.get(row.clip_id)
        oracle_label = int(getattr(lab, "label_conservative_positive", 0)) if lab is not None else ""
        human_label = getattr(hum, "human_label_conservative_positive", "") if hum is not None else ""
        rows.append(
            {
                "dataset": "local_kinematic_proxy_debug",
                "video_id": row.video_id,
                "unit_id": row.clip_id,
                "source_video_path": str(ROOT / "try_or_no/videos/realcartest_5k.mp4"),
                "start_time": row.start_time,
                "end_time": row.end_time,
                "duration": float(row.end_time) - float(row.start_time),
                "source_clip_path": row.clip_path,
                "label_source": "human_audit_conservative" if human_label != "" else "conservative_vlm_pseudo_oracle",
                "oracle_label": oracle_label,
                "human_label": human_label,
                "proxy_score_existing": getattr(prox, "score_kinematic", "") if prox is not None else "",
                "has_clean_event_boundary": False,
                "notes": "local-pseudo debugging unit; no clean event boundary; label is not human-truth event interval",
            }
        )
    units = pd.DataFrame(rows)
    units.to_csv(OUT / "tables/local_smoke_units.csv", index=False)

    full_rows = []
    for path in [ROOT / "try_or_no/videos/realcartest_5k.mp4", ROOT / "try_or_no/videos/test.mov", ROOT / "datasets/casq_external/nexar/videos_smoke/positive/00822.mp4"]:
        if path.exists():
            meta = video_meta(path)
            full_rows.append({"video_id": path.stem, "source_video_path": str(path), **meta})
    pd.DataFrame(full_rows).to_csv(OUT / "tables/local_full_video_selection.csv", index=False)
    pd.DataFrame(
        [
            {"input_name": "kinematic_proxy_clips", "path": str(KIN_CLIPS), "rows": len(clips)},
            {"input_name": "kinematic_proxy_labels", "path": str(KIN_LABELS), "rows": len(labels)},
            {"input_name": "kinematic_proxy_scores", "path": str(KIN_PROXY), "rows": len(proxy)},
            {"input_name": "kinematic_human_audit", "path": str(KIN_HUMAN), "rows": len(human)},
        ]
    ).to_csv(OUT / "data_manifest/input_manifest.csv", index=False)
    append_progress("build_smoke_dataset", "python scripts/10_build_local_smoke_dataset.py", f"units={len(units)}, full_videos={len(full_rows)}", next_action="extract frames")
    print(f"units={len(units)} full_videos={len(full_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

