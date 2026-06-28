#!/usr/bin/env python3
from __future__ import annotations

import pandas as pd

from candidate_common import CERT_COLUMNS, OUT, append_progress, empty_csv


def main() -> int:
    eval_path = OUT / "tables/candidate_eval_results.csv"
    eval_df = pd.read_csv(eval_path) if eval_path.exists() else pd.DataFrame()
    if eval_df.empty:
        empty_csv(OUT / "tables/candidate_certificate_results.csv", CERT_COLUMNS)
        pd.DataFrame(
            [
                {"constraint": "sample_split == certification", "passed": "not_applicable_no_candidates"},
                {"constraint": "used_for_design == false", "passed": "not_applicable_no_candidates"},
                {"constraint": "used_for_repair == false", "passed": "not_applicable_no_candidates"},
                {"constraint": "UCB_M_O >= M_hat_O - 1e-9", "passed": "not_applicable_no_candidates"},
                {"constraint": "LCB_Y_O <= Y_hat_O + 1e-9", "passed": "not_applicable_no_candidates"},
            ]
        ).to_csv(OUT / "tables/candidate_certificate_validity_constraints.csv", index=False)
        append_progress("certify_candidates", "python scripts/40_certify_candidate_sets.py", "skipped_no_promising_candidates", failure="no candidate evaluation rows", next_action="report")
        print("Certification skipped: no promising candidates")
        return 0
    promising = eval_df[eval_df["true_derived_recall"] >= 0.5]
    if promising.empty:
        empty_csv(OUT / "tables/candidate_certificate_results.csv", CERT_COLUMNS)
    append_progress("certify_candidates", "python scripts/40_certify_candidate_sets.py", f"promising_configs={len(promising)}", next_action="report")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

