import json

import pytest

from garc_eval.partial_scan_v2.run_recovery import (
    INCOMPLETE_RUN_MARKER,
    finalize_destination,
    prepare_destination,
)


def test_new_destination(tmp_path):
    root, destination = tmp_path / "runs", tmp_path / "runs" / "new"
    prepare_destination(destination, root, tmp_path / "repair.json")
    assert (destination / INCOMPLETE_RUN_MARKER).is_file()


def test_valid_incomplete_destination_is_repaired(tmp_path):
    root, destination = tmp_path / "runs", tmp_path / "runs" / "partial"
    destination.mkdir(parents=True)
    (destination / INCOMPLETE_RUN_MARKER).write_text("incomplete\n")
    (destination / "partial.txt").write_text("old")
    log = tmp_path / "repair.json"
    prepare_destination(destination, root, log)
    assert not (destination / "partial.txt").exists()
    assert json.loads(log.read_text())[0]["action"] == "REMOVED_VALID_INCOMPLETE_DESTINATION"


def test_completed_destination_is_not_overwritten(tmp_path):
    root, destination = tmp_path / "runs", tmp_path / "runs" / "done"
    destination.mkdir(parents=True)
    (destination / "run_summary.json").write_text("{}")
    with pytest.raises(FileExistsError):
        prepare_destination(destination, root, tmp_path / "repair.json")


@pytest.mark.parametrize("destination_factory", [lambda root: root.parent / "outside", lambda root: root])
def test_outside_or_root_destination_is_rejected(tmp_path, destination_factory):
    root = tmp_path / "runs"
    with pytest.raises(ValueError):
        prepare_destination(destination_factory(root), root, tmp_path / "repair.json")


def test_directory_without_marker_is_not_removed(tmp_path):
    root, destination = tmp_path / "runs", tmp_path / "runs" / "unknown"
    destination.mkdir(parents=True)
    with pytest.raises(FileExistsError):
        prepare_destination(destination, root, tmp_path / "repair.json")


def test_finalization_removes_marker_before_atomic_summary(tmp_path):
    root, destination = tmp_path / "runs", tmp_path / "runs" / "new"
    prepare_destination(destination, root, tmp_path / "repair.json")
    finalize_destination(destination, {"status": "done"})
    assert not (destination / INCOMPLETE_RUN_MARKER).exists()
    assert json.loads((destination / "run_summary.json").read_text())["status"] == "done"
