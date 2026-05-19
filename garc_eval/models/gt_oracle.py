"""Ground-truth oracle scorer — reads labels from CSV/parquet, no model inference."""

from pathlib import Path

import numpy as np
import pandas as pd

from .base import FrameScore, FrameScorer


class GTOracleScorer(FrameScorer):
    """Read ground-truth labels from a file with id,label columns.

    For compatibility with the FrameScorer interface, score = label (0 or 1),
    count = label, max_conf = label.
    """

    def __init__(self, label_path: str):
        p = Path(label_path)
        if not p.exists():
            raise FileNotFoundError(f"Label file not found: {p}")

        if p.suffix == ".parquet":
            df = pd.read_parquet(p)
        else:
            df = pd.read_csv(p)

        if "id" not in df.columns or "label" not in df.columns:
            raise ValueError(f"Label file must have 'id' and 'label' columns, got {list(df.columns)}")

        self._labels: dict[int, int] = dict(zip(df["id"].astype(int), df["label"].astype(int)))

    def score_frames(self, frame_rows: list[dict]) -> list[FrameScore]:
        results = []
        for row in frame_rows:
            fid = int(row["id"])
            label = self._labels.get(fid, 0)
            results.append(FrameScore(id=fid, score=float(label), count=int(label), max_conf=float(label)))
        return results

    def get_labels(self, frame_table: pd.DataFrame) -> pd.Series:
        """Return labels aligned to frame_table['id']."""
        return frame_table["id"].map(lambda x: self._labels.get(int(x), 0)).astype(int)
