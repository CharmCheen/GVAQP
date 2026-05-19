"""Materialize proxy and oracle scores for real video frames.

Usage:
    python -m garc_eval.experiments.materialize_frame_scores --config garc_eval/configs/real_frame_yolo.example.yaml
    python -m garc_eval.experiments.materialize_frame_scores --config ... --dry-run
    python -m garc_eval.experiments.materialize_frame_scores --config ... --skip-proxy --use-existing-proxy path/to/proxy.parquet
"""

import argparse
import json
import pathlib
import sys


def load_config(config_path: str) -> dict:
    try:
        import yaml
    except ImportError:
        raise ImportError(
            "pyyaml is not installed. Install with: pip install pyyaml"
        )
    with open(config_path) as f:
        return yaml.safe_load(f)


def resolve_config_paths(cfg: dict) -> dict:
    """Resolve all ${ENV_VAR} references in the config."""
    from garc_eval.models.model_paths import resolve_path

    def _resolve(obj):
        if isinstance(obj, str):
            return resolve_path(obj)
        if isinstance(obj, dict):
            return {k: _resolve(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_resolve(v) for v in obj]
        return obj

    return _resolve(cfg)


def dry_run(cfg: dict) -> None:
    """Check configuration and paths without running models."""
    from garc_eval.models.model_paths import resolve_path, check_path_exists

    print("[dry-run] Configuration check")
    print(f"  project: {cfg['project']['name']}")
    print(f"  seed:    {cfg['project']['seed']}")

    paths = cfg["paths"]
    print(f"\n[dry-run] Paths:")
    for k, v in paths.items():
        p = pathlib.Path(v)
        print(f"  {k}: {v}  (exists: {p.exists()})")

    data = cfg["data"]
    query = cfg.get("query", {})
    predicate = query.get("predicate", "contains_class")
    print(f"\n[dry-run] Data:")
    video_path = data.get("video_path")
    video_exists = pathlib.Path(video_path).exists() if video_path else "n/a"
    print(f"  video_path:      {video_path}  (exists: {video_exists})")
    print(f"  frames_dir:      {data['frames_dir']}  (exists: {pathlib.Path(data['frames_dir']).exists()})")
    print(f"  frame_table_path:{data['frame_table_path']}")
    print(f"  sample_fps:      {data['sample_fps']}")
    print(f"  max_frames:      {data['max_frames']}")
    print(f"\n[dry-run] Query:")
    print(f"  target_class:    {query.get('target_class')}")
    print(f"  predicate:       {predicate}")
    if predicate == "count_at_least":
        print(f"  count_threshold: {query.get('count_threshold')}")
    print(f"  oracle_threshold:{query.get('oracle_threshold')}")

    proxy = cfg["proxy"]
    oracle = cfg["oracle"]
    print(f"\n[dry-run] Proxy model:")
    print(f"  type:        {proxy['type']}")
    print(f"  model_path:  {proxy['model_path']}")
    print(f"  device:      {proxy['device']}")
    print(f"  model exists:{pathlib.Path(proxy['model_path']).exists()}")

    print(f"\n[dry-run] Oracle:")
    print(f"  type:        {oracle['type']}")
    if oracle["type"] == "yolo":
        print(f"  model_path:  {oracle['model_path']}")
        print(f"  model exists:{pathlib.Path(oracle['model_path']).exists()}")
    elif oracle["type"] == "gt":
        print(f"  label_path:  {oracle.get('label_path', 'NOT SET')}")

    supg = cfg["supg"]
    print(f"\n[dry-run] SUPG config:")
    print(f"  source_csv: {supg['source_csv']}")
    print(f"  budget:     {supg['budget']}")
    print(f"  gamma:      {supg['gamma']}")
    print(f"  delta:      {supg['delta']}")
    print(f"  trials:     {supg['trials']}")

    # Dependency check
    print(f"\n[dry-run] Dependencies:")
    deps = {"ultralytics": proxy["type"] == "yolo" or oracle.get("type") == "yolo",
            "cv2": True, "yaml": True, "pandas": True, "numpy": True}
    for pkg, needed in deps.items():
        if not needed:
            continue
        try:
            __import__(pkg)
            print(f"  {pkg}: OK")
        except ImportError:
            print(f"  {pkg}: MISSING")

    print("\n[dry-run] PASSED — configuration is valid")


def materialize(cfg: dict, skip_proxy: bool, skip_oracle: bool,
                existing_proxy: str | None, existing_oracle: str | None) -> None:
    """Run the full materialization pipeline."""
    import pandas as pd
    from garc_eval.models.registry import create_scorer
    from garc_eval.datasets.build_frame_table import build_frame_table

    data = cfg["data"]
    frame_table_path = data["frame_table_path"]

    # Load frame metadata
    p = pathlib.Path(frame_table_path)
    if p.suffix == ".parquet":
        meta = pd.read_parquet(p)
    else:
        meta = pd.read_csv(p)
    print(f"Loaded {len(meta)} frames from {frame_table_path}")

    frame_rows = meta.to_dict("records")
    outdir = pathlib.Path(cfg["supg"]["source_csv"]).parent
    outdir.mkdir(parents=True, exist_ok=True)

    # Proxy scores
    proxy_scores_path = str(outdir / "proxy_scores.parquet")
    if existing_proxy:
        proxy_scores_path = existing_proxy
        print(f"Using existing proxy scores: {proxy_scores_path}")
    elif skip_proxy:
        print("Skipping proxy (--skip-proxy without --use-existing-proxy)")
        proxy_scores_path = None
    else:
        proxy_cfg = cfg["proxy"]
        print(f"Running proxy scorer: {proxy_cfg['type']}")
        proxy_scorer = create_scorer(
            proxy_cfg["type"],
            model_path=proxy_cfg["model_path"],
            target_class=cfg["query"]["target_class"],
            device=proxy_cfg["device"],
            batch_size=proxy_cfg["batch_size"],
            conf_threshold=proxy_cfg.get("conf_threshold", 0.25),
        )
        proxy_results = proxy_scorer.score_frames(frame_rows)
        proxy_rows = []
        for r in proxy_results:
            row = {
                "id": r.id,
                "proxy_score": r.score,
                "proxy_max_conf": r.max_conf,
                "proxy_count": r.count,
            }
            if r.extra:
                row.update({
                    "proxy_conf_sum": r.extra.get("conf_sum", 0.0),
                    "proxy_conf_mean": r.extra.get("conf_mean", 0.0),
                    "proxy_conf_top3_sum": r.extra.get("conf_top3_sum", 0.0),
                    "proxy_conf_top5_sum": r.extra.get("conf_top5_sum", 0.0),
                })
            proxy_rows.append(row)
        proxy_df = pd.DataFrame(proxy_rows)
        proxy_df.to_parquet(proxy_scores_path, index=False)
        print(f"Saved proxy scores: {proxy_scores_path}")

    # Oracle scores
    oracle_scores_path = str(outdir / "oracle_scores.parquet")
    oracle_cfg = cfg["oracle"]

    if existing_oracle:
        oracle_scores_path = existing_oracle
        print(f"Using existing oracle scores: {oracle_scores_path}")
    elif skip_oracle:
        print("Skipping oracle")
        oracle_scores_path = None
    elif oracle_cfg["type"] == "gt":
        # GT oracle: no model, just label file
        gt_path = oracle_cfg.get("label_path")
        if gt_path is None:
            raise ValueError("Oracle type='gt' requires 'label_path' in config")
        oracle_scores_path = None  # will use gt_labels_path instead
    else:
        print(f"Running oracle scorer: {oracle_cfg['type']}")
        oracle_scorer = create_scorer(
            oracle_cfg["type"],
            model_path=oracle_cfg["model_path"],
            target_class=cfg["query"]["target_class"],
            device=oracle_cfg["device"],
            batch_size=oracle_cfg["batch_size"],
            conf_threshold=oracle_cfg.get("conf_threshold", 0.25),
        )
        oracle_results = oracle_scorer.score_frames(frame_rows)
        oracle_rows = []
        for r in oracle_results:
            row = {"id": r.id, "oracle_score": r.score, "oracle_count": r.count}
            if r.extra:
                row.update({
                    "oracle_conf_sum": r.extra.get("conf_sum", 0.0),
                    "oracle_conf_mean": r.extra.get("conf_mean", 0.0),
                    "oracle_conf_top3_sum": r.extra.get("conf_top3_sum", 0.0),
                    "oracle_conf_top5_sum": r.extra.get("conf_top5_sum", 0.0),
                })
            oracle_rows.append(row)
        oracle_df = pd.DataFrame(oracle_rows)
        oracle_df.to_parquet(oracle_scores_path, index=False)
        print(f"Saved oracle scores: {oracle_scores_path}")

    # Build frame table
    gt_labels_path = oracle_cfg.get("label_path") if oracle_cfg["type"] == "gt" else None
    frames_out = str(outdir / "frames.parquet")
    source_out = cfg["supg"]["source_csv"]

    build_frame_table(
        frame_metadata_path=frame_table_path,
        proxy_scores_path=proxy_scores_path or "",
        oracle_scores_path=oracle_scores_path,
        gt_labels_path=gt_labels_path,
        oracle_threshold=cfg["query"].get("oracle_threshold", 0.5),
        predicate=cfg["query"].get("predicate", "contains_class"),
        count_threshold=cfg["query"].get("count_threshold"),
        proxy_score_rule=cfg["query"].get("proxy_score_rule", "count_ratio"),
        output_frames_path=frames_out,
        output_source_csv=source_out,
    )

    # Save config
    config_out = outdir / "materialize_config.json"
    with open(config_out, "w") as f:
        json.dump(cfg, f, indent=2, default=str)
    print(f"Saved config: {config_out}")
    print("Done.")


def main():
    parser = argparse.ArgumentParser(description="Materialize proxy/oracle scores for real frames")
    parser.add_argument("--config", required=True, help="Path to YAML config file")
    parser.add_argument("--dry-run", action="store_true", help="Check config without running models")
    parser.add_argument("--skip-proxy", action="store_true", help="Skip proxy scoring")
    parser.add_argument("--skip-oracle", action="store_true", help="Skip oracle scoring")
    parser.add_argument("--use-existing-proxy", default=None, help="Path to existing proxy scores")
    parser.add_argument("--use-existing-oracle", default=None, help="Path to existing oracle scores")
    args = parser.parse_args()

    cfg = load_config(args.config)
    cfg = resolve_config_paths(cfg)

    if args.dry_run:
        dry_run(cfg)
        return

    materialize(cfg, args.skip_proxy, args.skip_oracle, args.use_existing_proxy, args.use_existing_oracle)


if __name__ == "__main__":
    main()
