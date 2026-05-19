"""Summarize trial results to assess guarantee satisfaction."""

import numpy as np
import pandas as pd


def summarize_trials(
    results_df: pd.DataFrame,
    qtype: str,
    gamma: float,
) -> dict:
    """Summarize per-trial results for a given query type.

    Parameters
    ----------
    results_df : DataFrame with columns [precision, recall, selected_n].
    qtype : 'rt' or 'pt'.
    gamma : target threshold.

    Returns
    -------
    dict with failure_rate, mean/median precision/recall, mean_selected_n.
    """
    if qtype == "rt":
        failures = results_df["recall"] < gamma
        quality = results_df["precision"]
    elif qtype == "pt":
        failures = results_df["precision"] < gamma
        quality = results_df["recall"]
    else:
        raise ValueError(f"Unknown qtype: {qtype}")

    failure_rate = float(failures.mean())

    if qtype == "rt":
        return {
            "failure_rate": failure_rate,
            "mean_precision": float(quality.mean()),
            "mean_recall": float(results_df["recall"].mean()),
            "median_precision": float(quality.median()),
            "median_recall": float(results_df["recall"].median()),
            "mean_selected_n": float(results_df["selected_n"].mean()),
        }
    else:
        return {
            "failure_rate": failure_rate,
            "mean_precision": float(results_df["precision"].mean()),
            "mean_recall": float(quality.mean()),
            "median_precision": float(results_df["precision"].median()),
            "median_recall": float(quality.median()),
            "mean_selected_n": float(results_df["selected_n"].mean()),
        }
