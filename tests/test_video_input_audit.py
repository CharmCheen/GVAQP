import json

from garc.audit.video_eligibility import pairwise_overlap, register_candidates


def test_registration_is_immutable_by_byte_identity(tmp_path):
    inbox, ledger = tmp_path / "inbox", tmp_path / "ledger.jsonl"
    inbox.mkdir()
    video = inbox / "a.mp4"
    video.write_bytes(b"one")
    first = register_candidates(inbox, ledger)
    second = register_candidates(inbox, ledger)
    video.write_bytes(b"two")
    third = register_candidates(inbox, ledger)
    assert len(first) == len(second) == 1 and len(third) == 2
    assert all(row["semantic_information_opened"] is False for row in third)


def test_pairwise_exact_duplicate_and_capture_session_detection():
    base = {"sha256": "a" * 64, "source": {"capture_session_id": "same"}, "signatures": []}
    result = pairwise_overlap({"path": "a", **base}, {"path": "b", **base})
    assert not result["pass"]
    assert set(result["failure_reasons"]) == {"EXACT_FILE_DUPLICATE", "SHARED_CAPTURE_SESSION_ID"}
