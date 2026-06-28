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
    predicate: str = "contains_class",
    count_threshold: int | None = None,
    proxy_score_rule: str = "count_ratio",
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

    if predicate not in {"contains_class", "count_at_least"}:
        raise ValueError(
            f"Unsupported predicate {predicate!r}. "
            "Supported predicates: contains_class, count_at_least"
        )
    if predicate == "count_at_least":
        if count_threshold is None or count_threshold <= 0:
            raise ValueError("count_at_least requires count_threshold > 0")
        if "proxy_count" not in proxy.columns:
            raise ValueError("count_at_least requires proxy scores with proxy_count")
        supported_rules = {
            "count_ratio",
            "conf_sum_ratio",
            "conf_top5_ratio",
            "soft_count_exp",
            "count_conf_hybrid",
            "rank_percentile",
        }
        if proxy_score_rule not in supported_rules:
            raise ValueError(
                f"Unsupported proxy_score_rule {proxy_score_rule!r}. "
                f"Supported rules: {sorted(supported_rules)}"
            )

    # Merge proxy scores. Preserve the raw YOLO confidence separately from the
    # predicate-specific score used by SUPG.
    proxy_cols = ["id", "proxy_score"]
    optional_proxy_cols = [
        "proxy_max_conf",
        "proxy_count",
        "proxy_conf_sum",
        "proxy_conf_mean",
        "proxy_conf_top3_sum",
        "proxy_conf_top5_sum",
    ]
    proxy_cols.extend([c for c in optional_proxy_cols if c in proxy.columns])
    proxy = proxy[proxy_cols].rename(columns={"proxy_score": "proxy_score_raw"})
    df = meta.merge(proxy, on="id", how="left")
    if df["proxy_score_raw"].isna().any():
        missing = int(df["proxy_score_raw"].isna().sum())
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
        if predicate != "contains_class":
            raise ValueError("count_at_least requires oracle_count; GT labels only support contains_class")
        df["label"] = df["label"].astype(int)
        df["proxy_score"] = df["proxy_score_raw"]
    elif oracle_scores_path is not None:
        oracle_path = pathlib.Path(oracle_scores_path)
        if oracle_path.suffix == ".parquet":
            oracle = pd.read_parquet(oracle_path)
        else:
            oracle = pd.read_csv(oracle_path)
        _validate_schema(oracle, _ORACLE_SCORE_SCHEMA, "oracle scores")
        if predicate == "count_at_least" and "oracle_count" not in oracle.columns:
            raise ValueError("count_at_least requires oracle scores with oracle_count")
        oracle_cols = ["id", "oracle_score"]
        if "oracle_count" in oracle.columns:
            oracle_cols.append("oracle_count")
        df = df.merge(oracle[oracle_cols], on="id", how="left")
        if df["oracle_score"].isna().any():
            raise ValueError("Some frames missing oracle scores after merge")
        if predicate == "contains_class":
            df["proxy_score"] = df["proxy_score_raw"]
            df["label"] = (df["oracle_score"] >= oracle_threshold).astype(int)
        else:
            df["proxy_score"] = _compute_count_proxy_score(df, count_threshold, proxy_score_rule)
            df["label"] = (df["oracle_count"] >= count_threshold).astype(int)
    else:
        raise ValueError("Must provide either gt_labels_path or oracle_scores_path")

    df["label"] = df["label"].astype(int)

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
    print(f"  predicate: {predicate}")
    if predicate == "count_at_least":
        print(f"  count_threshold: {count_threshold}")
        print(f"  proxy_score_rule: {proxy_score_rule}")
    print(f"  label rate: {df['label'].mean():.4f}")

    return df, source_df


def _require_columns(df: pd.DataFrame, cols: list[str], rule: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"proxy_score_rule={rule} requires columns {missing}")


def _compute_count_proxy_score(df: pd.DataFrame, count_threshold: int, rule: str) -> pd.Series:
    if rule == "count_ratio":
        _require_columns(df, ["proxy_count"], rule)
        score = df["proxy_count"] / count_threshold
    elif rule == "conf_sum_ratio":
        _require_columns(df, ["proxy_conf_sum"], rule)
        score = df["proxy_conf_sum"] / count_threshold
    elif rule == "conf_top5_ratio":
        _require_columns(df, ["proxy_conf_top5_sum"], rule)
        score = df["proxy_conf_top5_sum"] / count_threshold
    elif rule == "soft_count_exp":
        _require_columns(df, ["proxy_conf_sum"], rule)
        score = 1.0 - np.exp(-df["proxy_conf_sum"] / count_threshold)
    elif rule == "count_conf_hybrid":
        _require_columns(df, ["proxy_count"], rule)
        max_conf_col = "proxy_max_conf" if "proxy_max_conf" in df.columns else "proxy_score_raw"
        score = 0.7 * (df["proxy_count"] / count_threshold).clip(upper=1.0) + 0.3 * df[max_conf_col]
    elif rule == "rank_percentile":
        _require_columns(df, ["proxy_conf_sum"], rule)
        if len(df) <= 1:
            score = pd.Series([1.0] * len(df), index=df.index)
        else:
            score = (df["proxy_conf_sum"].rank(method="average") - 1.0) / (len(df) - 1.0)
    else:
        raise ValueError(f"Unsupported proxy_score_rule: {rule}")
    return score.clip(lower=0.0, upper=1.0)


def main():
    parser = argparse.ArgumentParser(description="Build frame table with scores and labels")
    parser.add_argument("--frame-metadata", required=True)
    parser.add_argument("--proxy-scores", required=True)
    parser.add_argument("--oracle-scores", default=None)
    parser.add_argument("--gt-labels", default=None)
    parser.add_argument("--oracle-threshold", type=float, default=0.5)
    parser.add_argument("--predicate", default="contains_class", choices=["contains_class", "count_at_least"])
    parser.add_argument("--count-threshold", type=int, default=None)
    parser.add_argument("--proxy-score-rule", default="count_ratio")
    parser.add_argument("--output-frames", default="frames.parquet")
    parser.add_argument("--output-source", default="supg_source.csv")
    args = parser.parse_args()

    build_frame_table(
        args.frame_metadata, args.proxy_scores, args.oracle_scores, args.gt_labels,
        args.oracle_threshold, args.predicate, args.count_threshold, args.proxy_score_rule,
        args.output_frames, args.output_source,
    )


if __name__ == "__main__":
    main()
