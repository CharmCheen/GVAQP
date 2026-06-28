#!/usr/bin/env python3
"""Validate CASQ schema files and local Phase 1 template headers."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from phase1_data_common import (
    EVENT_FIELDS,
    MICRO_TEMPLATE_FIELDS,
    OUT,
    UNIT_FIELDS,
    append_progress,
    ensure_dirs,
    write_csv,
)


def load_schema(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def required_fields(schema: dict) -> list[str]:
    return list(schema.get("required", []))


def csv_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        return next(reader)


def main() -> int:
    ensure_dirs()
    rows = []
    event_schema_path = OUT / "schema" / "casq_events_schema.json"
    unit_schema_path = OUT / "schema" / "casq_units_schema.json"

    for label, path, expected in [
        ("events_schema", event_schema_path, EVENT_FIELDS),
        ("units_schema", unit_schema_path, UNIT_FIELDS),
    ]:
        if not path.exists():
            rows.append({"check": label, "passed": False, "detail": f"missing {path}"})
            continue
        schema = load_schema(path)
        missing = sorted(set(expected) - set(required_fields(schema)))
        rows.append(
            {
                "check": label,
                "passed": not missing,
                "detail": "all required fields present" if not missing else "missing required: " + ",".join(missing),
            }
        )

    template_path = OUT.parent.parent.parent / "datasets" / "casq_external" / "micro_casq_v0" / "micro_casq_events_template.csv"
    if template_path.exists():
        header = csv_header(template_path)
        missing = sorted(set(MICRO_TEMPLATE_FIELDS) - set(header))
        extra = [c for c in header if c not in MICRO_TEMPLATE_FIELDS]
        rows.append(
            {
                "check": "micro_casq_template_header",
                "passed": not missing and not extra,
                "detail": "header matches required template"
                if not missing and not extra
                else f"missing={missing}; extra={extra}",
            }
        )
    else:
        rows.append({"check": "micro_casq_template_header", "passed": False, "detail": f"missing {template_path}"})

    write_csv(OUT / "tables" / "schema_validation_summary.csv", rows, ["check", "passed", "detail"])
    report = ["# CASQ Phase 1 Schema Validation", ""]
    for row in rows:
        report.append(f"- {row['check']}: passed={row['passed']} - {row['detail']}")
    report.append("")
    report.append("This check validates field contracts only. It does not prove that any external dataset contains clean event boundaries.")
    (OUT / "reports" / "SCHEMA_VALIDATION.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    all_passed = all(str(row["passed"]) == "True" or row["passed"] is True for row in rows)
    append_progress(
        "validate_casq_schema",
        "python scripts/01_validate_casq_schema.py",
        f"schema validation passed={all_passed}",
        "run converter scaffolds",
        failure="" if all_passed else "one or more schema checks failed",
    )
    print(f"Schema validation passed={all_passed}")
    return 0 if all_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())

