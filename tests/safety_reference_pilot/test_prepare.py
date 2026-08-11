from garc_eval.safety_reference_pilot.prepare import deterministic_selection, verify_v1


def candidate(video_id, window_id):
    return {
        "video_id": video_id,
        "video_path": f"/{video_id}.mp4",
        "start_sec": 0.0,
        "end_sec": 30.0,
        "source_window_id": window_id,
        "expected_sample_fps": 2.0,
        "selection_reason": "test",
    }


def test_v1_hashes_remain_frozen():
    observed = verify_v1()
    assert observed["immutable/reference_events.csv"].startswith("ca25d347")


def test_selection_is_deterministic_and_unique():
    names = [
        "legacy_cut_in_positive",
        "legacy_cut_in_hard_negative",
        "legacy_boundary_disagreement",
        "normal_traffic_control",
    ]
    pools = {
        name: [candidate(f"V{i % 2}", f"{name}_{i:03d}") for i in range(20)]
        for name in names
    }
    first = deterministic_selection(pools)
    second = deterministic_selection(pools)
    assert first == second
    assert len(first) == 30
    assert len({row["source_window_id"] for row in first}) == 30

