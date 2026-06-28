#!/usr/bin/env python3
from __future__ import annotations

import pandas as pd

from phase0_common import OUT_DIR, append_progress, attach_pseudo_events, build_pseudo_events, ensure_dirs, load_units


def main() -> None:
    ensure_dirs()
    units = load_units()
    events = build_pseudo_events(units)
    units = attach_pseudo_events(units, events)
    preferred = [
        "unit_id",
        "video_id",
        "clip_id",
        "start_time",
        "end_time",
        "duration",
        "proxy_score",
        "proxy_source",
        "score_source",
        "oracle_label",
        "oracle_source",
        "human_label",
        "event_id",
        "event_start",
        "event_end",
        "source_path",
        "has_event_boundary",
        "event_boundary_source",
    ]
    units = units[[c for c in preferred if c in units.columns]]
    units.to_csv(OUT_DIR / "data_audit/phase0_units.csv", index=False)
    events.to_csv(OUT_DIR / "data_audit/phase0_pseudo_events.csv", index=False)
    manifest = pd.DataFrame(
        [
            {
                "artifact": "phase0_units.csv",
                "rows": len(units),
                "oracle_positive_units": int(units["oracle_label"].sum()),
                "score_source_values": ";".join(sorted(units["score_source"].dropna().astype(str).unique())),
                "has_clean_event_boundaries": bool(units["has_event_boundary"].any()),
            },
            {
                "artifact": "phase0_pseudo_events.csv",
                "rows": len(events),
                "oracle_positive_units": int(events["num_positive_units"].sum()) if not events.empty else 0,
                "score_source_values": "",
                "has_clean_event_boundaries": False,
            },
        ]
    )
    manifest.to_csv(OUT_DIR / "data_manifest/phase0_manifest.csv", index=False)
    append_progress(
        "phase0 table",
        "python scripts/01_build_phase0_table.py",
        f"wrote {len(units)} units and {len(events)} pseudo-events",
        next_action="run SUPG/window stitch simulation",
    )


if __name__ == "__main__":
    main()
