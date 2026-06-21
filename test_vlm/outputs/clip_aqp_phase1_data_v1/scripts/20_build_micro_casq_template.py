#!/usr/bin/env python3
"""Create the Micro-CASQ-v0 manual annotation template."""

from phase1_data_common import DATASET_ROOT, MICRO_TEMPLATE_FIELDS, append_progress, ensure_dirs, write_csv


def main() -> int:
    ensure_dirs()
    path = DATASET_ROOT / "micro_casq_v0" / "micro_casq_events_template.csv"
    write_csv(path, [], MICRO_TEMPLATE_FIELDS)
    append_progress(
        "build_micro_casq_template",
        "python scripts/20_build_micro_casq_template.py",
        f"wrote empty template with {len(MICRO_TEMPLATE_FIELDS)} columns",
        "manual annotators can fill after source videos are selected",
    )
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

