"""Calibrate a count threshold from oracle count scores."""

from __future__ import annotations

import argparse
import json
import pathlib

import pandas as pd


def _load_scores(path: str) -> pd.DataFrame:
    score_path = pathlib.Path(path)
    if score_path.suffix == ".parquet":
        df = pd.read_parquet(score_path)
    else:
        df = pd.read_csv(score_path)
    if "oracle_count" in df.columns:
        df = df.rename(columns={"oracle_count": "count"})
    if "oracle_score" in df.columns:
        df = df.rename(columns={"oracle_score": "score"})
    required = {"id", "count"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"oracle scores missing columns {missing}; got {list(df.columns)}")
    return df


def _choose(rows: list[dict], low: float, high: float, selected_by: str) -> dict | None:
    candidates = [r for r in rows if low <= r["positive_rate"] <= high]
    if not candidates:
        return None
    midpoint = (low + high) / 2.0
    selected = min(candidates, key=lambda r: (abs(r["positive_rate"] - midpoint), r["k"]))
    return {**selected, "selected_by": selected_by}


def calibrate(
    oracle_scores: str,
    max_k: int,
    target_min: float,
    target_max: float,
    fallback_min: float,
    fallback_max: float,
) -> tuple[pd.DataFrame, dict]:
    if max_k <= 0:
        raise ValueError("max-k must be > 0")
    df = _load_scores(oracle_scores)
    n = len(df)
    rows = []
    for k in range(1, max_k + 1):
        labels = df["count"] >= k
        positive_count = int(labels.sum())
        rows.append(
            {
                "k": k,
                "positive_rate": float(positive_count / n) if n else 0.0,
                "positive_count": positive_count,
                "n": n,
            }
        )

    selected = _choose(rows, target_min, target_max, "target")
    if selected is None:
        selected = _choose(rows, fallback_min, fallback_max, "fallback")
    if selected is None:
        selected = min(rows, key=lambda r: (abs(r["positive_rate"] - 0.1), r["k"]))
        selected = {**selected, "selected_by": "closest"}

    results = pd.DataFrame(rows)
    results["selected_k"] = selected["k"]
    results["selected_by"] = selected["selected_by"]
    results["selected_positive_rate"] = selected["positive_rate"]
    results["selected_positive_count"] = selected["positive_count"]
    return results, selected


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate count_at_least threshold from oracle scores")
    parser.add_argument("--oracle-scores", required=True)
    parser.add_argument("--max-k", type=int, default=20)
    parser.add_argument("--target-min", type=float, default=0.05)
    parser.add_argument("--target-max", type=float, default=0.20)
    parser.add_argument("--fallback-min", type=float, default=0.01)
    parser.add_argument("--fallback-max", type=float, default=0.30)
    parser.add_argument("--out", required=True, help="Output CSV path; JSON is written next to it unless --json-out is set")
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()

    results, selected = calibrate(
        oracle_scores=args.oracle_scores,
        max_k=args.max_k,
        target_min=args.target_min,
        target_max=args.target_max,
        fallback_min=args.fallback_min,
        fallback_max=args.fallback_max,
    )

    out = pathlib.Path(args.out)
    if out.suffix == "":
        out = out.with_suffix(".csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(out, index=False)

    json_out = pathlib.Path(args.json_out) if args.json_out else out.with_suffix(".json")
    payload = {
        "oracle_scores": args.oracle_scores,
        "max_k": args.max_k,
        "target_min": args.target_min,
        "target_max": args.target_max,
        "fallback_min": args.fallback_min,
        "fallback_max": args.fallback_max,
        "selected_k": selected["k"],
        "selected_positive_rate": selected["positive_rate"],
        "selected_positive_count": selected["positive_count"],
        "selected_by": selected["selected_by"],
        "candidates": results[["k", "positive_rate", "positive_count", "n"]].to_dict("records"),
    }
    json_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"Saved CSV: {out}")
    print(f"Saved JSON: {json_out}")
    print(
        "Selected "
        f"K={selected['k']} rate={selected['positive_rate']:.6f} "
        f"count={selected['positive_count']} selected_by={selected['selected_by']}"
    )


if __name__ == "__main__":
    main()
