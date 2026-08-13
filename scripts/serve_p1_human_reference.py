#!/usr/bin/env python3
"""Local server for the P1 blinded human temporal-event reference package."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "outputs/gvaqp_long_horizon_p1_p3_v1/human_reference_package"
LABELS = PACKAGE / "HUMAN_EVENT_LABELS.jsonl"

INDEX = """<!doctype html><meta charset=utf-8><title>P1 independent event annotation</title><style>body{font:16px system-ui;max-width:1000px;margin:2rem auto}video{width:100%;max-height:58vh;background:#111}textarea,input{font:inherit;padding:.4rem}textarea{width:100%;height:9rem}button{padding:.6rem 1rem;margin:.3rem}#status{white-space:pre-wrap;color:#073}</style><h1>P1 independent temporal-event annotation</h1><p id=meta></p><video id=video controls></video><h2 id=title></h2><p id=query></p><p>Annotator ID: <input id=annotator placeholder="e.g. annotator_1"></p><p>Enter one event per line as <code>start_sec,end_sec,boundary_ambiguous(true|false)</code>. Use an empty list for no event.</p><textarea id=events placeholder="120.5,135.2,false"></textarea><br><button onclick=save()>Save case</button><button onclick=prev()>Previous</button><button onclick=next()>Next</button><p id=status></p><script>let cases=[],i=0;const q=s=>document.querySelector(s);async function init(){cases=await (await fetch('/api/cases')).json();show()}function show(){let c=cases[i];q('#meta').textContent=`Case ${i+1}/${cases.length}: ${c.case_id}`;q('#video').src=c.video_url;q('#title').textContent=c.query_title;q('#query').textContent=c.query_definition;q('#events').value='';q('#status').textContent=''}function parse(){let t=q('#events').value.trim();if(!t)return [];return t.split(/\\n+/).map((x,n)=>{let a=x.split(',').map(y=>y.trim());if(a.length!==3||!isFinite(+a[0])||!isFinite(+a[1])||+a[1]<=+a[0]||!['true','false'].includes(a[2]))throw Error(`invalid line ${n+1}`);return {event_exists:true,start_time:+a[0],end_time:+a[1],boundary_ambiguous:a[2]==='true'}})}async function save(){try{let c=cases[i],annotator=q('#annotator').value.trim();if(!annotator)throw Error('enter annotator ID');let events=parse();let body={annotator_id:annotator,case_id:c.case_id,video_id:c.video_id,query_id:c.query_id,event_exists:events.length>0,events};let r=await fetch('/api/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(!r.ok)throw Error(await r.text());q('#status').textContent='Saved. You may revise this case before adjudication.'}catch(e){q('#status').textContent='Error: '+e.message}}function next(){if(i<cases.length-1){i++;show()}}function prev(){if(i>0){i--;show()}}init()</script>"""

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw): super().__init__(*a, directory=str(ROOT), **kw)
    def do_GET(self):
        if self.path == "/":
            b = INDEX.encode(); self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b); return
        if self.path == "/api/cases":
            b = (PACKAGE / "ANNOTATOR_VIEW_CASES.json").read_bytes(); self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b); return
        super().do_GET()
    def do_POST(self):
        if self.path != "/api/save": self.send_error(404); return
        try:
            n=int(self.headers["Content-Length"]); row=json.loads(self.rfile.read(n)); cases={x["case_id"]:x for x in json.loads((PACKAGE / "ANNOTATOR_VIEW_CASES.json").read_text())}
            c=cases[row["case_id"]]
            if not all(row.get(k)==c[k] for k in ("video_id","query_id")): raise ValueError("case identity mismatch")
            if not isinstance(row.get("annotator_id"),str) or not row["annotator_id"].strip(): raise ValueError("missing annotator")
            if not isinstance(row.get("event_exists"),bool) or not isinstance(row.get("events"),list): raise ValueError("invalid event payload")
            if row["event_exists"] != bool(row["events"]): raise ValueError("event_exists mismatch")
            for e in row["events"]:
                if not (e.get("event_exists") is True and isinstance(e.get("boundary_ambiguous"),bool) and 0 <= float(e["start_time"]) < float(e["end_time"]) <= float(c["duration_sec"])): raise ValueError("invalid event interval")
            row["saved_at_utc"]=datetime.now(timezone.utc).isoformat()
            with LABELS.open("a",encoding="utf-8") as f: f.write(json.dumps(row,sort_keys=True)+"\\n")
            self.send_response(HTTPStatus.NO_CONTENT); self.end_headers()
        except Exception as e: self.send_error(HTTPStatus.BAD_REQUEST, str(e))

if __name__ == "__main__":
    p=argparse.ArgumentParser(); p.add_argument("--port",type=int,default=8766); a=p.parse_args()
    if not PACKAGE.exists(): raise SystemExit("run build_p1_human_reference_package.py first")
    print(f"P1 annotation server: http://127.0.0.1:{a.port}/")
    ThreadingHTTPServer(("127.0.0.1",a.port),Handler).serve_forever()
