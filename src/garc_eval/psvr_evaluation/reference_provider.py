"""Evaluator-side reference provider, intended for a separate process only."""

from pathlib import Path


def load_reference(reference_path: Path):
    import pandas as pd

    return pd.read_csv(Path(reference_path).resolve(strict=True))
