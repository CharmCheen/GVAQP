"""Scorer registry — creates scorer instances from config dicts."""

from .base import FrameScorer


def create_scorer(scorer_type: str, **kwargs) -> FrameScorer:
    """Create a scorer instance by type name.

    Parameters
    ----------
    scorer_type : str
        One of 'yolo', 'gt'.
    **kwargs
        Forwarded to the scorer constructor.

    Returns
    -------
    FrameScorer instance.
    """
    if scorer_type == "yolo":
        from .yolo_scorer import YOLOFrameScorer
        return YOLOFrameScorer(**kwargs)
    elif scorer_type == "gt":
        from .gt_oracle import GTOracleScorer
        return GTOracleScorer(**kwargs)
    else:
        raise ValueError(f"Unknown scorer type: {scorer_type!r}. Supported: yolo, gt")
