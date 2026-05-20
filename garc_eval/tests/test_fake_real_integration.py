"""Fake-real integration test.

Creates synthetic frame metadata + proxy scores + GT labels,
runs build_frame_table, then runs run_supg_real_frames on the result.
No real models or videos involved.

Usage:
    "D:/conda_envs/supg/python.exe" -m pytest garc_eval/tests/test_fake_real_integration.py -v
    "D:/conda_envs/supg/python.exe" garc_eval/tests/test_fake_real_integration.py
"""

import pathlib
import sys
import tempfile

import numpy as np
import pandas as pd

# Ensure project root is importable
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))


def make_fake_data(outdir: pathlib.Path, n: int = 2000, seed: int = 42) -> dict:
    """Create fake frame metadata, proxy scores, and GT labels."""
    rng = np.random.RandomState(seed)

    # Frame metadata
    meta = pd.DataFrame({
        "id": np.arange(n),
        "video_id": "fake_video",
        "frame_idx": np.arange(n),
        "timestamp": np.arange(n, dtype=float),
        "image_path": [str(outdir / "frames" / f"frame_{i:06d}.jpg") for i in range(n)],
    })

    # Proxy scores: Beta(0.01, 1.0) like the synthetic experiments
    proxy_score = rng.beta(0.01, 1.0, size=n).astype(np.float32)
    proxy = pd.DataFrame({
        "id": np.arange(n),
        "proxy_score": proxy_score,
    })

    # GT labels: Bernoulli(proxy_score)
    label = rng.binomial(1, proxy_score).astype(int)
    gt = pd.DataFrame({
        "id": np.arange(n),
        "label": label,
    })

    # Save
    frames_dir = outdir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    meta_path = outdir / "frame_metadata.parquet"
    proxy_path = outdir / "proxy_scores.parquet"
    gt_path = outdir / "gt_labels.csv"
    source_csv = outdir / "supg_source.csv"
    frames_parquet = outdir / "frames.parquet"

    meta.to_parquet(meta_path, index=False)
    proxy.to_parquet(proxy_path, index=False)
    gt.to_csv(gt_path, index=False)

    return {
        "meta_path": str(meta_path),
        "proxy_path": str(proxy_path),
        "gt_path": str(gt_path),
        "source_csv": str(source_csv),
        "frames_parquet": str(frames_parquet),
        "n": n,
        "label_rate": float(label.mean()),
    }


def test_build_frame_table(tmp_path) -> None:
    """Test build_frame_table with fake data."""
    from garc_eval.datasets.build_frame_table import build_frame_table

    paths = make_fake_data(tmp_path)
    frames_df, source_df = build_frame_table(
        frame_metadata_path=paths["meta_path"],
        proxy_scores_path=paths["proxy_path"],
        gt_labels_path=paths["gt_path"],
        oracle_threshold=0.5,
        output_frames_path=paths["frames_parquet"],
        output_source_csv=paths["source_csv"],
    )

    # Validate output
    assert len(frames_df) == paths["n"], f"Expected {paths['n']} rows, got {len(frames_df)}"
    assert set(source_df.columns) == {"id", "label", "proxy_score"}, f"Bad columns: {source_df.columns}"
    assert source_df["id"].is_unique, "source CSV has duplicate ids"
    assert source_df["label"].isin([0, 1]).all(), "labels not binary"
    assert source_df["proxy_score"].notna().all(), "NaN in proxy_score"

    assert pathlib.Path(paths["frames_parquet"]).exists(), "frames.parquet not written"
    assert pathlib.Path(paths["source_csv"]).exists(), "supg_source.csv not written"

    print(f"  build_frame_table: {len(frames_df)} rows, label_rate={source_df['label'].mean():.4f}")


def test_run_supg_real_frames(tmp_path, trials: int = 3) -> None:
    """Test run_supg_real_frames with a small number of trials."""
    from garc_eval.datasets.build_frame_table import build_frame_table
    from garc_eval.experiments.run_supg_real_frames import main as run_main

    paths = make_fake_data(tmp_path)
    build_frame_table(
        frame_metadata_path=paths["meta_path"],
        proxy_scores_path=paths["proxy_path"],
        gt_labels_path=paths["gt_path"],
        oracle_threshold=0.5,
        output_frames_path=paths["frames_parquet"],
        output_source_csv=paths["source_csv"],
    )

    outdir = str(tmp_path / "supg_test_results")

    # Simulate CLI args
    sys.argv = [
        "run_supg_real_frames",
        "--source-csv", paths["source_csv"],
        "--budget", "200",
        "--gamma", "0.9",
        "--delta", "0.05",
        "--trials", str(trials),
        "--outdir", outdir,
    ]
    run_main()

    # Validate outputs
    out = pathlib.Path(outdir)
    for fname in ("config.json", "per_trial_results.csv", "summary.csv",
                  "summary.md", "boxplot_rt_recall.png", "boxplot_pt_precision.png"):
        assert (out / fname).exists(), f"Missing output: {fname}"

    per_trial = pd.read_csv(out / "per_trial_results.csv")
    assert len(per_trial) == trials * 5, f"Expected {trials * 5} rows, got {len(per_trial)}"
    errors = per_trial[per_trial["error"].notna()]
    assert len(errors) == 0, f"Errors in per_trial:\n{errors}"

    summary = pd.read_csv(out / "summary.csv")
    assert len(summary) == 5, f"Expected 5 methods, got {len(summary)}"
    assert set(summary["method"]) == {"U-NOCI-RT", "U-CI-RT", "SUPG-RT", "U-NOCI-PT", "SUPG-PT"}

    print(f"  run_supg_real_frames: {len(per_trial)} trials, {len(summary)} methods, 0 errors")


def test_schema_validation_rejects_bad_csv(tmp_path) -> None:
    """Test that schema validation catches bad inputs."""
    from garc_eval.experiments.run_supg_real_frames import _validate_source_csv

    outdir = tmp_path

    # Missing column
    bad_csv = outdir / "bad_missing_col.csv"
    pd.DataFrame({"id": [0, 1], "label": [0, 1]}).to_csv(bad_csv, index=False)
    try:
        _validate_source_csv(pd.read_csv(bad_csv))
        assert False, "Should have raised ValueError for missing proxy_score"
    except ValueError as e:
        assert "proxy_score" in str(e)
        print(f"  Caught missing column: {e}")

    # Duplicate ids
    bad_csv2 = outdir / "bad_dupes.csv"
    pd.DataFrame({"id": [0, 0, 1], "label": [0, 1, 0], "proxy_score": [0.1, 0.2, 0.3]}).to_csv(bad_csv2, index=False)
    try:
        _validate_source_csv(pd.read_csv(bad_csv2))
        assert False, "Should have raised ValueError for duplicate ids"
    except ValueError as e:
        assert "duplicate" in str(e).lower()
        print(f"  Caught duplicate ids: {e}")

    # Non-binary label
    bad_csv3 = outdir / "bad_label.csv"
    pd.DataFrame({"id": [0, 1], "label": [0, 2], "proxy_score": [0.1, 0.2]}).to_csv(bad_csv3, index=False)
    try:
        _validate_source_csv(pd.read_csv(bad_csv3))
        assert False, "Should have raised ValueError for non-binary label"
    except ValueError as e:
        assert "binary" in str(e).lower()
        print(f"  Caught non-binary label: {e}")

    print("  schema validation: all rejection tests passed")


def main():
    print("=== Fake-Real Integration Test ===\n")

    with tempfile.TemporaryDirectory(prefix="garc_test_") as tmp:
        outdir = pathlib.Path(tmp)
        print(f"Working dir: {outdir}")

        # 1. Create fake data
        print("\n[1/4] Creating fake data...")
        paths = make_fake_data(outdir)
        print(f"  n={paths['n']}, label_rate={paths['label_rate']:.4f}")

        # 2. Test build_frame_table
        print("\n[2/4] Testing build_frame_table...")
        test_build_frame_table(paths)

        # 3. Test run_supg_real_frames
        print("\n[3/4] Testing run_supg_real_frames (3 trials)...")
        test_run_supg_real_frames(paths, trials=3)

        # 4. Test schema validation
        print("\n[4/4] Testing schema validation...")
        test_schema_validation_rejects_bad_csv(paths)

    print("\n=== ALL TESTS PASSED ===")


if __name__ == "__main__":
    main()
