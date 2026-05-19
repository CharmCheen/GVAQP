"""Build the final frame table with proxy_score, oracle_score, and label.

Inputs:
  - frame metadata (id, video_id, frame_idx, timestamp, image_path)
  - proxy scores (id, proxy_score, proxy_count)
  - oracle scores or GT labels

Output:
  - frames.parquet: full table with all columns
  - supg_source.csv: id, label, proxy_score
"""

import argparse
import pathlib

import numpy as np
import pandas as pd

# Required columns for each input table
_FRAME_META_SCHEMA = {"id", "video_id", "frame_idx", "timestamp", "image_path"}
_PROXY_SCORE_SCHEMA = {"id", "proxy_score"}
_ORACLE_SCORE_SCHEMA = {"id", "oracle_score"}
_GT_LABEL_SCHEMA = {"id", "label"}
_SOURCE_CSV_SCHEMA = {"id", "label", "proxy_score"}


def _validate_schema(df: pd.DataFrame, required: set, label: str) -> None:
    """Raise ValueError if df is missing any required columns or has duplicate ids."""
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{label} missing columns {missing}, got {list(df.columns)}")
    if "id" in df.columns and df["id"].duplicated().any():
        dupes = df[df["id"].duplicated()]["id"].head(5).tolist()
        raise ValueError(f"{label} has duplicate ids: {dupes}")


def build_frame_table(
    frame_metadata_path: str,
    proxy_scores_path: str,
    oracle_scores_path: str | None = None,
    gt_labels_path: str | None = None,
    oracle_threshold: float = 0.5,
    output_frames_path: str = "frames.parquet",
    output_source_csv: str = "supg_source.csv",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build frames.parquet and supg_source.csv.

    Returns (frames_df, source_df).
    """
    # Load frame metadata
    meta_path = pathlib.Path(frame_metadata_path)
    if meta_path.suffix == ".parquet":
        meta = pd.read_parquet(meta_path)
    else:
        meta = pd.read_csv(meta_path)
    _validate_schema(meta, _FRAME_META_SCHEMA, "frame metadata")

    # Load proxy scores
    proxy_path = pathlib.Path(proxy_scores_path)
    if proxy_path.suffix == ".parquet":
        proxy = pd.read_parquet(proxy_path)
    else:
        proxy = pd.read_csv(proxy_path)
    _validate_schema(proxy, _PROXY_SCORE_SCHEMA, "proxy scores")

    # Merge
    df = meta.merge(proxy[["id", "proxy_score"]], on="id", how="left")
    if df["proxy_score"].isna().any():
        missing = int(df["proxy_score"].isna().sum())
        raise ValueError(f"{missing} frames missing proxy scores after merge")

    # Oracle / GT label
    if gt_labels_path is not None:
        gt_path = pathlib.Path(gt_labels_path)
        if gt_path.suffix == ".parquet":
            gt = pd.read_parquet(gt_path)
        else:
            gt = pd.read_csv(gt_path)
        _validate_schema(gt, _GT_LABEL_SCHEMA, "GT labels")
        df = df.merge(gt[["id", "label"]], on="id", how="left")
        if df["label"].isna().any():
            raise ValueError("Some frames missing GT labels after merge")
        df["label"] = df["label"].astype(int)
    elif oracle_scores_path is not None:
        oracle_path = pathlib.Path(oracle_scores_path)
        if oracle_path.suffix == ".parquet":
            oracle = pd.read_parquet(oracle_path)
        else:
            oracle = pd.read_csv(oracle_path)
        _validate_schema(oracle, _ORACLE_SCORE_SCHEMA, "oracle scores")
        df = df.merge(oracle[["id", "oracle_score"]], on="id", how="left")
        if df["oracle_score"].isna().any():
            raise ValueError("Some frames missing oracle scores after merge")
        df["label"] = (df["oracle_score"] >= oracle_threshold).astype(int)
    else:
        raise ValueError("Must provide either gt_labels_path or oracle_scores_path")

    # Write outputs
    frames_out = pathlib.Path(output_frames_path)
    frames_out.parent.mkdir(parents=True, exist_ok=True)
    if frames_out.suffix == ".parquet":
        df.to_parquet(frames_out, index=False)
    else:
        df.to_csv(frames_out, index=False)

    source_df = df[["id", "label", "proxy_score"]].copy()
    _validate_schema(source_df, _SOURCE_CSV_SCHEMA, "output source CSV")
    source_out = pathlib.Path(output_source_csv)
    source_out.parent.mkdir(parents=True, exist_ok=True)
    source_df.to_csv(source_out, index=False)

    print(f"Built frame table: {len(df)} rows")
    print(f"  frames: {frames_out}")
    print(f"  source: {source_out}")
    print(f"  label rate: {df['label'].mean():.4f}")

    return df, source_df


def main():
    parser = argparse.ArgumentParser(description="Build frame table with scores and labels")
    parser.add_argument("--frame-metadata", required=True)
    parser.add_argument("--proxy-scores", required=True)
    parser.add_argument("--oracle-scores", default=None)
    parser.add_argument("--gt-labels", default=None)
    parser.add_argument("--oracle-threshold", type=float, default=0.5)
    parser.add_argument("--output-frames", default="frames.parquet")
    parser.add_argument("--output-source", default="supg_source.csv")
    args = parser.parse_args()

    build_frame_table(
        args.frame_metadata, args.proxy_scores, args.oracle_scores, args.gt_labels,
        args.oracle_threshold, args.output_frames, args.output_source,
    )


if __name__ == "__main__":
    main()
