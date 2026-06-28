#!/usr/bin/env python3
from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from phase0_common import OUT_DIR, STABILITY_FILES, append_progress, ensure_dirs


THRESHOLDS = {
    "stable": {"min_agreement_rate": 0.85, "max_flip_rate": 0.10},
    "ambiguous": {"min_agreement_rate": 0.75, "max_flip_rate": 0.20},
}


def is_positive(value) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "positive", "relevant", "y"}


def classify(agreement_rate: float, flip_rate: float) -> str:
    if agreement_rate >= THRESHOLDS["stable"]["min_agreement_rate"] and flip_rate <= THRESHOLDS["stable"]["max_flip_rate"]:
        return "stable"
    if agreement_rate >= THRESHOLDS["ambiguous"]["min_agreement_rate"] and flip_rate <= THRESHOLDS["ambiguous"]["max_flip_rate"]:
        return "ambiguous"
    return "unstable"


def audit_pair(path) -> dict | None:
    if not path.exists():
        return None
    df = pd.read_csv(path)
    stem = path.stem
    if "8b" in stem:
        prefix = "8b"
    elif "32b" in stem:
        prefix = "32b"
    else:
        return None
    raw_col = f"{prefix}_raw_relevant"
    masked_col = f"{prefix}_masked_relevant"
    agree_col = f"{prefix}_agree"
    if raw_col not in df.columns or masked_col not in df.columns:
        return None
    raw = df[raw_col].map(is_positive)
    masked = df[masked_col].map(is_positive)
    comparable = int(len(df))
    agreement = float((raw == masked).mean()) if comparable else 0.0
    pos_to_neg = int((raw & ~masked).sum())
    neg_to_pos = int((~raw & masked).sum())
    flip_rate = float((raw != masked).mean()) if comparable else 0.0
    abstain_rate = float(
        df[[raw_col, masked_col]]
        .astype(str)
        .apply(lambda s: s.str.lower().isin({"abstain", "unknown", "uncertain"}))
        .any(axis=1)
        .mean()
    )
    return {
        "label_source_pair": f"{prefix}_raw_vs_masked",
        "source_path": str(path),
        "num_comparable_clips": comparable,
        "agreement_rate": agreement,
        "positive_rate_source_a": float(raw.mean()) if comparable else 0.0,
        "positive_rate_source_b": float(masked.mean()) if comparable else 0.0,
        "positive_to_negative_flip": pos_to_neg,
        "negative_to_positive_flip": neg_to_pos,
        "flip_rate": flip_rate,
        "abstain_rate": abstain_rate,
        "boundary_variance": np.nan,
        "human_agreement": np.nan,
        "stable_min_agreement_rate": THRESHOLDS["stable"]["min_agreement_rate"],
        "stable_max_flip_rate": THRESHOLDS["stable"]["max_flip_rate"],
        "ambiguous_min_agreement_rate": THRESHOLDS["ambiguous"]["min_agreement_rate"],
        "ambiguous_max_flip_rate": THRESHOLDS["ambiguous"]["max_flip_rate"],
        "stability_classification": classify(agreement, flip_rate),
    }


def main() -> None:
    ensure_dirs()
    (OUT_DIR / "config/oracle_stability_thresholds.json").write_text(json.dumps(THRESHOLDS, indent=2) + "\n", encoding="utf-8")
    rows = [row for row in (audit_pair(path) for path in STABILITY_FILES) if row is not None]
    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "tables/oracle_stability.csv", index=False)
    if not out.empty:
        labels = out["label_source_pair"].tolist()
        matrix = out[["agreement_rate", "flip_rate", "abstain_rate"]].to_numpy(dtype=float)
        fig, ax = plt.subplots(figsize=(6.5, 3.6))
        im = ax.imshow(matrix, cmap="viridis", vmin=0, vmax=1)
        ax.set_xticks([0, 1, 2])
        ax.set_xticklabels(["agreement", "flip", "abstain"])
        ax.set_yticks(range(len(labels)))
        ax.set_yticklabels(labels)
        ax.set_title("Oracle label stability metrics")
        for i in range(matrix.shape[0]):
            for j in range(matrix.shape[1]):
                ax.text(j, i, f"{matrix[i, j]:.2f}", ha="center", va="center", color="white" if matrix[i, j] < 0.55 else "black")
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        fig.tight_layout()
        fig.savefig(OUT_DIR / "figures/oracle_label_flip_matrix.png", dpi=160)
        plt.close(fig)
    append_progress(
        "oracle stability",
        "python scripts/30_oracle_stability_audit.py",
        f"wrote {len(out)} stability rows",
        next_action="generate final Phase 0 report",
    )


if __name__ == "__main__":
    main()
