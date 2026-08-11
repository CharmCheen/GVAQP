#!/usr/bin/env python3
"""Serve the blinded human-continuity primary annotation package locally.

The server intentionally reads only ``annotation_package/`` and the primary
case IDs.  It never loads the hidden population or C0/C1/K3 predictions.
Each click appends an immutable JSONL audit record; the latest record for a
case is the editable answer until all 40 primary cases have an answer.  At
completion the labels are frozen into a CSV plus SHA256 hash.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import secrets
import tempfile
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

LABELS = {"SAME_EVENT", "DIFFERENT_EVENTS", "ANCHOR_INVALID", "UNCERTAIN"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.public = self.root / "annotation_package" / "PRIMARY_BLINDED_CASES.json"
        self.labels = self.root / "HUMAN_LABELS_PRIMARY.jsonl"
        self.frozen = self.root / "HUMAN_LABELS_PRIMARY_FROZEN.csv"
        self.hash_file = self.root / "HUMAN_LABELS_PRIMARY_HASH.txt"
        self.state_path = self.root / "HUMAN_CONTINUITY_STATE.json"
        data = json.loads(self.public.read_text(encoding="utf-8"))
        self.cases = data["cases"]
        self.ids = [x["case_id"] for x in self.cases]
        if len(self.ids) != 40 or len(set(self.ids)) != 40:
            raise RuntimeError("expected exactly 40 unique blinded primary cases")
        if not self.labels.exists():
            raise RuntimeError("zero-label JSONL file is missing")

    def latest(self) -> dict[str, dict[str, Any]]:
        records: dict[str, dict[str, Any]] = {}
        for line in self.labels.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            x = json.loads(line)
            if x.get("case_id") not in self.ids or x.get("label") not in LABELS:
                raise RuntimeError("label audit contains invalid case or label")
            records[x["case_id"]] = x
        return records

    def state(self, session_id: str | None = None) -> dict[str, Any]:
        latest = self.latest()
        first = next((i for i, x in enumerate(self.ids) if x not in latest), 0)
        return {
            "completed": len(latest),
            "first_unlabeled_index": first,
            "latest": latest,
            "frozen": self.frozen.exists(),
            "session_id": session_id or secrets.token_urlsafe(16),
        }

    def append(self, record: dict[str, Any]) -> None:
        if self.frozen.exists():
            raise RuntimeError("primary labels are frozen; use a documented revision workflow")
        case_id, label = record.get("case_id"), record.get("label")
        if case_id not in self.ids or label not in LABELS:
            raise ValueError("unknown case or invalid label")
        comment = str(record.get("optional_comment", ""))
        if len(comment) > 500:
            raise ValueError("optional comment exceeds 500 characters")
        clean = {
            "case_id": case_id,
            "label": label,
            "annotated_at": now(),
            "annotation_session_id": str(record.get("annotation_session_id") or secrets.token_urlsafe(16)),
            "optional_comment": comment,
        }
        with self.labels.open("a", encoding="utf-8") as f:
            f.write(json.dumps(clean, ensure_ascii=False, sort_keys=True) + "\n")
            f.flush()
        if len(self.latest()) == len(self.ids):
            self.freeze()

    def freeze(self) -> None:
        if self.frozen.exists():
            return
        latest = self.latest()
        if set(latest) != set(self.ids):
            raise RuntimeError("cannot freeze incomplete primary labels")
        rows = [latest[x] for x in self.ids]
        fields = ["case_id", "label", "annotated_at", "annotation_session_id", "optional_comment"]
        with self.frozen.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader(); writer.writerows(rows)
        self.hash_file.write_text(sha256(self.frozen) + "\n", encoding="utf-8")
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        state.update({"status": "PRIMARY_LABELS_COMPLETE", "human_labels_observed": 40, "primary_label_hash": sha256(self.frozen)})
        self.state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def handler_for(store: Store):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(store.root / "annotation_package"), **kwargs)

        def json_response(self, payload: Any, status: int = 200) -> None:
            blob = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(blob))); self.end_headers(); self.wfile.write(blob)

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/api/cases":
                self.json_response({"cases": store.cases}); return
            if path == "/api/state":
                self.json_response(store.state()); return
            super().do_GET()

        def do_POST(self) -> None:
            if urlparse(self.path).path != "/api/label":
                self.json_response({"error": "not found"}, 404); return
            try:
                n = int(self.headers.get("Content-Length", "0"))
                if not 0 < n <= 4096:
                    raise ValueError("invalid request size")
                store.append(json.loads(self.rfile.read(n).decode("utf-8")))
                self.json_response({"ok": True, "state": store.state()})
            except (ValueError, json.JSONDecodeError, RuntimeError) as exc:
                self.json_response({"error": str(exc)}, 400)

        def log_message(self, fmt: str, *args: Any) -> None:
            print("annotation-ui:", fmt % args)
    return Handler


def self_test() -> None:
    """Test append/latest/resume logic in a disposable package, never real labels."""
    with tempfile.TemporaryDirectory(prefix="human-continuity-ui-") as tmp:
        root = Path(tmp); (root / "annotation_package").mkdir()
        cases = [{"case_id": f"CASE_{i:04d}", "query_text": "q", "clips": []} for i in range(1, 41)]
        (root / "annotation_package" / "PRIMARY_BLINDED_CASES.json").write_text(json.dumps({"cases": cases}), encoding="utf-8")
        (root / "HUMAN_LABELS_PRIMARY.jsonl").write_text("", encoding="utf-8")
        (root / "HUMAN_CONTINUITY_STATE.json").write_text(json.dumps({"status": "WAITING_FOR_HUMAN"}), encoding="utf-8")
        s = Store(root)
        s.append({"case_id": "CASE_0001", "label": "SAME_EVENT", "annotation_session_id": "test"})
        assert s.state()["completed"] == 1 and s.latest()["CASE_0001"]["label"] == "SAME_EVENT"
        s.append({"case_id": "CASE_0001", "label": "DIFFERENT_EVENTS", "annotation_session_id": "test"})
        assert s.state()["completed"] == 1 and s.latest()["CASE_0001"]["label"] == "DIFFERENT_EVENTS"
    print("SELF_TEST_PASS")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", type=Path, default=Path("outputs/human_continuity_validation_v1"))
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test(); return
    store = Store(args.package)
    server = ThreadingHTTPServer((args.host, args.port), handler_for(store))
    print(f"Blinded annotation UI: http://{args.host}:{args.port}/  (40 primary cases)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
