"""Abstract base class for frame scorers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FrameScore:
    """Score result for a single frame."""
    id: int
    score: float
    count: int
    max_conf: float
    extra: dict[str, Any] | None = None


class FrameScorer(ABC):
    """Interface for scoring video frames."""

    @abstractmethod
    def score_frames(self, frame_rows: list[dict]) -> list[FrameScore]:
        """Score a batch of frames.

        Parameters
        ----------
        frame_rows : list of dicts, each with at least 'id' and 'image_path'.

        Returns
        -------
        list of FrameScore, one per input row.
        """
        ...
