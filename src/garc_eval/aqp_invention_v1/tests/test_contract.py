from __future__ import annotations

import json
import unittest

from garc_eval.aqp_invention_v1.contract import (
    ContractError,
    build_windows,
    owner_accepts,
    parse_event_enumeration,
    reconcile_owned_fragments,
    sample_frame_indices,
)


class ContractTests(unittest.TestCase):
    def test_timeline_cover(self):
        windows = build_windows(3462.930499)
        self.assertEqual(len(windows), 70)
        self.assertEqual(windows[0].input_start, 0.0)
        self.assertAlmostEqual(windows[-1].core_end, 3462.930499)
        self.assertTrue(all(a.core_end == b.core_start for a, b in zip(windows, windows[1:])))

    def test_sampler_is_inclusive_fixed_stride(self):
        self.assertEqual(sample_frame_indices(0, 10, 30.000005, 1000), list(range(0, 301, 15)))

    def test_strict_enumeration_parser(self):
        payload = {
            "clip_status": "ok",
            "events": [{
                "event_start": 1.0, "event_end": 2.0,
                "event_type": "enter_ego_path", "involved_object": "vehicle",
                "object_identity": "white car from left", "ego_relevant": True,
                "boundary_status": "ok", "complete_event_visible": True,
                "confidence": "high", "evidence": "crosses lane",
            }],
            "abstain_reason": None,
        }
        parsed = parse_event_enumeration(json.dumps(payload), 10.0)
        self.assertEqual(len(parsed["events"]), 1)
        payload["events"][0]["event_end"] = 11
        with self.assertRaises(ContractError):
            parse_event_enumeration(json.dumps(payload), 10.0)

    def test_midpoint_single_owner(self):
        self.assertTrue(owner_accepts(45.0, 55.0, 50.0, 100.0, 150.0))
        self.assertFalse(owner_accepts(45.0, 54.0, 50.0, 100.0, 150.0))

    def test_reconciler_does_not_hide_oversplit(self):
        base = {
            "start_time": 10.0, "end_time": 20.0, "involved_object": "vehicle",
            "object_identity": "blue car", "source_window_id": "w1",
        }
        exact = {**base, "source_window_id": "w2"}
        overlap = {**base, "start_time": 15.0, "end_time": 25.0, "source_window_id": "w2"}
        out = reconcile_owned_fragments([base, exact, overlap])
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["source_window_id"], "w1")


if __name__ == "__main__":
    unittest.main()
