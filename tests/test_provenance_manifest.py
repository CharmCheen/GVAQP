import csv
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMMIT = "5047241b0561b911b9a519b18e8e7591c0074e70"


def test_migration_and_omission_manifests_have_required_fields():
    migration = list(csv.DictReader((ROOT / "provenance/migration_manifest.csv").open(encoding="utf-8")))
    omitted = list(csv.DictReader((ROOT / "provenance/omitted_legacy_manifest.csv").open(encoding="utf-8")))
    assert migration and omitted
    assert set(migration[0]) == {"source_path", "source_commit", "target_path", "classification", "reason", "content_sha256", "semantic_change", "tests_covering"}
    assert set(omitted[0]) == {"source_path_or_prefix", "classification", "omission_reason", "replacement_path", "source_commit", "scientific_result_preserved_in"}
    assert all(row["source_commit"] == COMMIT and len(row["content_sha256"]) == 64 for row in migration)
    assert all(row["source_commit"] == COMMIT for row in omitted)
    for row in migration:
        assert hashlib.sha256((ROOT / row["target_path"]).read_bytes()).hexdigest() == row["content_sha256"]
