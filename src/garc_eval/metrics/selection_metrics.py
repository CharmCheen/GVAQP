"""Evaluation metrics for approximate query selection."""

import numpy as np
import pandas as pd


def evaluate_selection(
    labels: np.ndarray,
    selected_ids: np.ndarray,
    total_ids: np.ndarray | None = None,
) -> dict:
    """Compute precision, recall, and counts for a selection result.

    Parameters
    ----------
    labels : array of 0/1 — full-dataset oracle labels, indexed by position.
    selected_ids : array of ids that were selected by the method.
    total_ids : optional full id array; if None, labels[i] corresponds to id=i.

    Returns
    -------
    dict with keys: precision, recall, selected_n, true_positive_n, total_positive_n
    """
    labels = np.asarray(labels)
    selected_ids = np.asarray(selected_ids)
    total_positive_n = int(np.sum(labels))

    if len(selected_ids) == 0:
        return {
            "precision": 0.0,
            "recall": 0.0,
            "selected_n": 0,
            "true_positive_n": 0,
            "total_positive_n": total_positive_n,
        }

    if total_ids is not None:
        id_to_idx = {int(v): i for i, v in enumerate(total_ids)}
        sel_indices = np.array([id_to_idx[int(s)] for s in selected_ids])
    else:
        sel_indices = selected_ids.astype(int)

    selected_labels = labels[sel_indices]
    true_positive_n = int(np.sum(selected_labels))
    total_positive_n = int(np.sum(labels))
    selected_n = len(selected_ids)

    precision = true_positive_n / selected_n if selected_n > 0 else 0.0
    recall = true_positive_n / total_positive_n if total_positive_n > 0 else 0.0

    return {
        "precision": precision,
        "recall": recall,
        "selected_n": selected_n,
        "true_positive_n": true_positive_n,
        "total_positive_n": total_positive_n,
    }
