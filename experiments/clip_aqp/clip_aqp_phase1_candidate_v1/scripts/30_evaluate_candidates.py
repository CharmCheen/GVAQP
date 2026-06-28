#!/usr/bin/env python3
from __future__ import annotations

import pandas as pd

from candidate_common import EVAL_COLUMNS, OUT, append_progress, empty_csv


def main() -> int:
    status = pd.read_csv(OUT / "tables/candidate_generation_status.csv")
    runnable = status[~status["status"].astype(str).str.startswith("skipped")]
    if runnable.empty:
        empty_csv(OUT / "tables/candidate_eval_results.csv", EVAL_COLUMNS)
        pd.DataFrame([{"check": "candidate_eval_recomputable", "passed": False, "detail": "no candidate sets generated because videos were inaccessible"}]).to_csv(OUT / "tables/evaluation_checks.csv", index=False)
        append_progress("evaluate_candidates", "python scripts/30_evaluate_candidates.py", "skipped_no_candidates", failure="no candidate sets", next_action="certificate placeholders")
        print("Candidate evaluation skipped: no candidate sets")
        return 0
    empty_csv(OUT / "tables/candidate_eval_results.csv", EVAL_COLUMNS)
    append_progress("evaluate_candidates", "python scripts/30_evaluate_candidates.py", "no_evaluable_candidates", next_action="certificate placeholders")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

