import os

from garc_eval.accelerated_event_query.k3_unit_event_adapter import K3UnitEventAdapter
from garc_eval.accelerated_event_query.oracle_v3_full_grid_analyzer import (
    FullGridAnalysisProducts,
)
from garc_eval.accelerated_event_query.oracle_v3_full_grid_finalizer import _publish
from garc_eval.accelerated_event_query.oracle_v3_manifest import load_json

from .v3_helpers import unit


def test_reference_becomes_formal_only_after_atomic_release_pointer(tmp_path):
    rows = [unit(0, "relevant"), unit(1, "not_relevant")]
    relation = K3UnitEventAdapter("Q_DRIVER_RESPONSE_V1").materialize(rows)
    products = FullGridAnalysisProducts(
        unit_rows=tuple({
            "ordinal": index,
            "unit_id": row.unit_id,
            "video_id": row.video_id,
            "start_time": row.start_time,
            "end_time": row.end_time,
            "unit_kind": "normal",
            "parse_status": "ok",
            "authoritative_label": row.outcome,
            "diagnostic_confidence": "low",
            "diagnostic_evidence": "test",
            "source_raw_sha256": str(index) * 64,
            "record_payload_sha256": str(index + 1) * 64,
        } for index, row in enumerate(rows)),
        primary_relation=relation,
        lower_bound_relation=relation,
        upper_bound_relation=relation,
    )
    metrics = {
        "execution_seal_sha256": "a" * 64,
        "metrics_payload_sha256": "b" * 64,
        "oracle_coverage": 1.0,
        "per_video_oracle_coverage": {"V0": 1.0},
        "label_counts": {"relevant": 1, "not_relevant": 1},
        "parse_status_counts": {"ok": 2},
        "coverage_thresholds": {
            "minimum_global_determined_fraction": 0.99,
            "minimum_per_video_determined_fraction": 0.99,
        },
    }
    release = _publish(execution_root=tmp_path, metrics=metrics, products=products)
    pointer = tmp_path / "FORMAL_REFERENCE_RELEASE.json"
    assert pointer.is_file()
    assert load_json(pointer)["release_id"] == release["release_id"]
    assert {row["path"].split("/")[-1] for row in release["artifacts"]} == {
        "unit_labels.parquet",
        "oracle_coverage_report.json",
        "k3_model_relative_event_relation.parquet",
    }
    for row in release["artifacts"]:
        assert oct(os.stat(tmp_path / row["path"]).st_mode & 0o777) == "0o600"
