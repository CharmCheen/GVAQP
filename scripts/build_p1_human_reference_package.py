#!/usr/bin/env python3
"""Create the blinded independent P1 temporal-event annotation package.

It creates no labels and reads no semantic-oracle outcome or event reference.
The full source videos are deliberately served in place: duplicating multi-GB
videos into an annotation package would add cost without increasing blinding.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/gvaqp_long_horizon_p1_p3_v1/human_reference_package"
VIDEOS = {
    "DALI": {"file": "data/realcam/dali.mp4", "duration_sec": 5665.535},
    "HANGZHOU": {"file": "data/realcam/hangzhou.mp4", "duration_sec": 5600.566},
    "WUHAN": {"file": "data/realcam/wuhan.mp4", "duration_sec": 3462.930},
}
QUERIES = [
    {
        "query_id": "Q_DRIVER_RESPONSE_V1",
        "title": "Driver response required",
        "definition": "An attentive ego driver needs a noticeable slowdown, braking action, or avoidance maneuver because of visible conditions. Relevant causes include a road user entering or threatening the ego path, a suddenly slowing or stopped lead vehicle, traffic control requiring a marked response, or a visible obstacle/road condition requiring a marked speed or path change. Exclude normal steady driving, ordinary following without a marked response, distant hazards, and a response completed before the moment shown.",
    },
    {
        "query_id": "Q_VULNERABLE_ROAD_USER_CONFLICT_V1",
        "title": "Vulnerable-road-user conflict",
        "definition": "A pedestrian, cyclist, motorcyclist, or scooter rider visibly enters, crosses, or occupies the ego vehicle's immediate travel path such that the ego driver must yield, brake, slow markedly, or steer to avoid conflict. Exclude road users that remain clearly separated from the ego path, ordinary adjacent traffic, or a conflict already completed before the displayed moment.",
    },
]


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main() -> None:
    if OUT.exists() and (OUT / "HUMAN_REFERENCE_PROTOCOL.json").exists():
        raise RuntimeError(f"refusing to overwrite frozen package: {OUT}")
    if OUT.exists():
        expected_partial = {"ANNOTATOR_VIEW_CASES.json", "QUERY_DEFINITIONS.md", "ANNOTATION_GUIDE.md"}
        observed = {p.name for p in OUT.iterdir()}
        if observed != expected_partial:
            raise RuntimeError(f"unexpected incomplete-package contents: {sorted(observed)}")
    for video in VIDEOS.values():
        path = ROOT / video["file"]
        if not path.exists() or path.stat().st_size <= 0:
            raise RuntimeError(f"source video unavailable: {path}")
    OUT.mkdir(parents=True, exist_ok=True)
    cases = []
    for video_id, video in VIDEOS.items():
        for query in QUERIES:
            cases.append({"case_id": f"REF_{video_id}_{query['query_id']}", "video_id": video_id, "query_id": query["query_id"], "video_url": "/" + video["file"], "duration_sec": video["duration_sec"], "query_title": query["title"], "query_definition": query["definition"]})
    (OUT / "ANNOTATOR_VIEW_CASES.json").write_text(json.dumps(cases, indent=2) + "\n")
    (OUT / "QUERY_DEFINITIONS.md").write_text("# Frozen P1 query definitions\n\n" + "\n\n".join(f"## {q['query_id']} — {q['title']}\n\n{q['definition']}" for q in QUERIES) + "\n")
    (OUT / "ANNOTATION_GUIDE.md").write_text("""# Independent temporal-event annotation guide

For each video/query case, watch the full video (you may seek freely) and record every temporal episode that satisfies the frozen query definition. An event is a maximal continuous semantic episode, not a fixed 10-second unit. Do not use model predictions, candidate scores, previous event references, selection traces, or any method results.

For every event, record: `event_exists`, `start_time`, `end_time`, and whether either boundary is ambiguous. Use seconds as shown by the player. When a boundary is uncertain, record your best estimate and set `boundary_ambiguous=true`; do not delete a clearly present event merely because its edge is gradual. If no event occurs, submit an empty event list and `event_exists=false`.

Each annotator must complete all six cases independently. A second annotator should use a different `annotator_id`; adjudication is performed only after both submissions are frozen. The interface never displays semantic-oracle outcomes, C1/K3 events, proxy scores, trace identities, or study results.
""")
    protocol = {"protocol_id": "P1_INDEPENDENT_HUMAN_EVENT_REFERENCE_V1", "status": "FROZEN_BEFORE_HUMAN_LABELS", "reference_is_independent_of": ["C0", "C1", "K3", "proxy policies", "geometry hypothesis", "semantic oracle outcomes", "event-recovery results"], "annotation_unit": "maximal human-defined temporal event", "required_fields": ["query_id", "video_id", "event_exists", "start_time", "end_time", "boundary_ambiguous"], "annotators_recommended": 2, "adjudication": "after two independent complete submissions; preserve original records", "cases": [{"video_id": v, "query_id": q["query_id"]} for v in VIDEOS for q in QUERIES], "source_videos": {v: {"path": d["file"], "sha256": sha(ROOT/d["file"]), "duration_sec": d["duration_sec"]} for v,d in VIDEOS.items()}, "prohibitions": ["redefine query after annotation begins", "modify boundary to improve an algorithm", "delete difficult cases", "reveal method results to annotators"]}
    protocol["protocol_sha256"] = hashlib.sha256(json.dumps(protocol, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    (OUT / "HUMAN_REFERENCE_PROTOCOL.json").write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    (OUT / "HUMAN_EVENT_LABELS.jsonl").write_text("")
    (OUT / "README.md").write_text("# P1 independent human reference package\n\nThis is a six-cluster (three video × two query) blinded event-annotation package. Launch it with:\n\n```bash\npython scripts/serve_p1_human_reference.py\n```\n\nThen open `http://127.0.0.1:8766/`.\n")
    print(json.dumps({"status": "PACKAGE_FROZEN", "cases": len(cases), "output": str(OUT), "protocol": protocol["protocol_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
