from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_selected_configs_are_frozen():
    scan = yaml.safe_load((ROOT / "configs/safe_coverage.yaml").read_text())
    controller = yaml.safe_load((ROOT / "configs/fixed_ratio_25_75.yaml").read_text())
    assert scan["policy_id"] == "ANYTIME_LARGEST_GAP" and scan["yolo_guidance_enabled"] is False
    assert controller["controller_id"] == "R4_FIXED_TIME_RATIO_25_75"
    assert (controller["scan_time_target_fraction"], controller["confirm_time_target_fraction"]) == (.25, .75)
