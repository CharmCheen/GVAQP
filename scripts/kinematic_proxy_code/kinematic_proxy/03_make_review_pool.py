#!/usr/bin/env python3
"""Build a pooled review set and lightweight HTML review page."""

import argparse
import html
import random
from collections import defaultdict
from pathlib import Path

from common import DEFAULT_CONFIG, ensure_output_dir, fail, load_config, read_csv, to_float, validate_base_paths, write_csv


METHODS = [
    ("count", "score_count"),
    ("naive", "score_naive"),
    ("kinematic", "score_kinematic"),
]


def top_rows(rows: list[dict], score_col: str, n: int) -> list[dict]:
    return sorted(rows, key=lambda r: to_float(r.get(score_col)), reverse=True)[:n]


def compute_ranks(rows: list[dict], score_col: str) -> dict[str, int]:
    ranked = sorted(rows, key=lambda r: to_float(r.get(score_col)), reverse=True)
    return {row["clip_id"]: rank for rank, row in enumerate(ranked, start=1)}


def make_html(output_dir: Path, pooled_rows: list[dict], score_rows: list[dict], top_n: int) -> Path:
    html_dir = output_dir / "review_html"
    html_dir.mkdir(parents=True, exist_ok=True)
    by_id = {r["clip_id"]: r for r in score_rows}
    total_clips = len(score_rows)
    ranks = {
        "rank_count": compute_ranks(score_rows, "score_count"),
        "rank_naive": compute_ranks(score_rows, "score_naive"),
        "rank_kinematic": compute_ranks(score_rows, "score_kinematic"),
    }
    method_counts = {method: 0 for method in ["kinematic", "naive", "count", "random"]}
    for row in pooled_rows:
        for method in row["selected_by"].split("|"):
            if method in method_counts:
                method_counts[method] += 1

    parts = [
        "<!doctype html>",
        "<html><head><meta charset='utf-8'>",
        "<title>Kinematic Proxy Review</title>",
        "<style>",
        "body{font-family:Arial,sans-serif;margin:24px;background:#f7f7f7;color:#222}",
        "h1,h2{margin:0 0 16px} h2{margin-top:32px}",
        ".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:16px}",
        ".card{background:white;border:1px solid #ddd;border-radius:6px;padding:12px}",
        ".summary{background:white;border:1px solid #ddd;border-radius:6px;padding:12px;margin:16px 0 20px}",
        ".summary-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:8px;font-size:13px}",
        ".warning{background:#ffecec;border:1px solid #d33;color:#9b0000;border-radius:6px;padding:10px;margin-top:12px;font-weight:bold}",
        "video{width:100%;background:#000;border-radius:4px}",
        ".meta{font-size:13px;line-height:1.45;margin-top:8px}",
        ".scores{font-family:monospace;font-size:12px}",
        "</style></head><body>",
        "<h1>Kinematic Proxy Review</h1>",
        "<div class='summary'>",
        "<div class='summary-grid'>",
        f"<div><b>total clips in proxy_scores</b><br>{total_clips}</div>",
        f"<div><b>review pool size</b><br>{len(pooled_rows)}</div>",
        f"<div><b>top_n</b><br>{top_n}</div>",
        f"<div><b>selected by kinematic</b><br>{method_counts['kinematic']}</div>",
        f"<div><b>selected by naive</b><br>{method_counts['naive']}</div>",
        f"<div><b>selected by count</b><br>{method_counts['count']}</div>",
        f"<div><b>selected by random</b><br>{method_counts['random']}</div>",
        "</div>",
    ]
    if top_n >= total_clips:
        parts.append(
            "<div class='warning'>WARNING: top_n &gt;= total clips, all methods may select the same clips. "
            "This review page is only a smoke test and not useful for method comparison.</div>"
        )
    parts.extend(["</div>", "<h2>Unified Review Grid</h2>", "<div class='grid'>"])

    for row in pooled_rows:
        full = by_id[row["clip_id"]]
        video_src = html.escape("../clips/" + Path(row["clip_path"]).name)
        clip_id = row["clip_id"]
        parts.append("<div class='card'>")
        parts.append(f"<video controls preload='metadata' src='{video_src}'></video>")
        parts.append("<div class='meta'>")
        parts.append(f"<div><b>{html.escape(clip_id)}</b></div>")
        parts.append(f"<div>{html.escape(full.get('start_time',''))}s - {html.escape(full.get('end_time',''))}s</div>")
        parts.append(f"<div>selected_by: {html.escape(row['selected_by'])}</div>")
        parts.append(
            "<div class='scores'>"
            f"score_count={html.escape(row['score_count'])} "
            f"score_naive={html.escape(row['score_naive'])} "
            f"score_kinematic={html.escape(row['score_kinematic'])}</div>"
        )
        parts.append(
            "<div class='scores'>"
            f"rank_count={ranks['rank_count'].get(clip_id, '')} "
            f"rank_naive={ranks['rank_naive'].get(clip_id, '')} "
            f"rank_kinematic={ranks['rank_kinematic'].get(clip_id, '')}</div>"
        )
        parts.append("</div></div>")
    parts.append("</div>")
    parts.append("</body></html>")

    out_path = html_dir / "index.html"
    out_path.write_text("\n".join(parts), encoding="utf-8")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Create pooled CSV and HTML for manual review.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    cfg = load_config(args.config)
    validate_base_paths(cfg)
    output_dir = ensure_output_dir(cfg)
    scores_path = output_dir / "proxy_scores.csv"
    rows = read_csv(scores_path)
    top_n = int(cfg.get("top_n", 50))
    if top_n <= 0:
        fail("top_n must be positive")

    selected: dict[str, dict] = {}
    selected_by: dict[str, set[str]] = defaultdict(set)
    for method, score_col in METHODS:
        for row in top_rows(rows, score_col, top_n):
            selected[row["clip_id"]] = row
            selected_by[row["clip_id"]].add(method)

    rng = random.Random(args.seed)
    random_rows = rows[:]
    rng.shuffle(random_rows)
    for row in random_rows[:top_n]:
        selected[row["clip_id"]] = row
        selected_by[row["clip_id"]].add("random")

    method_order = {"kinematic": 0, "naive": 1, "count": 2, "random": 3}
    pooled = []
    for clip_id, row in selected.items():
        methods = sorted(selected_by[clip_id], key=lambda m: method_order.get(m, 99))
        pooled.append(
            {
                "clip_id": clip_id,
                "clip_path": row["clip_path"],
                "selected_by": "|".join(methods),
                "score_count": row["score_count"],
                "score_naive": row["score_naive"],
                "score_kinematic": row["score_kinematic"],
                "label": "",
                "notes": "",
            }
        )
    pooled.sort(key=lambda r: (method_order.get(r["selected_by"].split("|")[0], 99), r["clip_id"]))

    out_path = output_dir / "review_pool.csv"
    write_csv(
        out_path,
        pooled,
        ["clip_id", "clip_path", "selected_by", "score_count", "score_naive", "score_kinematic", "label", "notes"],
    )
    html_path = make_html(output_dir, pooled, rows, top_n)
    print(f"review_pool_csv={out_path}")
    print(f"review_html={html_path}")
    print(f"review_pool_size={len(pooled)}")


if __name__ == "__main__":
    main()
