#!/usr/bin/env python3
"""Simulate limited-VLM budget allocation against VLM32B pseudo labels."""

import argparse
import math
from pathlib import Path

from common import DEFAULT_CONFIG, ensure_output_dir, fail, load_config, validate_base_paths


METHODS = [
    "random",
    "uniform_time",
    "top_count",
    "top_naive",
    "top_kinematic",
    "ensemble_count_naive",
    "ensemble_all_proxy",
    "temporal_nms_count",
    "temporal_nms_naive",
    "temporal_nms_ensemble",
    "uniform_expansion",
    "proxy_then_expansion_count",
    "proxy_then_expansion_naive",
    "proxy_then_expansion_ensemble",
]

PLOT_METHODS = [
    "random",
    "top_count",
    "top_naive",
    "top_kinematic",
    "ensemble_count_naive",
    "temporal_nms_ensemble",
    "uniform_expansion",
    "proxy_then_expansion_count",
    "proxy_then_expansion_ensemble",
]

SWEEP_METHODS = [
    "uniform_expansion",
    "proxy_then_expansion_count",
    "proxy_then_expansion_naive",
    "proxy_then_expansion_ensemble",
    "temporal_nms_count",
    "temporal_nms_naive",
    "temporal_nms_ensemble",
]

EXACT_LABEL_COLUMNS = {
    "clip_id",
    "start_time",
    "end_time",
    "clip_path",
    "vlm_relevant",
    "vlm_risk_level",
    "vlm_affected_ego",
    "vlm_event_type",
    "vlm_confidence",
    "vlm_reason",
    "raw_response",
}

STRICT_VARIANT_COLUMNS = {
    "clip_id",
    "start_time",
    "end_time",
    "clip_path",
    "vlm_relevant",
    "vlm_risk_level",
    "vlm_affected_ego",
    "vlm_event_type",
    "vlm_confidence",
    "vlm_reason",
    "label_broad",
    "label_ego_relevant",
    "label_strict",
    "label_strict_v2",
    "label_strict_v3",
    "strict_v2_reason",
    "strict_v3_reason",
}

CONSERVATIVE_LABEL_COLUMNS = {
    "clip_id",
    "start_time",
    "end_time",
    "clip_path",
    "old_vlm_relevant",
    "old_vlm_risk_level",
    "old_vlm_affected_ego",
    "old_vlm_event_type",
    "old_vlm_confidence",
    "conservative_positive",
    "risk_level",
    "affected_ego",
    "event_type",
    "starts_outside_ego_path",
    "enters_ego_path",
    "requires_ego_attention",
    "negative_reason",
    "confidence",
    "evidence",
    "label_conservative_positive",
    "validation_reason",
    "raw_response",
}


def require_deps():
    missing = []
    try:
        import pandas as pd
    except ImportError:
        pd = None
        missing.append("pandas")
    try:
        import numpy as np
    except ImportError:
        np = None
        missing.append("numpy")
    if missing:
        fail(f"missing dependencies: {', '.join(missing)}. Install with: pip install {' '.join(missing)}")
    return pd, np


def require_matplotlib():
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        fail("missing dependency matplotlib. Install with: pip install matplotlib")
    return plt


def check_output_path(path: Path, output_dir: Path) -> None:
    try:
        path.resolve().relative_to(output_dir.resolve())
    except ValueError:
        fail(f"output path must be under {output_dir}: {path}")


def parse_yes_no(value) -> int:
    text = str(value).strip().lower()
    if text in {"1", "yes", "true", "positive", "relevant"}:
        return 1
    if text in {"0", "no", "false", "negative", "irrelevant"}:
        return 0
    return -1


def truthy(value) -> bool | None:
    text = str(value).strip().lower()
    if text in {"1", "yes", "true", "y", "affected", "relevant"}:
        return True
    if text in {"0", "no", "false", "n", "none", "not_affected", "irrelevant"}:
        return False
    return None


def risk_rank(value) -> int | None:
    text = str(value).strip().lower()
    mapping = {
        "none": 0,
        "normal": 0,
        "normal_driving": 0,
        "l0": 0,
        "0": 0,
        "low": 1,
        "l1": 1,
        "1": 1,
        "medium": 2,
        "moderate": 2,
        "l2": 2,
        "2": 2,
        "high": 3,
        "l3": 3,
        "3": 3,
        "critical": 4,
        "l4": 4,
        "4": 4,
    }
    return mapping.get(text)


def label_schema(labels) -> str:
    if CONSERVATIVE_LABEL_COLUMNS.issubset(set(labels.columns)):
        return "conservative"
    if STRICT_VARIANT_COLUMNS.issubset(set(labels.columns)):
        return "strict_variants"
    if EXACT_LABEL_COLUMNS.issubset(set(labels.columns)):
        return "exact"
    return "mapped"


def normalize_exact_affected(value) -> int:
    affected = truthy(value)
    if affected is True:
        return 1
    if affected is False:
        return 0
    return -1


def normalize_labels_for_eval(labels):
    labels = labels.copy()
    schema = label_schema(labels)
    if schema == "conservative":
        labels["vlm_label"] = labels["label_conservative_positive"].map(
            lambda v: int(v) if str(v).strip() in {"0", "1", "-1"} else -1
        )
        labels["vlm_reason"] = labels["evidence"].fillna("")
        labels["vlm_risk_level"] = labels["risk_level"].fillna("")
    elif schema in {"exact", "strict_variants"}:
        labels["vlm_label"] = labels["vlm_relevant"].map(parse_yes_no)
        labels["vlm_reason"] = labels["vlm_reason"].fillna("")
        labels["vlm_risk_level"] = labels["vlm_risk_level"].fillna("")
    return labels


def avg_positive_run_length(df) -> float:
    run_lengths = []
    current = 0
    for label in df.sort_values(["start_time", "clip_id"])["vlm_label"].tolist():
        if int(label) == 1:
            current += 1
        elif current:
            run_lengths.append(current)
            current = 0
    if current:
        run_lengths.append(current)
    return sum(run_lengths) / len(run_lengths) if run_lengths else 0.0


def write_missing_template(pd, proxy_df, template_path: Path, report_path: Path, reason: str) -> None:
    rows = proxy_df[["clip_id", "start_time", "end_time", "clip_path"]].copy()
    rows["vlm_label"] = ""
    rows["vlm_risk_level"] = ""
    rows["vlm_reason"] = ""
    rows.to_csv(template_path, index=False)
    report_path.write_text(
        "\n".join(
            [
                "# BLOCKED: Missing VLM32B Labels",
                "",
                reason,
                "",
                "Cannot run a real budget simulation because the full or near-full VLM32B pseudo labels are unavailable.",
                "",
                "Expected label file:",
                "",
                f"```text\n{template_path}\n```",
                "",
                "Expected schema:",
                "",
                "```text\nclip_id,start_time,end_time,clip_path,vlm_label,vlm_risk_level,vlm_reason\n```",
                "",
                "Label convention:",
                "",
                "- `1` = VLM32B positive",
                "- `0` = VLM32B negative",
                "- `-1` = uncertain / invalid",
                "",
                "Populate this file or provide a compatible VLM32B result CSV with `start_sec`, `end_sec`, and `vlm_relevant` fields.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def source_columns_for_review(src) -> dict:
    if "vlm_relevant" in src.columns:
        return {
            "relevant_col": "vlm_relevant",
            "risk_col": "vlm_risk_level" if "vlm_risk_level" in src.columns else "vlm_risk_type",
            "reason_col": "vlm_evidence" if "vlm_evidence" in src.columns else "manual_note",
        }
    if "32b_raw_relevant" in src.columns:
        return {
            "relevant_col": "32b_raw_relevant",
            "risk_col": "32b_raw_risk_level" if "32b_raw_risk_level" in src.columns else "32b_raw_risk_type",
            "reason_col": "32b_raw_evidence",
        }
    if "32b_masked_relevant" in src.columns:
        return {
            "relevant_col": "32b_masked_relevant",
            "risk_col": "32b_masked_risk_level" if "32b_masked_risk_level" in src.columns else "32b_masked_risk_type",
            "reason_col": "32b_masked_evidence",
        }
    raise ValueError("VLM source must include vlm_relevant, 32b_raw_relevant, or 32b_masked_relevant")


def adapt_vlm_review_csv(pd, proxy_df, source_path: Path, labels_path: Path, min_overlap_ratio: float) -> dict:
    if not source_path.is_file():
        raise FileNotFoundError(f"VLM source review CSV not found: {source_path}")
    src = pd.read_csv(source_path)
    required = {"start_sec", "end_sec"}
    if not required.issubset(src.columns):
        raise ValueError(f"VLM source must include {sorted(required)}, got columns: {list(src.columns)}")
    cols = source_columns_for_review(src)

    out_rows = []
    valid = 0
    positives = 0
    for _, clip in proxy_df.iterrows():
        cs = float(clip["start_time"])
        ce = float(clip["end_time"])
        clip_len = max(ce - cs, 1e-9)
        best_i = None
        best_overlap = 0.0
        for i, row in src.iterrows():
            ss = float(row["start_sec"])
            se = float(row["end_sec"])
            overlap = max(0.0, min(ce, se) - max(cs, ss))
            if overlap > best_overlap:
                best_overlap = overlap
                best_i = i
        overlap_ratio = best_overlap / clip_len
        if best_i is None or overlap_ratio < min_overlap_ratio:
            label = -1
            risk_level = "invalid"
            reason = f"no VLM32B source window with overlap_ratio >= {min_overlap_ratio:.3f}"
            src_clip_id = ""
            src_start = ""
            src_end = ""
        else:
            src_row = src.loc[best_i]
            label = parse_yes_no(src_row[cols["relevant_col"]])
            risk_level = str(src_row.get(cols["risk_col"], ""))
            reason = str(src_row.get(cols["reason_col"], ""))
            src_clip_id = str(src_row.get("clip_id", ""))
            src_start = str(src_row.get("start_sec", ""))
            src_end = str(src_row.get("end_sec", ""))
            if label in {0, 1}:
                valid += 1
                positives += int(label == 1)
        out_rows.append(
            {
                "clip_id": clip["clip_id"],
                "start_time": clip["start_time"],
                "end_time": clip["end_time"],
                "clip_path": clip["clip_path"],
                "vlm_label": label,
                "vlm_risk_level": risk_level,
                "vlm_reason": reason,
                "vlm_source_clip_id": src_clip_id,
                "vlm_source_start_sec": src_start,
                "vlm_source_end_sec": src_end,
                "vlm_source_overlap_sec": round(best_overlap, 6),
                "vlm_source_overlap_ratio": round(overlap_ratio, 6),
            }
        )
    labels = pd.DataFrame(out_rows)
    labels.to_csv(labels_path, index=False)
    return {
        "source_path": str(source_path),
        "rows": len(labels),
        "valid": valid,
        "positives": positives,
        "min_overlap_ratio": min_overlap_ratio,
        "relevant_col": cols["relevant_col"],
    }


def load_source_df(pd, cfg: dict):
    source_value = (cfg.get("vlm_labels") or {}).get("source_review_csv")
    if not source_value:
        return None, None, "no vlm_labels.source_review_csv configured"
    source_path = Path(source_value)
    if not source_path.is_absolute():
        fail(f"vlm_labels.source_review_csv must be absolute: {source_path}")
    if not source_path.is_file():
        return source_path, None, f"source file not found: {source_path}"
    return source_path, pd.read_csv(source_path), "ok"


def load_or_adapt_labels(pd, cfg: dict, output_dir: Path, proxy_df):
    vlm_cfg = cfg.get("vlm_labels") or {}
    labels_path = Path(vlm_cfg.get("path", output_dir / "vlm_labels.csv"))
    if not labels_path.is_absolute():
        fail(f"vlm_labels.path must be absolute: {labels_path}")
    check_output_path(labels_path, output_dir)
    block_path = output_dir / "BLOCKED_missing_vlm_labels.md"
    template_path = output_dir / "vlm_labels_template.csv"

    if labels_path.is_file():
        labels = pd.read_csv(labels_path)
        source_path, source_df, source_status = load_source_df(pd, cfg)
        return labels, {
            "mode": "existing",
            "labels_path": str(labels_path),
            "source_path": str(source_path) if source_path else "",
            "source_status": source_status,
            "source_rows": len(source_df) if source_df is not None else 0,
        }, source_df

    source_value = vlm_cfg.get("source_review_csv")
    if source_value:
        source_path = Path(source_value)
        if not source_path.is_absolute():
            fail(f"vlm_labels.source_review_csv must be absolute: {source_path}")
        min_overlap = float(vlm_cfg.get("min_overlap_ratio", 0.5))
        try:
            adapter_info = adapt_vlm_review_csv(pd, proxy_df, source_path, labels_path, min_overlap)
        except Exception as exc:
            write_missing_template(
                pd,
                proxy_df,
                template_path,
                block_path,
                f"Configured VLM source could not be adapted: {exc}",
            )
            fail(f"could not adapt VLM labels. Wrote template and blocking report: {template_path}, {block_path}")
        labels = pd.read_csv(labels_path)
        source_df = pd.read_csv(source_path)
        adapter_info["mode"] = "adapted"
        adapter_info["labels_path"] = str(labels_path)
        adapter_info["source_rows"] = len(source_df)
        return labels, adapter_info, source_df

    write_missing_template(
        pd,
        proxy_df,
        template_path,
        block_path,
        "No VLM label file exists and no explicit `vlm_labels.source_review_csv` was configured.",
    )
    fail(f"missing VLM labels. Wrote template and blocking report: {template_path}, {block_path}")


def validate_labels(labels, proxy_df) -> None:
    schema = label_schema(labels)
    if schema == "conservative":
        required = CONSERVATIVE_LABEL_COLUMNS
    elif schema == "strict_variants":
        required = STRICT_VARIANT_COLUMNS
    elif schema == "exact":
        required = EXACT_LABEL_COLUMNS
    else:
        required = {"clip_id", "start_time", "end_time", "clip_path", "vlm_label", "vlm_risk_level", "vlm_reason"}
    if not required.issubset(labels.columns):
        fail(f"VLM labels missing required columns {sorted(required - set(labels.columns))}; got {list(labels.columns)}")
    missing = set(proxy_df["clip_id"]) - set(labels["clip_id"])
    if missing:
        fail(f"VLM labels missing {len(missing)} proxy clip_id rows, e.g. {sorted(missing)[:3]}")


def robust_minmax(series, np):
    arr = series.astype(float).to_numpy()
    lo = np.nanpercentile(arr, 5)
    hi = np.nanpercentile(arr, 95)
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        lo = np.nanmin(arr)
        hi = np.nanmax(arr)
    if hi <= lo:
        return series.astype(float) * 0.0
    return ((series.astype(float) - lo) / (hi - lo)).clip(0.0, 1.0)


def prepare_eval_base_df(pd, np, proxy_df, labels):
    keep = ["clip_id", "vlm_label", "vlm_risk_level", "vlm_reason"]
    for col in [
        "vlm_relevant",
        "vlm_affected_ego",
        "vlm_event_type",
        "vlm_confidence",
        "raw_response",
        "label_broad",
        "label_ego_relevant",
        "label_strict",
        "label_strict_v2",
        "label_strict_v3",
        "strict_v2_reason",
        "strict_v3_reason",
        "old_vlm_relevant",
        "old_vlm_risk_level",
        "old_vlm_affected_ego",
        "old_vlm_event_type",
        "old_vlm_confidence",
        "conservative_positive",
        "risk_level",
        "affected_ego",
        "event_type",
        "starts_outside_ego_path",
        "enters_ego_path",
        "requires_ego_attention",
        "negative_reason",
        "confidence",
        "evidence",
        "label_conservative_positive",
        "validation_reason",
        "vlm_source_clip_id",
        "vlm_source_start_sec",
        "vlm_source_end_sec",
        "vlm_source_overlap_sec",
        "vlm_source_overlap_ratio",
    ]:
        if col in labels.columns:
            keep.append(col)
    keep = list(dict.fromkeys(keep))
    merged = proxy_df.merge(labels[keep], on="clip_id", how="left")
    merged["vlm_label"] = pd.to_numeric(merged["vlm_label"], errors="coerce").fillna(-1).astype(int)
    merged["start_time"] = pd.to_numeric(merged["start_time"], errors="coerce")
    merged["end_time"] = pd.to_numeric(merged["end_time"], errors="coerce")
    for col in ["score_count", "score_naive", "score_kinematic"]:
        merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0.0)
        merged[f"{col}_norm"] = robust_minmax(merged[col], np)
    merged["ensemble_count_naive_score"] = merged["score_count_norm"] + merged["score_naive_norm"]
    merged["ensemble_all_proxy_score"] = (
        merged["score_count_norm"] + merged["score_naive_norm"] + merged["score_kinematic_norm"]
    )
    merged = merged.sort_values(["start_time", "clip_id"]).reset_index(drop=True)
    merged["time_rank"] = range(len(merged))
    return merged


def detect_variant_capabilities(source_df, labels) -> dict:
    source_cols = set(source_df.columns) if source_df is not None else set()
    label_cols = set(labels.columns)
    risk_cols = [c for c in ["vlm_risk_level", "32b_raw_risk_level", "32b_masked_risk_level"] if c in source_cols]
    affected_cols = [
        c for c in ["vlm_affected_ego", "affected_ego", "ego_related", "32b_raw_affected_ego", "32b_masked_affected_ego"]
        if c in source_cols
    ]
    confidence_cols = [c for c in ["vlm_confidence", "confidence", "32b_raw_confidence", "32b_masked_confidence"] if c in source_cols]
    relevant_cols = [c for c in ["vlm_relevant", "32b_raw_relevant", "32b_masked_relevant"] if c in source_cols]
    label_risk_usable = False
    if "vlm_risk_level" in label_cols and "vlm_label" in label_cols:
        label_tmp = labels.copy()
        label_tmp["vlm_label_num"] = label_tmp["vlm_label"].astype(str).map({"1": 1, "0": 0, "-1": -1})
        label_tmp["risk_rank"] = label_tmp["vlm_risk_level"].map(risk_rank)
        label_risk_usable = bool(((label_tmp["vlm_label_num"] == 1) & (label_tmp["risk_rank"].fillna(-1) > 0)).any())
    source_risk_usable = False
    if risk_cols and source_df is not None:
        relevant_col = None
        for candidate in ["vlm_relevant", "32b_raw_relevant", "32b_masked_relevant"]:
            if candidate in source_df.columns:
                relevant_col = candidate
                break
        if relevant_col:
            for col in risk_cols:
                src_tmp = source_df.copy()
                src_tmp["relevant_num"] = src_tmp[relevant_col].map(parse_yes_no)
                src_tmp["risk_rank"] = src_tmp[col].map(risk_rank)
                if ((src_tmp["relevant_num"] == 1) & (src_tmp["risk_rank"].fillna(-1) > 0)).any():
                    source_risk_usable = True
                    break
    confidence_usable = any(source_df[c].astype(str).str.strip().replace({"": None}).notna().any() for c in confidence_cols) if confidence_cols else False
    return {
        "risk_cols": risk_cols,
        "affected_cols": affected_cols,
        "confidence_cols": confidence_cols,
        "relevant_cols": relevant_cols,
        "strict_available": bool(label_risk_usable or source_risk_usable or affected_cols),
        "high_confidence_available": bool(confidence_usable or relevant_cols),
        "strict_reason": "risk_level or affected_ego available"
        if (label_risk_usable or source_risk_usable or affected_cols)
        else "no usable risk_level rank or affected_ego/ego_related field in current raw 32B source",
        "high_confidence_reason": "explicit yes/no relevance or confidence field available"
        if (confidence_usable or relevant_cols)
        else "no confidence or explicit yes/no relevance field available",
    }


def build_label_variants(pd, base_df, labels, source_df, output_path: Path) -> tuple[object, dict]:
    if label_schema(labels) == "conservative":
        variant_rows = []
        invalid = {"old_strict": 0, "conservative": 0}
        for _, row in base_df.iterrows():
            old_affected = truthy(row.get("old_vlm_affected_ego", ""))
            old_rank = risk_rank(row.get("old_vlm_risk_level", ""))
            if old_affected is None or old_rank is None:
                old_strict = -1
                invalid["old_strict"] += 1
            else:
                old_strict = 1 if old_affected and old_rank >= 2 else 0
            conservative = int(row["vlm_label"]) if int(row["vlm_label"]) in {-1, 0, 1} else -1
            invalid["conservative"] += int(conservative == -1)
            variant_rows.append(
                {
                    "clip_id": row["clip_id"],
                    "start_time": row["start_time"],
                    "end_time": row["end_time"],
                    "clip_path": row["clip_path"],
                    "vlm_label_old_strict": old_strict,
                    "vlm_label_conservative": conservative,
                    "old_vlm_relevant": row.get("old_vlm_relevant", ""),
                    "old_vlm_risk_level": row.get("old_vlm_risk_level", ""),
                    "old_vlm_affected_ego": row.get("old_vlm_affected_ego", ""),
                    "old_vlm_event_type": row.get("old_vlm_event_type", ""),
                    "old_vlm_confidence": row.get("old_vlm_confidence", ""),
                    "conservative_positive": row.get("conservative_positive", ""),
                    "risk_level": row.get("risk_level", ""),
                    "affected_ego": row.get("affected_ego", ""),
                    "event_type": row.get("event_type", ""),
                    "negative_reason": row.get("negative_reason", ""),
                    "confidence": row.get("confidence", ""),
                    "evidence": row.get("evidence", ""),
                    "variant_notes": "old_strict=old affected_ego true and old risk>=L2; conservative=validated conservative_positive label",
                }
            )
        variants = pd.DataFrame(variant_rows)
        variants.to_csv(output_path, index=False)
        info = {
            "label_source_mode": "conservative",
            "broad_available": False,
            "ego_relevant_available": False,
            "strict_available": False,
            "old_strict_available": True,
            "conservative_available": True,
            "strict_v2_available": False,
            "strict_v3_available": False,
            "high_confidence_available": False,
            "strict_reason": "old strict reconstructed from old exact VLM fields",
            "high_confidence_reason": "not used for conservative evaluation",
            "source_risk_cols": ["old_vlm_risk_level", "risk_level"],
            "source_affected_cols": ["old_vlm_affected_ego", "affected_ego"],
            "source_confidence_cols": ["old_vlm_confidence", "confidence"],
            "source_relevant_cols": ["old_vlm_relevant", "conservative_positive"],
            "invalid_counts": invalid,
        }
        return variants, info

    if label_schema(labels) == "strict_variants":
        variant_rows = []
        invalid = {name: 0 for name in ["broad", "ego_relevant", "strict", "strict_v2", "strict_v3"]}
        for _, row in base_df.iterrows():
            values = {}
            for name in invalid:
                src_col = f"label_{name}"
                value = pd.to_numeric(row.get(src_col, -1), errors="coerce")
                value = -1 if pd.isna(value) else int(value)
                if value not in {-1, 0, 1}:
                    value = -1
                values[name] = value
                invalid[name] += int(value == -1)
            variant_rows.append(
                {
                    "clip_id": row["clip_id"],
                    "start_time": row["start_time"],
                    "end_time": row["end_time"],
                    "clip_path": row["clip_path"],
                    "vlm_label_broad": values["broad"],
                    "vlm_label_ego_relevant": values["ego_relevant"],
                    "vlm_label_strict": values["strict"],
                    "vlm_label_strict_v2": values["strict_v2"],
                    "vlm_label_strict_v3": values["strict_v3"],
                    "vlm_relevant": row.get("vlm_relevant", ""),
                    "vlm_risk_level": row.get("vlm_risk_level", ""),
                    "vlm_affected_ego": row.get("vlm_affected_ego", ""),
                    "vlm_event_type": row.get("vlm_event_type", ""),
                    "vlm_confidence": row.get("vlm_confidence", ""),
                    "strict_v2_reason": row.get("strict_v2_reason", ""),
                    "strict_v3_reason": row.get("strict_v3_reason", ""),
                    "variant_notes": (
                        "strict variants pre-derived by 07_strict_label_analysis.py; "
                        "strict_v2 filters weak event types and low confidence; "
                        "strict_v3 keeps L3 or high-confidence L2 cut_in/crossing/sudden_braking/lane_conflict"
                    ),
                }
            )
        variants = pd.DataFrame(variant_rows)
        variants.to_csv(output_path, index=False)
        info = {
            "label_source_mode": "strict_variants",
            "broad_available": True,
            "ego_relevant_available": True,
            "strict_available": True,
            "strict_v2_available": True,
            "strict_v3_available": True,
            "high_confidence_available": False,
            "strict_reason": "strict variants include pre-derived labels from exact VLM fields",
            "high_confidence_reason": "not used as a separate variant for strict-variant evaluation",
            "source_risk_cols": ["vlm_risk_level"],
            "source_affected_cols": ["vlm_affected_ego"],
            "source_confidence_cols": ["vlm_confidence"],
            "source_relevant_cols": ["vlm_relevant"],
            "invalid_counts": invalid,
        }
        return variants, info

    if label_schema(labels) == "exact":
        variant_rows = []
        invalid = {"broad": 0, "ego_relevant": 0, "strict": 0}
        for _, row in base_df.iterrows():
            broad = parse_yes_no(row.get("vlm_relevant", ""))
            ego = normalize_exact_affected(row.get("vlm_affected_ego", ""))
            rank = risk_rank(row.get("vlm_risk_level", ""))
            if broad == -1:
                invalid["broad"] += 1
            if ego == -1:
                invalid["ego_relevant"] += 1
            if ego == -1 or rank is None:
                strict = -1
                invalid["strict"] += 1
            else:
                strict = 1 if ego == 1 and rank >= 2 else 0
            variant_rows.append(
                {
                    "clip_id": row["clip_id"],
                    "start_time": row["start_time"],
                    "end_time": row["end_time"],
                    "clip_path": row["clip_path"],
                    "vlm_label_broad": broad,
                    "vlm_label_ego_relevant": ego,
                    "vlm_label_strict": strict,
                    "vlm_relevant": row.get("vlm_relevant", ""),
                    "vlm_risk_level": row.get("vlm_risk_level", ""),
                    "vlm_affected_ego": row.get("vlm_affected_ego", ""),
                    "vlm_event_type": row.get("vlm_event_type", ""),
                    "vlm_confidence": row.get("vlm_confidence", ""),
                    "variant_notes": (
                        "broad=vlm_relevant==yes; "
                        "ego_relevant=vlm_affected_ego==true; "
                        "strict=vlm_affected_ego==true and vlm_risk_level in {L2,L3}"
                    ),
                }
            )
        variants = pd.DataFrame(variant_rows)
        variants.to_csv(output_path, index=False)
        info = {
            "label_source_mode": "exact",
            "broad_available": True,
            "ego_relevant_available": True,
            "strict_available": True,
            "high_confidence_available": False,
            "strict_reason": "exact labels include vlm_affected_ego and vlm_risk_level",
            "high_confidence_reason": "not used for exact 102-label evaluation",
            "source_risk_cols": ["vlm_risk_level"],
            "source_affected_cols": ["vlm_affected_ego"],
            "source_confidence_cols": ["vlm_confidence"],
            "source_relevant_cols": ["vlm_relevant"],
            "invalid_counts": invalid,
        }
        return variants, info

    caps = detect_variant_capabilities(source_df, labels)
    variant_rows = []
    source_by_id = {}
    if source_df is not None and "clip_id" in source_df.columns:
        source_by_id = {str(r["clip_id"]): r for _, r in source_df.iterrows()}

    for _, row in base_df.iterrows():
        broad = int(row["vlm_label"]) if int(row["vlm_label"]) in {-1, 0, 1} else -1
        notes = ["broad=current mapped vlm_label"]

        strict = ""
        if caps["strict_available"]:
            if broad == -1:
                strict = -1
            else:
                strict_positive = broad == 1
                rank = risk_rank(row.get("vlm_risk_level", ""))
                if rank is not None:
                    strict_positive = strict_positive and rank >= 2
                source_id = str(row.get("vlm_source_clip_id", ""))
                src_row = source_by_id.get(source_id)
                if src_row is not None:
                    for col in caps["risk_cols"]:
                        src_rank = risk_rank(src_row.get(col, ""))
                        if src_rank is not None:
                            strict_positive = strict_positive and src_rank >= 2
                            break
                    for col in caps["affected_cols"]:
                        affected = truthy(src_row.get(col, ""))
                        if affected is not None:
                            strict_positive = strict_positive and affected
                            break
                strict = 1 if strict_positive else 0
            notes.append("strict=requires positive plus usable risk_level>=medium and/or affected_ego=true")
        else:
            notes.append(f"strict unavailable: {caps['strict_reason']}")

        high_conf = ""
        if caps["high_confidence_available"]:
            # Current raw 32B CSV has explicit yes/no relevance but empty confidence.
            # Treat explicit yes/no as high-confidence enough for a separate variant, and document this.
            high_conf = broad
            notes.append("high_confidence=explicit yes/no relevance; no non-empty confidence score required")
        else:
            notes.append(f"high_confidence unavailable: {caps['high_confidence_reason']}")

        variant_rows.append(
            {
                "clip_id": row["clip_id"],
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "clip_path": row["clip_path"],
                "vlm_label_broad": broad,
                "vlm_label_strict": strict,
                "vlm_label_high_confidence": high_conf,
                "variant_notes": "; ".join(notes),
            }
        )
    variants = pd.DataFrame(variant_rows)
    variants.to_csv(output_path, index=False)
    info = {
        "label_source_mode": "mapped",
        "broad_available": True,
        "ego_relevant_available": False,
        "strict_available": caps["strict_available"],
        "high_confidence_available": caps["high_confidence_available"],
        "strict_reason": caps["strict_reason"],
        "high_confidence_reason": caps["high_confidence_reason"],
        "source_risk_cols": caps["risk_cols"],
        "source_affected_cols": caps["affected_cols"],
        "source_confidence_cols": caps["confidence_cols"],
        "source_relevant_cols": caps["relevant_cols"],
    }
    return variants, info


def variant_eval_df(base_df, variants, variant_name: str):
    col = f"vlm_label_{variant_name}"
    if col not in variants.columns:
        return None
    labels = variants[["clip_id", col]].copy()
    labels[col] = labels[col].map(lambda v: float(v) if str(v).strip() not in {"", "nan", "None"} else float("nan"))
    df = base_df.merge(labels, on="clip_id", how="left")
    df["vlm_label"] = df[col]
    df = df[df["vlm_label"].isin([0.0, 1.0])].copy()
    if df.empty:
        return None
    df["vlm_label"] = df["vlm_label"].astype(int)
    return df.sort_values(["start_time", "clip_id"]).reset_index(drop=True)


def metrics_for_selection(selected_ids: list[str], positives: set[str]) -> dict:
    selected_set = set(selected_ids)
    found = len(selected_set & positives)
    total_pos = len(positives)
    selected_n = len(selected_set)
    recall = found / total_pos if total_pos else 0.0
    precision = found / selected_n if selected_n else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall > 0 else 0.0
    return {
        "selected_n": selected_n,
        "positives_found": found,
        "total_positives": total_pos,
        "recall": recall,
        "precision": precision,
        "f1": f1,
    }


def build_events(df, event_merge_gap_sec: float) -> list[dict]:
    positives = df[df["vlm_label"] == 1].sort_values(["start_time", "end_time", "clip_id"])
    events = []
    current = None
    for _, row in positives.iterrows():
        start = float(row["start_time"])
        end = float(row["end_time"])
        if current is None or start - current["last_start"] > event_merge_gap_sec:
            if current is not None:
                events.append(current)
            current = {
                "event_id": len(events) + 1,
                "start_time": start,
                "end_time": end,
                "last_start": start,
                "clip_ids": [row["clip_id"]],
            }
        else:
            current["end_time"] = max(current["end_time"], end)
            current["last_start"] = start
            current["clip_ids"].append(row["clip_id"])
    if current is not None:
        events.append(current)
    return events


def event_metrics_for_selection(df, selected_ids: list[str], events: list[dict]) -> dict:
    selected = df[df["clip_id"].isin(set(selected_ids))]
    hits = 0
    for event in events:
        hit = False
        for _, row in selected.iterrows():
            if max(0.0, min(float(row["end_time"]), event["end_time"]) - max(float(row["start_time"]), event["start_time"])) > 0:
                hit = True
                break
        hits += int(hit)
    total = len(events)
    return {
        "num_events": total,
        "num_events_hit": hits,
        "event_recall": hits / total if total else 0.0,
    }


def top_by_score(df, score_col: str, budget: int) -> list[str]:
    return (
        df.sort_values([score_col, "start_time", "clip_id"], ascending=[False, True, True])
        .head(budget)["clip_id"]
        .tolist()
    )


def uniform_time(df, np, budget: int) -> list[str]:
    if budget >= len(df):
        return df["clip_id"].tolist()
    positions = np.linspace(0, len(df) - 1, budget)
    indices = []
    used = set()
    for pos in positions:
        idx = int(round(float(pos)))
        while idx in used and idx + 1 < len(df):
            idx += 1
        while idx in used and idx - 1 >= 0:
            idx -= 1
        used.add(idx)
        indices.append(idx)
    return df.iloc[sorted(indices)]["clip_id"].tolist()


def random_select(df, np, budget: int, seed: int) -> list[str]:
    rng = np.random.default_rng(seed)
    indices = rng.choice(len(df), size=min(budget, len(df)), replace=False)
    return df.iloc[indices]["clip_id"].tolist()


def interval_distance(a_start, a_end, b_start, b_end) -> float:
    if a_end < b_start:
        return b_start - a_end
    if b_end < a_start:
        return a_start - b_end
    return 0.0


def temporal_nms(df, score_col: str, budget: int, gap_sec: float) -> list[str]:
    ordered = df.sort_values([score_col, "start_time", "clip_id"], ascending=[False, True, True])
    selected = []
    selected_intervals = []
    for _, row in ordered.iterrows():
        start, end = float(row["start_time"]), float(row["end_time"])
        too_close = any(interval_distance(start, end, s, e) < gap_sec for s, e in selected_intervals)
        if too_close:
            continue
        selected.append(row["clip_id"])
        selected_intervals.append((start, end))
        if len(selected) >= budget:
            return selected
    if len(selected) < budget:
        selected_set = set(selected)
        for _, row in ordered.iterrows():
            if row["clip_id"] not in selected_set:
                selected.append(row["clip_id"])
                selected_set.add(row["clip_id"])
            if len(selected) >= budget:
                break
    return selected[:budget]


def expansion_neighbors(df, idx: int, radius: int) -> list[int]:
    out = []
    for step in range(1, radius + 1):
        left = idx - step
        right = idx + step
        if left >= 0:
            out.append(left)
        if right < len(df):
            out.append(right)
    return out


def expansion_strategy(df, anchor_order: list[int], budget: int, radius: int, anchor_fraction: float) -> list[str]:
    selected = []
    selected_idx = set()
    anchor_budget = max(1, min(budget, int(math.ceil(anchor_fraction * budget))))
    anchors_queried = 0
    for idx in anchor_order:
        if len(selected) >= budget or anchors_queried >= anchor_budget:
            break
        if idx in selected_idx:
            continue
        selected_idx.add(idx)
        selected.append(df.iloc[idx]["clip_id"])
        anchors_queried += 1
        if len(selected) >= budget:
            break
        if int(df.iloc[idx]["vlm_label"]) == 1:
            for nidx in expansion_neighbors(df, idx, radius):
                if nidx not in selected_idx:
                    selected_idx.add(nidx)
                    selected.append(df.iloc[nidx]["clip_id"])
                if len(selected) >= budget:
                    break
    if len(selected) < budget:
        for idx in anchor_order:
            if idx not in selected_idx:
                selected_idx.add(idx)
                selected.append(df.iloc[idx]["clip_id"])
            if len(selected) >= budget:
                break
    if len(selected) < budget:
        for idx in range(len(df)):
            if idx not in selected_idx:
                selected_idx.add(idx)
                selected.append(df.iloc[idx]["clip_id"])
            if len(selected) >= budget:
                break
    return selected[:budget]


def anchor_order_for_score(df, score_col: str) -> list[int]:
    ordered = df.sort_values([score_col, "start_time", "clip_id"], ascending=[False, True, True])
    id_to_idx = {cid: i for i, cid in enumerate(df["clip_id"])}
    return [id_to_idx[cid] for cid in ordered["clip_id"]]


def selection_for_method(
    df,
    np,
    method: str,
    budget: int,
    seed: int,
    gap_sec: float,
    radius: int,
    anchor_fraction: float,
) -> list[str]:
    if budget >= len(df):
        return df["clip_id"].tolist()
    if method == "random":
        return random_select(df, np, budget, seed)
    if method == "uniform_time":
        return uniform_time(df, np, budget)
    if method == "top_count":
        return top_by_score(df, "score_count", budget)
    if method == "top_naive":
        return top_by_score(df, "score_naive", budget)
    if method == "top_kinematic":
        return top_by_score(df, "score_kinematic", budget)
    if method == "ensemble_count_naive":
        return top_by_score(df, "ensemble_count_naive_score", budget)
    if method == "ensemble_all_proxy":
        return top_by_score(df, "ensemble_all_proxy_score", budget)
    if method == "temporal_nms_count":
        return temporal_nms(df, "score_count", budget, gap_sec)
    if method == "temporal_nms_naive":
        return temporal_nms(df, "score_naive", budget, gap_sec)
    if method == "temporal_nms_ensemble":
        return temporal_nms(df, "ensemble_count_naive_score", budget, gap_sec)
    if method == "uniform_expansion":
        anchor_ids = uniform_time(df, np, len(df))
        id_to_idx = {cid: i for i, cid in enumerate(df["clip_id"])}
        return expansion_strategy(df, [id_to_idx[cid] for cid in anchor_ids], budget, radius, anchor_fraction)
    if method == "proxy_then_expansion_count":
        return expansion_strategy(df, anchor_order_for_score(df, "score_count"), budget, radius, anchor_fraction)
    if method == "proxy_then_expansion_naive":
        return expansion_strategy(df, anchor_order_for_score(df, "score_naive"), budget, radius, anchor_fraction)
    if method in {"proxy_then_expansion", "proxy_then_expansion_ensemble"}:
        return expansion_strategy(
            df, anchor_order_for_score(df, "ensemble_count_naive_score"), budget, radius, anchor_fraction
        )
    raise ValueError(f"unknown method: {method}")


def selection_for_sweep_policy(df, np, method: str, budget: int, gap_sec: float, radius: int, anchor_fraction: float) -> list[str]:
    if method == "uniform_expansion":
        anchor_ids = uniform_time(df, np, len(df))
        id_to_idx = {cid: i for i, cid in enumerate(df["clip_id"])}
        return expansion_strategy(df, [id_to_idx[cid] for cid in anchor_ids], budget, radius, anchor_fraction)
    if method == "proxy_then_expansion_count":
        return expansion_strategy(df, anchor_order_for_score(df, "score_count"), budget, radius, anchor_fraction)
    if method == "proxy_then_expansion_naive":
        return expansion_strategy(df, anchor_order_for_score(df, "score_naive"), budget, radius, anchor_fraction)
    if method in {"proxy_then_expansion_ensemble", "proxy_then_expansion_ensemble_count_naive"}:
        return expansion_strategy(df, anchor_order_for_score(df, "ensemble_count_naive_score"), budget, radius, anchor_fraction)
    if method == "temporal_nms_count":
        return temporal_nms(df, "score_count", budget, gap_sec)
    if method == "temporal_nms_naive":
        return temporal_nms(df, "score_naive", budget, gap_sec)
    if method == "temporal_nms_ensemble":
        return temporal_nms(df, "ensemble_count_naive_score", budget, gap_sec)
    raise ValueError(f"unknown sweep method: {method}")


def evaluate_variant(pd, np, df, cfg, label_variant: str):
    ratios = [float(v) for v in cfg.get("budget_ratios", [0.05, 0.10, 0.15, 0.20, 0.30, 0.50])]
    seed_count = int(cfg.get("random_seeds", 20))
    seeds = list(range(seed_count))
    gap_sec = float(cfg.get("temporal_nms_gap_sec", 4.0))
    event_gap = float(cfg.get("event_merge_gap_sec", 4.0))
    radius = int(cfg.get("expansion_radius", 2))
    anchor_fraction = float(cfg.get("anchor_fraction", 0.5))
    positives = set(df[df["vlm_label"] == 1]["clip_id"])
    events = build_events(df, event_gap)
    raw_rows = []
    selected_rows = []
    n = len(df)
    for ratio in ratios:
        budget = min(n, max(1, int(math.ceil(ratio * n))))
        for method in METHODS:
            method_seeds = seeds if method == "random" else [0]
            for seed in method_seeds:
                selected = selection_for_method(df, np, method, budget, seed, gap_sec, radius, anchor_fraction)
                clip_m = metrics_for_selection(selected, positives)
                event_m = event_metrics_for_selection(df, selected, events)
                common = {
                    "label_variant": label_variant,
                    "method": method,
                    "budget_ratio": ratio,
                    "budget": budget,
                    "seed": seed,
                    "calls_saved_vs_full_scan": n - budget,
                    "calls_saved_fraction": (n - budget) / n if n else 0.0,
                    **clip_m,
                    **event_m,
                }
                raw_rows.append({**common, "metric_level": "clip", "metric_recall": clip_m["recall"]})
                raw_rows.append({**common, "metric_level": "event", "metric_recall": event_m["event_recall"]})
                for rank, clip_id in enumerate(selected, start=1):
                    row = df[df["clip_id"] == clip_id].iloc[0]
                    selected_rows.append(
                        {
                            "label_variant": label_variant,
                            "method": method,
                            "budget_ratio": ratio,
                            "budget": budget,
                            "seed": seed,
                            "selection_rank": rank,
                            "clip_id": clip_id,
                            "start_time": row["start_time"],
                            "end_time": row["end_time"],
                            "vlm_label": int(row["vlm_label"]),
                            "score_count": row["score_count"],
                            "score_naive": row["score_naive"],
                            "score_kinematic": row["score_kinematic"],
                            "ensemble_count_naive_score": row["ensemble_count_naive_score"],
                            "ensemble_all_proxy_score": row["ensemble_all_proxy_score"],
                        }
                    )
    raw = pd.DataFrame(raw_rows)
    agg = (
        raw.groupby(["label_variant", "metric_level", "method", "budget_ratio", "budget"], as_index=False)
        .agg(
            recall_mean=("metric_recall", "mean"),
            recall_std=("metric_recall", "std"),
            precision_mean=("precision", "mean"),
            precision_std=("precision", "std"),
            f1_mean=("f1", "mean"),
            f1_std=("f1", "std"),
            positives_found_mean=("positives_found", "mean"),
            selected_n_mean=("selected_n", "mean"),
            total_positives=("total_positives", "max"),
            event_recall=("event_recall", "mean"),
            event_recall_std=("event_recall", "std"),
            num_events=("num_events", "max"),
            num_events_hit=("num_events_hit", "mean"),
            calls_saved_vs_full_scan=("calls_saved_vs_full_scan", "max"),
            calls_saved_fraction=("calls_saved_fraction", "max"),
        )
        .fillna(0.0)
    )
    return raw, agg, pd.DataFrame(selected_rows), events


def evaluate_methods(pd, np, base_df, variants, variant_info, cfg):
    raw_parts = []
    agg_parts = []
    selected_parts = []
    events_by_variant = {}
    variant_order = available_variant_names(variant_info)
    for variant in variant_order:
        if variant == "ego_relevant" and not variant_info.get("ego_relevant_available", False):
            continue
        if variant == "strict" and not variant_info["strict_available"]:
            continue
        if variant == "high_confidence" and not variant_info["high_confidence_available"]:
            continue
        df = variant_eval_df(base_df, variants, variant)
        if df is None or df.empty:
            continue
        raw, agg, selected, events = evaluate_variant(pd, np, df, cfg, variant)
        raw_parts.append(raw)
        agg_parts.append(agg)
        selected_parts.append(selected)
        events_by_variant[variant] = events
    if not agg_parts:
        fail("no label variants with valid {0,1} labels are available")
    return pd.concat(raw_parts, ignore_index=True), pd.concat(agg_parts, ignore_index=True), pd.concat(selected_parts, ignore_index=True), events_by_variant


def evaluate_policy_sweep(pd, np, base_df, variants, cfg, variant_info=None):
    ratios = [float(v) for v in cfg.get("budget_ratios", [0.05, 0.10, 0.15, 0.20, 0.30, 0.50])]
    sweep_cfg = cfg.get("policy_sweep") or {}
    radii = [int(v) for v in sweep_cfg.get("expansion_radius", [1, 2, 3])]
    anchor_fracs = [float(v) for v in sweep_cfg.get("anchor_fraction", [0.25, 0.5, 0.75])]
    gaps = [float(v) for v in sweep_cfg.get("temporal_nms_gap_sec", [0, 2, 4, 6, 8])]
    event_gap = float(cfg.get("event_merge_gap_sec", 4.0))
    rows = []
    if variant_info and variant_info.get("label_source_mode") in {"exact", "strict_variants", "conservative"}:
        variant_order = available_variant_names(variant_info)
    else:
        variant_order = ["broad"]
    for variant in variant_order:
        df = variant_eval_df(base_df, variants, variant)
        if df is None or df.empty:
            continue
        positives = set(df[df["vlm_label"] == 1]["clip_id"])
        events = build_events(df, event_gap)
        n = len(df)
        for ratio in ratios:
            budget = min(n, max(1, int(math.ceil(ratio * n))))
            for method in SWEEP_METHODS:
                if method.startswith("temporal_nms"):
                    for gap in gaps:
                        selected = selection_for_sweep_policy(df, np, method, budget, gap, 0, 0.0)
                        clip_m = metrics_for_selection(selected, positives)
                        event_m = event_metrics_for_selection(df, selected, events)
                        rows.append(
                            {
                                "label_variant": variant,
                                "method": method,
                                "budget_ratio": ratio,
                                "budget": budget,
                                "expansion_radius": "",
                                "anchor_fraction": "",
                                "temporal_nms_gap_sec": gap,
                                **clip_m,
                                **event_m,
                            }
                        )
                else:
                    for radius in radii:
                        for anchor_fraction in anchor_fracs:
                            selected = selection_for_sweep_policy(df, np, method, budget, 0.0, radius, anchor_fraction)
                            clip_m = metrics_for_selection(selected, positives)
                            event_m = event_metrics_for_selection(df, selected, events)
                            rows.append(
                                {
                                    "label_variant": variant,
                                    "method": method,
                                    "budget_ratio": ratio,
                                    "budget": budget,
                                    "expansion_radius": radius,
                                    "anchor_fraction": anchor_fraction,
                                    "temporal_nms_gap_sec": "",
                                    **clip_m,
                                    **event_m,
                                }
                            )
    return pd.DataFrame(rows)


def fmt_mean_std(mean: float, std: float, stochastic: bool) -> str:
    return f"{mean:.3f} ± {std:.3f}" if stochastic else f"{mean:.3f}"


def best_methods_by_budget(agg, variant: str, metric_level: str):
    out = {}
    subagg = agg[(agg["label_variant"] == variant) & (agg["metric_level"] == metric_level)]
    for ratio, group in subagg.groupby("budget_ratio"):
        best_recall = group["recall_mean"].max()
        winners = group[group["recall_mean"] == best_recall]["method"].tolist()
        out[ratio] = (best_recall, winners)
    return out


def compare_avg(agg, methods: list[str], ratios: list[float], variant: str, metric_level: str) -> tuple[str, float]:
    sub = agg[
        (agg["label_variant"] == variant)
        & (agg["metric_level"] == metric_level)
        & (agg["method"].isin(methods))
        & (agg["budget_ratio"].isin(ratios))
    ]
    if sub.empty:
        return "NA", 0.0
    means = sub.groupby("method")["recall_mean"].mean().sort_values(ascending=False)
    return means.index[0], float(means.iloc[0])


def avg_recall(agg, method, ratios, variant: str, metric_level: str):
    sub = agg[
        (agg["label_variant"] == variant)
        & (agg["metric_level"] == metric_level)
        & (agg["method"] == method)
        & (agg["budget_ratio"].isin(ratios))
    ]
    return float(sub["recall_mean"].mean()) if not sub.empty else 0.0


def available_variant_names(variant_info: dict) -> list[str]:
    if variant_info.get("label_source_mode") == "conservative":
        return ["old_strict", "conservative"]
    if variant_info.get("label_source_mode") == "strict_variants":
        return ["broad", "ego_relevant", "strict", "strict_v2", "strict_v3"]
    if variant_info.get("label_source_mode") == "exact":
        return ["broad", "ego_relevant", "strict"]
    names = ["broad"]
    if variant_info.get("strict_available"):
        names.append("strict")
    if variant_info.get("high_confidence_available"):
        names.append("high_confidence")
    return names


def variant_summary(base_df, variants, variant: str, event_gap: float) -> dict:
    df = variant_eval_df(base_df, variants, variant)
    if df is None or df.empty:
        return {
            "valid": 0,
            "positives": 0,
            "rate": 0.0,
            "events": 0,
            "avg_run": 0.0,
        }
    positives = int((df["vlm_label"] == 1).sum())
    return {
        "valid": len(df),
        "positives": positives,
        "rate": positives / len(df) if len(df) else 0.0,
        "events": len(build_events(df, event_gap)),
        "avg_run": avg_positive_run_length(df),
    }


def best_low_budget_method(agg, variant: str, metric_level: str, ratios: list[float]) -> tuple[str, float]:
    low_ratios = [r for r in ratios if r <= 0.20]
    return compare_avg(agg, METHODS, low_ratios, variant, metric_level)


def mean_sweep_recall(sweep, variant: str, methods: list[str], metric: str) -> float:
    if sweep is None or sweep.empty:
        return 0.0
    sub = sweep[(sweep["label_variant"] == variant) & (sweep["method"].isin(methods))]
    return float(sub[metric].mean()) if not sub.empty else 0.0


def write_label_diagnostics(path: Path, labels, proxy_df, source_df, adapter_info, variant_info) -> None:
    valid = labels[labels["vlm_label"].isin([0, 1])] if labels["vlm_label"].dtype != object else labels[labels["vlm_label"].astype(str).isin(["0", "1"])]
    valid_labels = labels.copy()
    valid_labels["vlm_label_num"] = valid_labels["vlm_label"].astype(str).map({"1": 1, "0": 0, "-1": -1})
    valid_sorted = valid_labels[valid_labels["vlm_label_num"].isin([0, 1])].copy()
    valid_sorted["start_time"] = valid_sorted["start_time"].astype(float)
    valid_sorted = valid_sorted.sort_values(["start_time", "clip_id"])
    transitions = {}
    names = {1: "positive", 0: "negative"}
    previous = None
    for label in valid_sorted["vlm_label_num"].tolist():
        if previous is not None:
            key = f"{names[previous]}->{names[label]}"
            transitions[key] = transitions.get(key, 0) + 1
        previous = label
    run_lengths = []
    current = 0
    for label in valid_sorted["vlm_label_num"].tolist():
        if label == 1:
            current += 1
        elif current:
            run_lengths.append(current)
            current = 0
    if current:
        run_lengths.append(current)
    avg_run = sum(run_lengths) / len(run_lengths) if run_lengths else 0.0
    positive_count = int((valid_sorted["vlm_label_num"] == 1).sum())
    valid_count = len(valid_sorted)
    invalid_count = int((valid_labels["vlm_label_num"] == -1).sum())
    source_count = len(source_df) if source_df is not None else int(adapter_info.get("source_rows", 0))
    source_path = adapter_info.get("source_path", "")

    mode = variant_info.get("label_source_mode", "mapped")
    if mode == "strict_variants":
        title = "# Strict Variant VLM Label Diagnostics"
    elif mode == "conservative":
        title = "# Conservative VLM Label Diagnostics"
    elif mode == "exact":
        title = "# Exact 102-Clip VLM Label Diagnostics"
    else:
        title = "# VLM Label Mapping Diagnostics"
    lines = [
        title,
        "",
        f"- VLM source file path: {source_path or 'unknown'}",
        f"- original VLM window count: {source_count}",
        f"- proxy clip count: {len(proxy_df)}",
        f"- valid label count: {valid_count}",
        f"- invalid count: {invalid_count}",
        f"- positive count: {positive_count}",
        f"- positive rate: {positive_count / valid_count if valid_count else 0.0:.3f}",
        f"- label source mode: {mode}",
        f"- ego-relevant label availability: {variant_info.get('ego_relevant_available', False)}",
        f"- strict label availability: {variant_info['strict_available']} ({variant_info['strict_reason']})",
        f"- high-confidence label availability: {variant_info['high_confidence_available']} ({variant_info['high_confidence_reason']})",
        "",
        "## Adjacent Label Transitions",
        "",
    ]
    for key in ["positive->positive", "positive->negative", "negative->positive", "negative->negative"]:
        lines.append(f"- {key}: {transitions.get(key, 0)}")
    lines.extend(
        [
            f"- average positive run length: {avg_run:.3f} clips",
            "",
            "## Mapping Table",
            "",
        ]
    )
    needed = {"vlm_source_clip_id", "vlm_source_overlap_ratio"}
    if needed.issubset(labels.columns):
        lines.append("| proxy_clip_id | mapped_vlm_window_id | overlap_ratio | label |")
        lines.append("|---|---|---:|---:|")
        for _, row in labels.sort_values(["start_time", "clip_id"]).iterrows():
            lines.append(
                f"| {row['clip_id']} | {row.get('vlm_source_clip_id', '')} | "
                f"{float(row.get('vlm_source_overlap_ratio', 0.0)):.3f} | {row['vlm_label']} |"
            )
    elif mode in {"exact", "strict_variants"}:
        lines.append("| clip_id | relevant | risk_level | affected_ego | event_type | confidence |")
        lines.append("|---|---|---|---|---|---|")
        for _, row in labels.sort_values(["start_time", "clip_id"]).iterrows():
            affected_text = str(row.get("vlm_affected_ego", "")).strip().lower()
            lines.append(
                f"| {row['clip_id']} | {row.get('vlm_relevant', '')} | {row.get('vlm_risk_level', '')} | "
                f"{affected_text} | {row.get('vlm_event_type', '')} | {row.get('vlm_confidence', '')} |"
            )
    elif mode == "conservative":
        lines.append("| clip_id | old_strict_label | conservative_label | event_type | negative_reason | confidence |")
        lines.append("|---|---:|---:|---|---|---|")
        for _, row in labels.sort_values(["start_time", "clip_id"]).iterrows():
            old_affected = truthy(row.get("old_vlm_affected_ego", ""))
            old_rank = risk_rank(row.get("old_vlm_risk_level", ""))
            old_strict = 1 if old_affected and old_rank is not None and old_rank >= 2 else 0
            lines.append(
                f"| {row['clip_id']} | {old_strict} | {row.get('vlm_label', '')} | "
                f"{row.get('event_type', '')} | {row.get('negative_reason', '')} | {row.get('confidence', '')} |"
            )
    else:
        lines.append("Current `vlm_labels.csv` lacks `vlm_source_clip_id` and/or `vlm_source_overlap_ratio`; per-clip mapping diagnostics are unavailable.")
    if mode == "conservative":
        lines.extend(
            [
                "",
                "## Conservative Predicate Boundary",
                "",
                "- These labels are direct clip_id-level Qwen3-VL-32B pseudo labels produced with the conservative prompt.",
                "- old_strict is reconstructed from previous exact VLM fields for comparison.",
                "- Conservative labels remain VLM pseudo-GT, not human ground truth.",
            ]
        )
    elif mode == "strict_variants":
        lines.extend(
            [
                "",
                "## Strict Variant Boundary",
                "",
                "- These labels are derived from exact clip_id-level Qwen3-VL-32B pseudo labels.",
                "- strict_v2 / strict_v3 are post-processing filters over VLM fields, not new VLM calls and not human ground truth.",
            ]
        )
    elif mode == "exact":
        lines.extend(
            [
                "",
                "## Exact-Label Boundary",
                "",
                "- These labels are direct clip_id-level Qwen3-VL-32B pseudo labels for the 102 proxy clips.",
                "- They remove the 67-window overlap-mapping ambiguity but remain VLM pseudo-GT, not human ground truth.",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "## Temporal-Overlap Mapping Risk",
                "",
                "- Current labels map 67 original 6s stride3 VLM windows onto 102 5s stride2 proxy clips by time overlap.",
                "- One VLM decision can label multiple overlapping proxy clips, inflating apparent temporal continuity.",
                "- Clip-level recall can therefore over-credit expansion policies that harvest adjacent windows from the same mapped VLM segment.",
                "- Event-level recall is reported to reduce this duplication effect, but exact 102-clip VLM labels remain the cleaner evaluation target.",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_exact_label_todo(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "# TODO: Exact 102-Clip VLM32B Labels",
                "",
                "The cleanest next step is to run the same 32B VLM prompt directly on the 102 clips in:",
                "",
                "```text",
                "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/proxy_scores.csv",
                "```",
                "",
                "Expected output schema:",
                "",
                "```text",
                "clip_id,start_time,end_time,clip_path,vlm_label,vlm_risk_level,vlm_affected_ego,vlm_reason",
                "```",
                "",
                "Why this matters:",
                "",
                "- The current pseudo labels come from 67 original 6s stride3 VLM windows.",
                "- They are mapped onto 102 5s stride2 proxy clips by temporal overlap.",
                "- This preliminary mapping can duplicate one VLM decision across neighboring proxy clips.",
                "- Exact clip_id-level labels would remove the main alignment ambiguity and make clip-level budget curves cleaner.",
                "",
                "Do not treat the current overlap-mapped labels as final ground truth.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def write_report(path: Path, agg, base_df, variants, variant_info, cfg, events_by_variant, sweep=None) -> None:
    ratios = [float(v) for v in cfg.get("budget_ratios", [0.05, 0.10, 0.15, 0.20, 0.30, 0.50])]
    event_gap = float(cfg.get("event_merge_gap_sec", 4.0))
    variant_names = available_variant_names(variant_info)
    lines = [
        "# VLM32B Pseudo-GT Budget Simulation",
        "",
        "This report treats the available VLM32B scan as pseudo-GT / pseudo-oracle. It does not measure true real-world danger detection accuracy.",
        "",
        "## Data Overview",
        "",
        f"- number of clips in proxy_scores: {len(base_df)}",
        f"- budget ratios: {', '.join(f'{r:.2f}' for r in ratios)}",
        f"- methods evaluated: {', '.join(METHODS)}",
        f"- event_merge_gap_sec: {float(cfg.get('event_merge_gap_sec', 4.0)):.3f}",
        f"- broad label available: {variant_info['broad_available']}",
        f"- ego-relevant label available: {variant_info.get('ego_relevant_available', False)}",
        f"- strict label available: {variant_info['strict_available']} ({variant_info['strict_reason']})",
        f"- high-confidence label available: {variant_info['high_confidence_available']} ({variant_info['high_confidence_reason']})",
        "",
        "## Variant Overview",
        "",
        "| variant | valid clips | positives | positive rate | events |",
        "|---|---:|---:|---:|---:|",
    ]
    available_variants = []
    summaries = {}
    for variant in variant_names:
        df = variant_eval_df(base_df, variants, variant)
        if df is None or df.empty:
            continue
        available_variants.append(variant)
        summary = variant_summary(base_df, variants, variant, event_gap)
        summaries[variant] = summary
        lines.append(
            f"| {variant} | {summary['valid']} | {summary['positives']} | {summary['rate']:.3f} | {summary['events']} |"
        )
        if summary["positives"] < 5:
            lines.append(f"| {variant} warning | fewer than 5 positives; curves are unstable |  |  |  |")

    if variant_info.get("label_source_mode") == "conservative":
        old = summaries.get("old_strict", {})
        cons = summaries.get("conservative", {})
        lines.extend(["", "## Conservative Predicate Answers", ""])
        lines.append(
            f"- old_strict positive rate={old.get('rate', 0.0):.3f} "
            f"({old.get('positives', 0)}/{old.get('valid', 0)}); "
            f"conservative positive rate={cons.get('rate', 0.0):.3f} "
            f"({cons.get('positives', 0)}/{cons.get('valid', 0)})."
        )
        lines.append(
            f"- positive events: old_strict={old.get('events', 0)}, conservative={cons.get('events', 0)}."
        )
        lines.append(
            f"- average positive run length: old_strict={old.get('avg_run', 0.0):.3f}, "
            f"conservative={cons.get('avg_run', 0.0):.3f} clips."
        )
        for variant in ["old_strict", "conservative"]:
            clip_method, clip_val = best_low_budget_method(agg, variant, "clip", ratios)
            event_method, event_val = best_low_budget_method(agg, variant, "event", ratios)
            lines.append(
                f"- {variant}: low-budget 5%-20% best clip recall `{clip_method}` ({clip_val:.3f}); "
                f"best event recall `{event_method}` ({event_val:.3f})."
            )
        for variant in ["old_strict", "conservative"]:
            nms_event = max(
                avg_recall(agg, "temporal_nms_count", ratios, variant, "event"),
                avg_recall(agg, "temporal_nms_naive", ratios, variant, "event"),
                avg_recall(agg, "temporal_nms_ensemble", ratios, variant, "event"),
            )
            random_clip = avg_recall(agg, "random", [r for r in ratios if r <= 0.20], variant, "clip")
            best_clip_method, best_clip = best_low_budget_method(agg, variant, "clip", ratios)
            proxy_event = mean_sweep_recall(
                sweep,
                variant,
                ["proxy_then_expansion_count", "proxy_then_expansion_naive", "proxy_then_expansion_ensemble"],
                "event_recall",
            )
            uniform_event = mean_sweep_recall(sweep, variant, ["uniform_expansion"], "event_recall")
            lines.append(
                f"- {variant}: best low-budget clip recall vs random={best_clip:.3f}/{random_clip:.3f}; "
                f"temporal-NMS best avg event recall={nms_event:.3f}; "
                f"proxy-anchor sweep avg event recall={proxy_event:.3f} vs uniform-anchor={uniform_event:.3f}."
            )
        clip_method, _ = best_low_budget_method(agg, "conservative", "clip", ratios)
        event_method, _ = best_low_budget_method(agg, "conservative", "event", ratios)
        if clip_method != event_method:
            lines.append(
                "- Temporal-aware allocation remains supported under conservative pseudo-GT because clip recovery and event coverage prefer different policies."
            )
        else:
            lines.append(
                "- Temporal-aware allocation evidence is weaker under conservative pseudo-GT because clip and event winners align."
            )

    if variant_info.get("label_source_mode") == "strict_variants":
        lines.extend(["", "## Strict Variant Answers", ""])
        strict_v2 = summaries.get("strict_v2", {})
        strict_v3 = summaries.get("strict_v3", {})
        lines.append(
            f"1. strict_v2 positive rate={strict_v2.get('rate', 0.0):.3f} "
            f"({strict_v2.get('positives', 0)}/{strict_v2.get('valid', 0)}); "
            f"strict_v3 positive rate={strict_v3.get('rate', 0.0):.3f} "
            f"({strict_v3.get('positives', 0)}/{strict_v3.get('valid', 0)})."
        )
        if 0.10 <= strict_v2.get("rate", 0.0) <= 0.30 or 0.10 <= strict_v3.get("rate", 0.0) <= 0.30:
            lines.append("2. At least one stricter variant reaches the target 10%-30% positive-rate range.")
        else:
            lines.append("2. Neither strict_v2 nor strict_v3 reaches the target 10%-30% range.")
        lines.append(
            "3. If still high, the likely cause is that the source VLM already marks many clips as "
            "high-confidence L2 ego-relevant cut_in/crossing events; field-level post-processing has little remaining leverage."
        )
        lines.append(
            f"4. positive events: strict_v2={strict_v2.get('events', 0)}, strict_v3={strict_v3.get('events', 0)}."
        )
        lines.append(
            f"5. average positive run length: strict_v2={strict_v2.get('avg_run', 0.0):.3f}, "
            f"strict_v3={strict_v3.get('avg_run', 0.0):.3f} clips."
        )
        for variant in ["strict_v2", "strict_v3"]:
            clip_method, clip_val = best_low_budget_method(agg, variant, "clip", ratios)
            event_method, event_val = best_low_budget_method(agg, variant, "event", ratios)
            lines.append(
                f"6-7. {variant}: low-budget 5%-20% best clip recall is `{clip_method}` ({clip_val:.3f}); "
                f"best event recall is `{event_method}` ({event_val:.3f})."
            )
        for variant in ["strict_v2", "strict_v3"]:
            nms_event = max(
                avg_recall(agg, "temporal_nms_count", ratios, variant, "event"),
                avg_recall(agg, "temporal_nms_naive", ratios, variant, "event"),
                avg_recall(agg, "temporal_nms_ensemble", ratios, variant, "event"),
            )
            top_event = max(
                avg_recall(agg, "top_count", ratios, variant, "event"),
                avg_recall(agg, "top_naive", ratios, variant, "event"),
                avg_recall(agg, "ensemble_count_naive", ratios, variant, "event"),
            )
            expansion_clip = max(
                avg_recall(agg, "uniform_expansion", ratios, variant, "clip"),
                avg_recall(agg, "proxy_then_expansion_count", ratios, variant, "clip"),
                avg_recall(agg, "proxy_then_expansion_naive", ratios, variant, "clip"),
                avg_recall(agg, "proxy_then_expansion_ensemble", ratios, variant, "clip"),
            )
            expansion_event = max(
                avg_recall(agg, "uniform_expansion", ratios, variant, "event"),
                avg_recall(agg, "proxy_then_expansion_count", ratios, variant, "event"),
                avg_recall(agg, "proxy_then_expansion_naive", ratios, variant, "event"),
                avg_recall(agg, "proxy_then_expansion_ensemble", ratios, variant, "event"),
            )
            proxy_event = mean_sweep_recall(
                sweep,
                variant,
                ["proxy_then_expansion_count", "proxy_then_expansion_naive", "proxy_then_expansion_ensemble"],
                "event_recall",
            )
            uniform_event = mean_sweep_recall(sweep, variant, ["uniform_expansion"], "event_recall")
            top_count_clip = avg_recall(agg, "top_count", ratios, variant, "clip")
            top_naive_clip = avg_recall(agg, "top_naive", ratios, variant, "clip")
            ensemble_clip = avg_recall(agg, "ensemble_count_naive", ratios, variant, "clip")
            kin_clip = avg_recall(agg, "top_kinematic", ratios, variant, "clip")
            kin_event = avg_recall(agg, "top_kinematic", ratios, variant, "event")
            lines.append(
                f"8-12. {variant}: temporal-NMS best avg event recall={nms_event:.3f} vs top/ensemble best={top_event:.3f}; "
                f"expansion avg best clip/event recall={expansion_clip:.3f}/{expansion_event:.3f}; "
                f"proxy-anchor sweep avg event recall={proxy_event:.3f} vs uniform-anchor={uniform_event:.3f}; "
                f"top_count/top_naive/ensemble avg clip recall={top_count_clip:.3f}/{top_naive_clip:.3f}/{ensemble_clip:.3f}; "
                f"top_kinematic avg clip/event recall={kin_clip:.3f}/{kin_event:.3f}."
            )
        divergence_notes = []
        for variant in ["strict_v2", "strict_v3"]:
            clip_method, _ = best_low_budget_method(agg, variant, "clip", ratios)
            event_method, _ = best_low_budget_method(agg, variant, "event", ratios)
            if clip_method != event_method:
                divergence_notes.append(f"{variant}: clip `{clip_method}` vs event `{event_method}`")
        if divergence_notes:
            lines.append("13. Temporal-aware budget allocation is supported because dense clip recovery and event coverage prefer different policies: " + "; ".join(divergence_notes) + ".")
        else:
            lines.append("13. Temporal-aware allocation evidence is weaker because clip and event winners align for strict_v2/strict_v3.")
        kin_strong = any(
            avg_recall(agg, "top_kinematic", ratios, variant, "clip")
            >= max(avg_recall(agg, "top_count", ratios, variant, "clip"), avg_recall(agg, "top_naive", ratios, variant, "clip"))
            for variant in ["strict_v2", "strict_v3"]
        )
        if kin_strong:
            lines.append("14. Kinematic proxy has some signal, but only targeted event-coverage use is justified unless it beats count/naive on clip recall.")
        else:
            lines.append("14. More kinematic-v0 tuning is not justified; focus on proxy anchors, temporal diversity, and predicate definition.")
        if not (0.10 <= strict_v2.get("rate", 0.0) <= 0.30 or 0.10 <= strict_v3.get("rate", 0.0) <= 0.30):
            lines.append("15. A re-prompted 32B pass is needed for a truly rare predicate; post-processing these fields does not make the workload sparse enough.")
        else:
            lines.append("15. Re-prompting 32B is still useful for validation, but strict post-processing gives a usable sparse predicate candidate.")

    if variant_info.get("label_source_mode") == "exact":
        lines.extend(["", "## Exact 102-Clip Answers", ""])
        broad = summaries.get("broad", {})
        ego = summaries.get("ego_relevant", {})
        strict = summaries.get("strict", {})
        lines.extend(
            [
                f"1. Positive rates: broad={broad.get('rate', 0.0):.3f} ({broad.get('positives', 0)}/{broad.get('valid', 0)}), "
                f"ego_relevant={ego.get('rate', 0.0):.3f} ({ego.get('positives', 0)}/{ego.get('valid', 0)}), "
                f"strict={strict.get('rate', 0.0):.3f} ({strict.get('positives', 0)}/{strict.get('valid', 0)}).",
            ]
        )
        if strict.get("valid", 0):
            if strict.get("rate", 0.0) < broad.get("rate", 0.0):
                lines.append("2. Strict label reduces the broad positive rate, so it is usable for a less saturated pseudo-GT view.")
            else:
                lines.append("2. Strict label does not reduce the broad positive rate; it does not solve saturation in this exact-label run.")
        else:
            lines.append("2. Strict label is not usable because no valid strict labels were produced.")
        for variant in ["broad", "ego_relevant", "strict"]:
            s = summaries.get(variant, {})
            lines.append(
                f"3. {variant}: positive events={s.get('events', 0)}, average positive run length={s.get('avg_run', 0.0):.3f} clips."
            )
        for variant in ["broad", "ego_relevant", "strict"]:
            clip_method, clip_val = best_low_budget_method(agg, variant, "clip", ratios)
            event_method, event_val = best_low_budget_method(agg, variant, "event", ratios)
            lines.append(f"4-5. {variant}: low-budget best clip recall is `{clip_method}` ({clip_val:.3f}); best event recall is `{event_method}` ({event_val:.3f}).")
        divergence_notes = []
        for variant in ["broad", "ego_relevant", "strict"]:
            clip_method, _ = best_low_budget_method(agg, variant, "clip", ratios)
            event_method, _ = best_low_budget_method(agg, variant, "event", ratios)
            if clip_method != event_method:
                divergence_notes.append(f"{variant}: clip `{clip_method}` vs event `{event_method}`")
        if divergence_notes:
            lines.append("6. Clip-level and event-level conclusions still diverge: " + "; ".join(divergence_notes) + ".")
        else:
            lines.append("6. Clip-level and event-level winners are aligned at low budget for the evaluated variants.")
        for variant in ["broad", "ego_relevant", "strict"]:
            ue_clip = avg_recall(agg, "uniform_expansion", ratios, variant, "clip")
            top_count_clip = avg_recall(agg, "top_count", ratios, variant, "clip")
            nms_event = max(
                avg_recall(agg, "temporal_nms_count", ratios, variant, "event"),
                avg_recall(agg, "temporal_nms_naive", ratios, variant, "event"),
                avg_recall(agg, "temporal_nms_ensemble", ratios, variant, "event"),
            )
            top_event = max(
                avg_recall(agg, "top_count", ratios, variant, "event"),
                avg_recall(agg, "top_naive", ratios, variant, "event"),
                avg_recall(agg, "ensemble_count_naive", ratios, variant, "event"),
            )
            proxy_event = mean_sweep_recall(
                sweep,
                variant,
                ["proxy_then_expansion_count", "proxy_then_expansion_naive", "proxy_then_expansion_ensemble"],
                "event_recall",
            )
            uniform_event = mean_sweep_recall(sweep, variant, ["uniform_expansion"], "event_recall")
            top_count_clip = avg_recall(agg, "top_count", ratios, variant, "clip")
            top_naive_clip = avg_recall(agg, "top_naive", ratios, variant, "clip")
            kin_clip = avg_recall(agg, "top_kinematic", ratios, variant, "clip")
            lines.append(
                f"7-11. {variant}: uniform_expansion avg clip recall={ue_clip:.3f} vs top_count={top_count_clip:.3f}; "
                f"temporal-NMS best avg event recall={nms_event:.3f} vs top/ensemble proxy best={top_event:.3f}; "
                f"proxy-anchor sweep avg event recall={proxy_event:.3f} vs uniform-anchor={uniform_event:.3f}; "
                f"top_count/top_naive avg clip recall={top_count_clip:.3f}/{top_naive_clip:.3f}; "
                f"top_kinematic avg clip recall={kin_clip:.3f}."
            )
        exact_support = any(
            best_low_budget_method(agg, variant, "clip", ratios)[0] != best_low_budget_method(agg, variant, "event", ratios)[0]
            for variant in ["broad", "ego_relevant", "strict"]
        )
        if exact_support:
            lines.append("12. Current exact-label evidence supports temporal-aware budget allocation as an allocation problem with separate dense clip recovery and event coverage objectives.")
        else:
            lines.append("12. Current exact-label evidence is weaker for temporal-aware allocation because clip and event objectives select similar policies.")
        kin_better = any(
            avg_recall(agg, "top_kinematic", ratios, variant, "clip")
            >= max(avg_recall(agg, "top_count", ratios, variant, "clip"), avg_recall(agg, "top_naive", ratios, variant, "clip"))
            for variant in ["broad", "ego_relevant", "strict"]
        )
        if kin_better:
            lines.append("13. Kinematic proxy is not uniformly weak in this exact-label run, but it should only be developed if the gain is stable across variants and budgets.")
        else:
            lines.append("13. Current evidence does not justify more kinematic-v0 tuning; count/naive proxy and temporal allocation remain higher-priority.")

    for variant in available_variants:
        for metric_level in ["clip", "event"]:
            subagg = agg[(agg["label_variant"] == variant) & (agg["metric_level"] == metric_level)]
            if subagg.empty:
                continue
            winners = best_methods_by_budget(agg, variant, metric_level)
            lines.extend(["", f"## {variant} Label: {metric_level.title()}-Level Results", ""])
            for ratio in ratios:
                if ratio not in winners:
                    continue
                best_recall, best = winners[ratio]
                lines.append(f"### Budget Ratio {ratio:.2f}")
                lines.append("")
                lines.append(f"Best {metric_level} recall: {best_recall:.3f} by {', '.join(best)}.")
                lines.append("")
                if metric_level == "clip":
                    lines.append("| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |")
                    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
                else:
                    lines.append("| method | budget | event recall | events hit | clip recall | precision |")
                    lines.append("|---|---:|---:|---:|---:|---:|")
                sub = subagg[subagg["budget_ratio"] == ratio].sort_values(["recall_mean", "precision_mean"], ascending=False)
                for _, row in sub.iterrows():
                    stochastic = row["method"] == "random"
                    if metric_level == "clip":
                        lines.append(
                            f"| {row['method']} | {int(row['budget'])} | "
                            f"{fmt_mean_std(row['recall_mean'], row['recall_std'], stochastic)} | "
                            f"{fmt_mean_std(row['precision_mean'], row['precision_std'], stochastic)} | "
                            f"{fmt_mean_std(row['f1_mean'], row['f1_std'], stochastic)} | "
                            f"{row['positives_found_mean']:.2f} | {row['event_recall']:.3f} | {row['num_events_hit']:.2f}/{int(row['num_events'])} |"
                        )
                    else:
                        clip_row = agg[
                            (agg["label_variant"] == variant)
                            & (agg["metric_level"] == "clip")
                            & (agg["method"] == row["method"])
                            & (agg["budget_ratio"] == ratio)
                        ].iloc[0]
                        lines.append(
                            f"| {row['method']} | {int(row['budget'])} | "
                            f"{fmt_mean_std(row['recall_mean'], row['recall_std'], stochastic)} | "
                            f"{row['num_events_hit']:.2f}/{int(row['num_events'])} | "
                            f"{clip_row['recall_mean']:.3f} | {clip_row['precision_mean']:.3f} |"
                        )
                lines.append("")

    broad_clip = agg[(agg["label_variant"] == "broad") & (agg["metric_level"] == "clip")]
    broad_event = agg[(agg["label_variant"] == "broad") & (agg["metric_level"] == "event")]
    lines.extend(["", "## Key Diagnostics", ""])
    if not broad_clip.empty and not broad_event.empty:
        low_ratios = [r for r in ratios if r <= 0.20]
        high_ratios = [r for r in ratios if r >= 0.30]
        low_best_clip, low_clip = compare_avg(agg, METHODS, low_ratios, "broad", "clip")
        low_best_event, low_event = compare_avg(agg, METHODS, low_ratios, "broad", "event")
        high_best_clip, high_clip = compare_avg(agg, METHODS, high_ratios, "broad", "clip")
        high_best_event, high_event = compare_avg(agg, METHODS, high_ratios, "broad", "event")
        lines.extend(
            [
                f"- Broad low-budget best clip recall: `{low_best_clip}` at {low_clip:.3f}.",
                f"- Broad low-budget best event recall: `{low_best_event}` at {low_event:.3f}.",
                f"- Broad high-budget best clip recall: `{high_best_clip}` at {high_clip:.3f}.",
                f"- Broad high-budget best event recall: `{high_best_event}` at {high_event:.3f}.",
                f"- temporal_nms_count vs top_count broad clip recall avg: {avg_recall(agg, 'temporal_nms_count', ratios, 'broad', 'clip'):.3f} vs {avg_recall(agg, 'top_count', ratios, 'broad', 'clip'):.3f}.",
                f"- temporal_nms_count vs top_count broad event recall avg: {avg_recall(agg, 'temporal_nms_count', ratios, 'broad', 'event'):.3f} vs {avg_recall(agg, 'top_count', ratios, 'broad', 'event'):.3f}.",
                f"- uniform_expansion broad clip/event recall avg: {avg_recall(agg, 'uniform_expansion', ratios, 'broad', 'clip'):.3f} / {avg_recall(agg, 'uniform_expansion', ratios, 'broad', 'event'):.3f}.",
                f"- top_kinematic broad clip/event recall avg: {avg_recall(agg, 'top_kinematic', ratios, 'broad', 'clip'):.3f} / {avg_recall(agg, 'top_kinematic', ratios, 'broad', 'event'):.3f}.",
            ]
        )
        ue_clip = avg_recall(agg, "uniform_expansion", ratios, "broad", "clip")
        ue_event = avg_recall(agg, "uniform_expansion", ratios, "broad", "event")
        if ue_clip > ue_event + 0.10:
            lines.append("- uniform_expansion has materially higher clip recall than event recall; part of its gain is likely repeated overlapping positives from the same segment.")
        else:
            lines.append("- uniform_expansion event recall tracks clip recall closely enough to suggest it is not only harvesting duplicate windows.")
    lines.extend(
        [
            "",
            "## Failure Conditions",
            "",
            "- If VLM labels are missing, this script writes `vlm_labels_template.csv` and `BLOCKED_missing_vlm_labels.md` instead of fabricating results.",
            "- If VLM-positive clips are fewer than 5, treat curves as unstable.",
            "- These results are pseudo-oracle recovery results, not validated human-GT danger detection results.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_policy_sweep_report(path: Path, sweep, cfg) -> None:
    target_ratios = [0.10, 0.20, 0.30]
    lines = [
        "# Budget Policy Sweep Report",
        "",
        "This sweep reports every available VLM pseudo-label variant in the sweep CSV.",
        "",
        "## Best Policies At Key Budgets",
        "",
        "| label variant | budget ratio | best clip recall policy | clip recall | best event recall policy | event recall |",
        "|---|---:|---|---:|---|---:|",
    ]
    for variant, variant_sweep in sweep.groupby("label_variant"):
        for ratio in target_ratios:
            sub = variant_sweep[variant_sweep["budget_ratio"].round(6) == ratio]
            if sub.empty:
                continue
            best_clip = sub.sort_values(["recall", "precision"], ascending=False).iloc[0]
            best_event = sub.sort_values(["event_recall", "recall"], ascending=False).iloc[0]
            lines.append(
                f"| {variant} | {ratio:.2f} | {best_clip['method']} {format_policy_params(best_clip)} | {best_clip['recall']:.3f} | "
                f"{best_event['method']} {format_policy_params(best_event)} | {best_event['event_recall']:.3f} |"
            )

    if {"strict_v2", "strict_v3"}.issubset(set(sweep["label_variant"].astype(str))):
        lines.extend(["", "## Strict Variant Sweep Answers", ""])
        for variant in ["strict_v2", "strict_v3"]:
            sub = sweep[sweep["label_variant"] == variant]
            low = sub[sub["budget_ratio"] <= 0.20]
            best_clip = low.groupby("method")["recall"].mean().sort_values(ascending=False)
            best_event = low.groupby("method")["event_recall"].mean().sort_values(ascending=False)
            nms_event = low[low["method"].astype(str).str.startswith("temporal_nms")]["event_recall"].mean()
            expansion = low[low["method"].astype(str).str.contains("expansion")]
            uniform_expansion = expansion[expansion["method"] == "uniform_expansion"]
            proxy_expansion = expansion[expansion["method"] != "uniform_expansion"]
            lines.append(
                f"- {variant}: low-budget best clip policy `{best_clip.index[0]}` ({best_clip.iloc[0]:.3f}); "
                f"best event policy `{best_event.index[0]}` ({best_event.iloc[0]:.3f}); "
                f"temporal-NMS mean event recall={nms_event:.3f}; "
                f"proxy expansion mean event recall={proxy_expansion['event_recall'].mean() if not proxy_expansion.empty else 0.0:.3f} vs "
                f"uniform expansion={uniform_expansion['event_recall'].mean() if not uniform_expansion.empty else 0.0:.3f}."
            )
        lines.append(
            "- Interpretation: temporal NMS/diversity should be read as event-coverage machinery, while expansion primarily spends calls around triggered positives for dense clip recovery."
        )

    if {"old_strict", "conservative"}.issubset(set(sweep["label_variant"].astype(str))):
        lines.extend(["", "## Conservative Predicate Sweep Answers", ""])
        for variant in ["old_strict", "conservative"]:
            sub = sweep[sweep["label_variant"] == variant]
            low = sub[sub["budget_ratio"] <= 0.20]
            best_clip = low.groupby("method")["recall"].mean().sort_values(ascending=False)
            best_event = low.groupby("method")["event_recall"].mean().sort_values(ascending=False)
            nms_event = low[low["method"].astype(str).str.startswith("temporal_nms")]["event_recall"].mean()
            expansion = low[low["method"].astype(str).str.contains("expansion")]
            uniform_expansion = expansion[expansion["method"] == "uniform_expansion"]
            proxy_expansion = expansion[expansion["method"] != "uniform_expansion"]
            lines.append(
                f"- {variant}: low-budget best clip policy `{best_clip.index[0]}` ({best_clip.iloc[0]:.3f}); "
                f"best event policy `{best_event.index[0]}` ({best_event.iloc[0]:.3f}); "
                f"temporal-NMS mean event recall={nms_event:.3f}; "
                f"proxy expansion mean event recall={proxy_expansion['event_recall'].mean() if not proxy_expansion.empty else 0.0:.3f} vs "
                f"uniform expansion={uniform_expansion['event_recall'].mean() if not uniform_expansion.empty else 0.0:.3f}."
            )
        lines.append(
            "- Interpretation: conservative pseudo-GT is the preferred predicate for the next budget-allocation analysis if its positive rate and examples remain acceptable."
        )

    lines.extend(["", "## Parameter Diagnostics", ""])
    expansion = sweep[sweep["method"].astype(str).str.contains("expansion")]
    if not expansion.empty:
        by_radius = expansion.groupby("expansion_radius", dropna=False)[["recall", "event_recall"]].mean().reset_index()
        lines.append("### Expansion Radius")
        lines.append("")
        lines.append("| radius | mean clip recall | mean event recall |")
        lines.append("|---:|---:|---:|")
        for _, row in by_radius.iterrows():
            lines.append(f"| {row['expansion_radius']} | {row['recall']:.3f} | {row['event_recall']:.3f} |")
        best_radius = by_radius.sort_values("event_recall", ascending=False).iloc[0]
        lines.append("")
        lines.append(f"- Best average event recall radius: {best_radius['expansion_radius']}. Larger radius is useful only if this increases monotonically.")
        by_anchor = expansion.groupby("anchor_fraction", dropna=False)[["recall", "event_recall"]].mean().reset_index()
        lines.append("")
        lines.append("### Anchor Fraction")
        lines.append("")
        lines.append("| anchor_fraction | mean clip recall | mean event recall |")
        lines.append("|---:|---:|---:|")
        for _, row in by_anchor.iterrows():
            lines.append(f"| {row['anchor_fraction']} | {row['recall']:.3f} | {row['event_recall']:.3f} |")

    nms = sweep[sweep["method"].astype(str).str.startswith("temporal_nms")]
    if not nms.empty:
        by_gap = nms.groupby("temporal_nms_gap_sec", dropna=False)[["recall", "event_recall"]].mean().reset_index()
        lines.extend(["", "### Temporal NMS Gap", "", "| gap_sec | mean clip recall | mean event recall |", "|---:|---:|---:|"])
        for _, row in by_gap.iterrows():
            lines.append(f"| {row['temporal_nms_gap_sec']} | {row['recall']:.3f} | {row['event_recall']:.3f} |")
        first = by_gap.sort_values("temporal_nms_gap_sec").iloc[0]
        last = by_gap.sort_values("temporal_nms_gap_sec").iloc[-1]
        if last["recall"] < first["recall"]:
            lines.append("- Larger temporal_nms_gap_sec hurts clip recall, consistent with suppressing adjacent positive windows.")
        else:
            lines.append("- Larger temporal_nms_gap_sec does not hurt average clip recall in this sweep.")

    uniform = expansion[expansion["method"] == "uniform_expansion"]
    proxy = expansion[expansion["method"] != "uniform_expansion"]
    if not uniform.empty and not proxy.empty:
        uniform_event = uniform["event_recall"].mean()
        proxy_event = proxy["event_recall"].mean()
        lines.extend(
            [
                "",
                "### Proxy Anchors Vs Uniform Anchors",
                "",
                f"- uniform expansion mean event recall: {uniform_event:.3f}",
                f"- proxy expansion mean event recall: {proxy_event:.3f}",
            ]
        )
        if proxy_event > uniform_event:
            lines.append("- Proxy anchors outperform uniform anchors on average.")
        else:
            lines.append("- Uniform anchors outperform or match proxy anchors on average; temporal coverage matters more than current proxy anchor quality.")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def format_policy_params(row) -> str:
    parts = []
    if str(row.get("expansion_radius", "")) not in {"", "nan"}:
        parts.append(f"r={row['expansion_radius']}")
    if str(row.get("anchor_fraction", "")) not in {"", "nan"}:
        parts.append(f"a={row['anchor_fraction']}")
    if str(row.get("temporal_nms_gap_sec", "")) not in {"", "nan"}:
        parts.append(f"gap={row['temporal_nms_gap_sec']}")
    return f"({', '.join(parts)})" if parts else ""


def write_plot(plt, agg, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    plot_agg = agg[(agg["label_variant"] == "broad") & (agg["metric_level"] == "clip")]
    for method in PLOT_METHODS:
        sub = plot_agg[plot_agg["method"] == method].sort_values("budget_ratio")
        if sub.empty:
            continue
        ax.plot(sub["budget_ratio"], sub["recall_mean"], marker="o", label=method)
        if method == "random":
            low = (sub["recall_mean"] - sub["recall_std"]).clip(lower=0.0)
            high = (sub["recall_mean"] + sub["recall_std"]).clip(upper=1.0)
            ax.fill_between(sub["budget_ratio"].to_numpy(), low.to_numpy(), high.to_numpy(), alpha=0.15)
    ax.set_xlabel("budget ratio")
    ax.set_ylabel("clip recall against broad VLM32B pseudo-GT")
    ax.set_ylim(0, 1.02)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run budget allocation simulation against VLM32B pseudo labels.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--vlm-labels", type=Path, default=None, help="Override VLM labels CSV path.")
    parser.add_argument(
        "--label-source",
        choices=["mapped", "exact", "strict_variants", "conservative"],
        default="mapped",
        help="Select mapped legacy labels, exact 102-clip labels, strict variants, or conservative 102-clip labels.",
    )
    parser.add_argument("--output-suffix", default=None, help="Suffix inserted before output file extensions, e.g. _exact_102.")
    args = parser.parse_args()

    pd, np = require_deps()
    cfg = load_config(args.config)
    validate_base_paths(cfg)
    output_dir = ensure_output_dir(cfg)
    proxy_path = output_dir / "proxy_scores.csv"
    if not proxy_path.is_file():
        fail(f"required proxy_scores.csv not found: {proxy_path}")
    proxy_df = pd.read_csv(proxy_path)

    if args.label_source == "exact" and args.vlm_labels is None:
        exact_path = (cfg.get("exact_vlm_labels") or {}).get("output_csv")
        if exact_path:
            args.vlm_labels = Path(exact_path)
        else:
            args.vlm_labels = output_dir / "vlm_labels_exact_102.csv"
    if args.label_source == "strict_variants" and args.vlm_labels is None:
        args.vlm_labels = output_dir / "vlm_labels_strict_variants_exact_102.csv"
    if args.label_source == "conservative" and args.vlm_labels is None:
        args.vlm_labels = output_dir / "vlm_labels_conservative_exact_102.csv"

    if args.vlm_labels is not None:
        if not args.vlm_labels.is_absolute():
            fail(f"--vlm-labels must be an absolute path: {args.vlm_labels}")
        if args.label_source in {"exact", "strict_variants", "conservative"} and not args.vlm_labels.is_file():
            if args.label_source == "exact":
                fail(f"exact VLM labels not found: {args.vlm_labels}. Run 06_run_exact_vlm_labels.py first.")
            if args.label_source == "strict_variants":
                fail(f"strict variant labels not found: {args.vlm_labels}. Run 07_strict_label_analysis.py first.")
            fail(f"conservative labels not found: {args.vlm_labels}. Run 08_calibrate_conservative_vlm.py --full-run first.")
        cfg.setdefault("vlm_labels", {})["path"] = str(args.vlm_labels)

    labels, adapter_info, source_df = load_or_adapt_labels(pd, cfg, output_dir, proxy_df)
    validate_labels(labels, proxy_df)
    labels = normalize_labels_for_eval(labels)
    adapter_info["label_source_mode"] = label_schema(labels)
    if adapter_info["label_source_mode"] in {"exact", "strict_variants", "conservative"}:
        adapter_info["source_path"] = str(args.vlm_labels or cfg.get("vlm_labels", {}).get("path", ""))
        adapter_info["source_rows"] = len(labels)
        source_df = None
    labels["vlm_label"] = pd.to_numeric(labels["vlm_label"], errors="coerce").fillna(-1).astype(int)
    base_df = prepare_eval_base_df(pd, np, proxy_df, labels)

    suffix = args.output_suffix
    if suffix is None:
        if args.label_source == "exact":
            suffix = "_exact_102"
        elif args.label_source == "strict_variants":
            suffix = "_strict_variants_exact_102"
        elif args.label_source == "conservative":
            suffix = "_conservative_exact_102"
        else:
            suffix = ""
    if suffix and not suffix.startswith("_"):
        suffix = "_" + suffix

    variants_path = output_dir / f"vlm_labels_variants{suffix}.csv"
    variants, variant_info = build_label_variants(pd, base_df, labels, source_df, variants_path)
    diagnostics_path = output_dir / f"vlm_label_diagnostics{suffix}.md"
    write_label_diagnostics(diagnostics_path, labels, proxy_df, source_df, adapter_info, variant_info)
    todo_path = output_dir / "TODO_exact_102_clip_vlm_labels.md"
    if args.label_source == "mapped":
        write_exact_label_todo(todo_path)

    raw, agg, selected, events_by_variant = evaluate_methods(pd, np, base_df, variants, variant_info, cfg)
    sweep = evaluate_policy_sweep(pd, np, base_df, variants, cfg, variant_info)

    curve_path = output_dir / f"budget_curve{suffix}.csv"
    raw_path = output_dir / f"budget_curve_raw{suffix}.csv"
    selected_path = output_dir / f"budget_selected_clips{suffix}.csv"
    report_path = output_dir / f"budget_report{suffix}.md"
    plot_path = output_dir / f"budget_curve{suffix}.png"
    sweep_path = output_dir / f"budget_policy_sweep{suffix}.csv"
    sweep_report_path = output_dir / f"budget_policy_sweep_report{suffix}.md"

    agg.to_csv(curve_path, index=False)
    raw.to_csv(raw_path, index=False)
    selected.to_csv(selected_path, index=False)
    sweep.to_csv(sweep_path, index=False)
    write_report(report_path, agg, base_df, variants, variant_info, cfg, events_by_variant, sweep)
    write_policy_sweep_report(sweep_report_path, sweep, cfg)
    plt = require_matplotlib()
    write_plot(plt, agg, plot_path)

    print(f"vlm_label_diagnostics={diagnostics_path}")
    print(f"vlm_labels_variants={variants_path}")
    print(f"budget_curve={curve_path}")
    print(f"budget_report={report_path}")
    print(f"budget_policy_sweep={sweep_path}")
    print(f"budget_policy_sweep_report={sweep_report_path}")
    if args.label_source == "mapped":
        print(f"TODO_exact_102_clip_vlm_labels={todo_path}")
    print(f"budget_selected_clips={selected_path}")
    print(f"budget_curve_png={plot_path}")


if __name__ == "__main__":
    main()
