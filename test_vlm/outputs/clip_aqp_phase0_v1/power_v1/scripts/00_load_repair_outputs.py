#!/usr/bin/env python3
from __future__ import annotations

import pandas as pd

from power_common import EPSILON, POWER_DIR, REPAIR_REPORT, ROOT_CAUSE, ROWS_CSV, RESULTS_CSV, append_progress, ensure_dirs, load_repair_tables


def main() -> None:
    ensure_dirs()
    rows, results = load_repair_tables()
    required = {
        "block_id",
        "video_id",
        "start_time",
        "end_time",
        "Y_i_O",
        "M_i_O",
        "inclusion_probability",
        "sample_split",
        "used_for_design",
        "used_for_repair",
        "padding_width_used",
    }
    missing = sorted(required - set(rows.columns))
    invariant_ok = bool(
        (results["UCB_M_O"] >= results["M_hat_O"] - EPSILON).all()
        and (results["LCB_Y_O"] <= results["Y_hat_O"] + EPSILON).all()
        and (rows["sample_split"].astype(str).eq("certification")).all()
        and (~rows["used_for_design"].astype(bool)).all()
        and (~rows["used_for_repair"].astype(bool)).all()
    )
    manifest = pd.DataFrame(
        [
            {"input_path": str(ROWS_CSV), "exists": ROWS_CSV.exists(), "rows": len(rows), "columns": ";".join(rows.columns)},
            {"input_path": str(RESULTS_CSV), "exists": RESULTS_CSV.exists(), "rows": len(results), "columns": ";".join(results.columns)},
            {"input_path": str(REPAIR_REPORT), "exists": REPAIR_REPORT.exists(), "rows": "", "columns": ""},
            {"input_path": str(ROOT_CAUSE), "exists": ROOT_CAUSE.exists(), "rows": "", "columns": ""},
        ]
    )
    manifest.to_csv(POWER_DIR / "data_manifest/repair_inputs.csv", index=False)
    validation = pd.DataFrame(
        [
            {
                "missing_required_block_columns": ";".join(missing),
                "UCB_M_ge_M_hat": bool((results["UCB_M_O"] >= results["M_hat_O"] - EPSILON).all()),
                "LCB_Y_le_Y_hat": bool((results["LCB_Y_O"] <= results["Y_hat_O"] + EPSILON).all()),
                "all_rows_certification": bool((rows["sample_split"].astype(str).eq("certification")).all()),
                "no_used_for_design": bool((~rows["used_for_design"].astype(bool)).all()),
                "no_used_for_repair": bool((~rows["used_for_repair"].astype(bool)).all()),
                "validation_passed": invariant_ok and not missing,
            }
        ]
    )
    validation.to_csv(POWER_DIR / "tables/input_validation.csv", index=False)
    if missing or not invariant_ok:
        raise SystemExit("repair input validation failed")
    append_progress(
        "load repair outputs",
        "python scripts/00_load_repair_outputs.py",
        f"validated {len(rows)} block rows and {len(results)} result rows",
        next_action="fit empirical block model",
    )


if __name__ == "__main__":
    main()
