from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
V1_BENCH = ROOT / "benchmarks/partial_scan_pilot_v1"
V1_IMMUTABLE = V1_BENCH / "immutable"
V1_DERIVED = V1_BENCH / "derived"
V1_OUTPUT = ROOT / "outputs/partial_scan_pilot_v1"

V2_BENCH = ROOT / "benchmarks/partial_scan_pilot_v2"
V2_IMMUTABLE = V2_BENCH / "immutable"
V2_DERIVED = V2_BENCH / "derived"
V2_OUTPUT = ROOT / "outputs/partial_scan_pilot_v2"

V2_AUDITS = V2_DERIVED / "audits"
V2_ISOLATION = V2_DERIVED / "isolation"
V2_REPLAY = V2_DERIVED / "policy_runs/replay"
V2_PHYSICAL = V2_DERIVED / "policy_runs/physical"
V2_COST = V2_DERIVED / "cost_calibration"

POLICY_UID = 61042
POLICY_GID = 61042
POLICY_ROOTFS = Path("/dev/shm/partial_scan_policy_v2_rootfs")
POLICY_IDS = (
    "SEQUENTIAL",
    "RANDOM_WITHOUT_REPLACEMENT",
    "UNIFORM_PREFIX",
    "ANYTIME_LARGEST_GAP",
)
LATIN_SQUARE = (
    POLICY_IDS,
    POLICY_IDS[1:] + POLICY_IDS[:1],
    POLICY_IDS[2:] + POLICY_IDS[:2],
    POLICY_IDS[3:] + POLICY_IDS[:3],
)
SEED = 20260724
PHYSICAL_BUDGET_SEC = 60.0
REPLAY_BUDGET_SEC = 60.0
INITIAL_SCAN_COST_SEC = 5.0
INITIAL_E2E_OVERHEAD_SEC = 0.25
