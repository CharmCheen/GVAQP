import pytest

from garc_eval.safety_reference_pilot.frame_labels import annotate_frames, frame_index_records


def test_frame_index_records_preserve_exact_timestamp_mapping():
    records = frame_index_records([10.0, 10.49, 11.01])
    assert [row["visible_frame_label"] for row in records] == ["F000", "F001", "F002"]
    assert records[2]["source_timestamp_sec"] == 11.01


def test_frame_index_records_require_monotonic_timestamps():
    with pytest.raises(ValueError):
        frame_index_records([1.0, 1.0])


def test_annotation_changes_copies_not_source_images():
    Image = pytest.importorskip("PIL.Image")
    originals = [Image.new("RGB", (160, 60), color=(128, 128, 128)) for _ in range(2)]
    before = originals[0].tobytes()
    annotated = annotate_frames(originals, [5.0, 5.5])
    assert originals[0].tobytes() == before
    assert annotated[0].tobytes() != before

