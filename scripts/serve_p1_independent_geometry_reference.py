#!/usr/bin/env python3
"""Serve the blinded P1 independent human-event annotation package locally."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "outputs/p1_independent_geometry_replication_v1"
CASES = PACKAGE / "ANNOTATOR_VIEW_CASES.json"
LABELS = PACKAGE / "HUMAN_EVENT_LABELS.jsonl"
QUERY_DEFINITIONS = PACKAGE / "QUERY_DEFINITIONS.md"


def blinded_cases() -> list[dict]:
    """Attach the authoritative frozen definitions, never stale package summaries."""
    text = QUERY_DEFINITIONS.read_text()
    driver = text.split("## Q_DRIVER_RESPONSE_V1", 1)[1].split("## Q_VULNERABLE", 1)[0].strip()
    vulnerable = text.split("## Q_VULNERABLE_ROAD_USER_CONFLICT_V1", 1)[1].split("## Rules common", 1)[0].strip()
    common = text.split("## Rules common to both queries", 1)[1].strip()
    definitions = {
        "Q_DRIVER_RESPONSE_V1": driver + "\n\nRules common to both queries\n" + common,
        "Q_VULNERABLE_ROAD_USER_CONFLICT_V1": vulnerable + "\n\nRules common to both queries\n" + common,
    }
    guide = (PACKAGE / "ANNOTATION_GUIDE.md").read_text()
    cases = json.loads(CASES.read_text())
    for case in cases:
        case["query_definition"] = definitions[case["query_id"]] + "\n\nFrozen annotation guide\n" + guide
        case["annotation_guide"] = guide
    return cases

INDEX = r"""<!doctype html><meta charset="utf-8"><title>GVAQP P1 blinded event annotation</title>
<style>body{font:16px system-ui;max-width:1050px;margin:2rem auto;padding:0 1rem}video{width:100%;max-height:58vh;background:#111}textarea,input{font:inherit;padding:.45rem}textarea{width:100%;height:10rem}button{padding:.6rem 1rem;margin:.3rem}#status{white-space:pre-wrap;color:#064}code{background:#eee;padding:.1rem .25rem}</style>
<h1>GVAQP P1 independent temporal-event annotation</h1><p><strong>Blinded:</strong> this interface exposes no proxy, trace, oracle, C1/K3, geometry, pair, or result data.</p><p id="meta"></p><video id="video" controls preload="metadata"></video><p>Current time: <strong id="clock">0.000</strong>s <button onclick="markStart()">Mark start</button><button onclick="markEnd()">Add event to current time</button></p><h2 id="title"></h2><p id="query"></p><p>Annotator ID: <input id="annotator" placeholder="ANNOTATOR_A or ANNOTATOR_B" onchange="restore()"></p><p>One event per line: <code>start,end,boundary_ambiguous,semantic_ambiguity,optional note</code>. Leave empty only for an explicit no-event case.</p><textarea id="events" placeholder="120.5,135.2,false,false,pedestrian crosses ego path" oninput="draft()"></textarea><br><button onclick="save()">Save append-only revision</button><button onclick="deleteLast()">Delete last event</button><button onclick="prev()">Previous</button><button onclick="next()">Next</button><p id="completion"></p><p id="status"></p>
<script>let cases=[],i=0,startMark=null;const q=s=>document.querySelector(s),key=()=>`p1b:${q('#annotator').value.trim()}:${cases[i]?.case_id}`;async function init(){cases=await (await fetch('/api/cases')).json();q('#video').ontimeupdate=()=>q('#clock').textContent=q('#video').currentTime.toFixed(3);show()}function show(){const c=cases[i];q('#meta').textContent=`Case ${i+1}/${cases.length}: ${c.case_id}`;q('#video').src=c.video_url;q('#title').textContent=c.query_id;q('#query').textContent=c.query_definition;q('#status').textContent='';restore()}function restore(){q('#events').value=localStorage.getItem(key())||'';completion()}function draft(){localStorage.setItem(key(),q('#events').value);completion()}function completion(){const a=q('#annotator').value.trim();const n=cases.filter(c=>localStorage.getItem(`p1b:saved:${a}:${c.case_id}`)==='yes').length;q('#completion').textContent=a?`This annotator saved ${n}/6 cases.`:'Enter a stable annotator ID.'}function parse(){const t=q('#events').value.trim();if(!t)return [];return t.split(/\n+/).map((line,n)=>{const a=line.split(',').map(x=>x.trim());if(a.length<4||!isFinite(+a[0])||!isFinite(+a[1])||+a[1]<=+a[0]||!['true','false'].includes(a[2])||!['true','false'].includes(a[3]))throw Error(`invalid line ${n+1}`);return{start_time:+a[0],end_time:+a[1],boundary_ambiguous:a[2]==='true',semantic_ambiguity:a[3]==='true',optional_note:a.slice(4).join(',')}})}function markStart(){startMark=q('#video').currentTime;q('#status').textContent=`Start marked at ${startMark.toFixed(3)}s`}function markEnd(){if(startMark===null){alert('Mark start first');return}const end=q('#video').currentTime;if(end<=startMark){alert('End must follow start');return}const line=`${startMark.toFixed(3)},${end.toFixed(3)},false,false,`;q('#events').value+=(q('#events').value.trim()?'\n':'')+line;startMark=null;draft()}function deleteLast(){let a=q('#events').value.split(/\n/);a.pop();q('#events').value=a.join('\n');draft()}async function save(){try{const c=cases[i],annotator=q('#annotator').value.trim();if(!['ANNOTATOR_A','ANNOTATOR_B'].includes(annotator))throw Error('use exactly ANNOTATOR_A or ANNOTATOR_B');const events=parse();const body={annotator_id:annotator,case_id:c.case_id,video_id:c.video_id,query_id:c.query_id,event_exists:events.length>0,events};const r=await fetch('/api/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(!r.ok)throw Error(await r.text());localStorage.setItem(`p1b:saved:${annotator}:${c.case_id}`,'yes');draft();q('#status').textContent='Saved append-only revision. Your local draft remains available for resume.'}catch(e){q('#status').textContent='Error: '+e.message}}function next(){if(i<cases.length-1){i++;show()}}function prev(){if(i>0){i--;show()}}init()</script>"""


class Handler(BaseHTTPRequestHandler):

    def send_bytes(self, payload: bytes, content_type: str) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def send_video(self, path: Path) -> None:
        size = path.stat().st_size
        start, end = 0, size - 1
        header = self.headers.get("Range")
        if header:
            spec = header.removeprefix("bytes=").split(",", 1)[0]
            left, right = spec.split("-", 1)
            start = int(left) if left else 0
            end = min(int(right), size - 1) if right else size - 1
            if not (0 <= start <= end < size):
                self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                return
            self.send_response(HTTPStatus.PARTIAL_CONTENT)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        else:
            self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        with path.open("rb") as handle:
            handle.seek(start)
            remaining = end - start + 1
            while remaining:
                block = handle.read(min(1 << 20, remaining))
                if not block:
                    break
                self.wfile.write(block)
                remaining -= len(block)

    def do_GET(self) -> None:
        if self.path == "/":
            self.send_bytes(INDEX.encode(), "text/html; charset=utf-8")
            return
        if self.path == "/api/cases":
            self.send_bytes(json.dumps(blinded_cases()).encode(), "application/json")
            return
        video_paths = {item["video_url"]: ROOT / item["video_path"] for item in blinded_cases()}
        if self.path in video_paths:
            self.send_video(video_paths[self.path])
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_HEAD(self) -> None:
        video_paths = {item["video_url"]: ROOT / item["video_path"] for item in blinded_cases()}
        if self.path not in video_paths:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        path = video_paths[self.path]
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Length", str(path.stat().st_size))
        self.end_headers()

    def do_POST(self) -> None:
        if self.path != "/api/save":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            size = int(self.headers["Content-Length"])
            row = json.loads(self.rfile.read(size))
            cases = {item["case_id"]: item for item in blinded_cases()}
            case = cases[row["case_id"]]
            if any(row.get(key) != case[key] for key in ("video_id", "query_id")):
                raise ValueError("case identity mismatch")
            annotator = row.get("annotator_id")
            if annotator not in {"ANNOTATOR_A", "ANNOTATOR_B"}:
                raise ValueError("annotator_id must be ANNOTATOR_A or ANNOTATOR_B")
            events = row.get("events")
            if not isinstance(events, list) or row.get("event_exists") is not bool(events):
                raise ValueError("event_exists/event list mismatch")
            for index, event in enumerate(events, 1):
                start, end = float(event["start_time"]), float(event["end_time"])
                if not (0 <= start < end <= float(case["duration_sec"])):
                    raise ValueError("event interval outside video")
                if not isinstance(event.get("boundary_ambiguous"), bool) or not isinstance(event.get("semantic_ambiguity"), bool):
                    raise ValueError("ambiguity fields must be boolean")
                event["annotation_id"] = f"{case['case_id']}::{annotator}::E{index:03d}"
                event["event_index"] = index
                event["video_id"] = case["video_id"]
                event["query_id"] = case["query_id"]
                event["annotator_id"] = annotator
                event["adjudication_status"] = "UNADJUDICATED_INDEPENDENT"
            row["saved_at_utc"] = datetime.now(timezone.utc).isoformat()
            row["protocol_hash"] = json.loads(
                (PACKAGE / "HUMAN_REFERENCE_PROTOCOL.json").read_text()
            )["protocol_hash"]
            with LABELS.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
            self.send_response(HTTPStatus.NO_CONTENT)
            self.end_headers()
        except Exception as error:
            self.send_error(HTTPStatus.BAD_REQUEST, str(error))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8767)
    args = parser.parse_args()
    if not CASES.exists() or not LABELS.exists():
        raise SystemExit("run prepare_p1_independent_geometry_replication.py first")
    print(f"P1 blinded annotation server: http://127.0.0.1:{args.port}/")
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
