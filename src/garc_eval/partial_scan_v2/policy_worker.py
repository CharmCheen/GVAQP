#!/usr/bin/python3
"""Self-contained policy worker copied into the isolated policy root.

This file intentionally imports no evaluator or benchmark module.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import sys
import traceback


PROTOCOL = "partial-scan-policy-jsonl-v2"
MAX_MESSAGE_BYTES = 2 * 1024 * 1024
RUN_RE = re.compile(r"^r_[0-9a-f]{32}$")
UNIT_RE = re.compile(r"^u_[0-9a-f]{20}$")
POLICIES = {
    "SEQUENTIAL",
    "RANDOM_WITHOUT_REPLACEMENT",
    "UNIFORM_PREFIX",
    "ANYTIME_LARGEST_GAP",
}


def exact_keys(value: dict, expected: set[str]) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("PROTOCOL_FIELD_SET")


def read_message() -> dict | None:
    line = sys.stdin.buffer.readline(MAX_MESSAGE_BYTES + 2)
    if not line:
        return None
    if len(line) > MAX_MESSAGE_BYTES or not line.endswith(b"\n"):
        raise ValueError("PROTOCOL_MESSAGE_SIZE")
    value = json.loads(line)
    if not isinstance(value, dict):
        raise ValueError("PROTOCOL_OBJECT_REQUIRED")
    return value


def send_message(value: dict) -> None:
    encoded = (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("ascii")
    if len(encoded) > MAX_MESSAGE_BYTES:
        raise ValueError("PROTOCOL_MESSAGE_SIZE")
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


def validate_initialize(message: dict) -> tuple[str, list[dict]]:
    exact_keys(
        message,
        {
            "type",
            "protocol_version",
            "run_id",
            "video",
            "units",
            "budget_sec",
            "public_contract_hash",
        },
    )
    if (
        message["type"] != "initialize"
        or message["protocol_version"] != PROTOCOL
        or not RUN_RE.fullmatch(str(message["run_id"]))
    ):
        raise ValueError("PROTOCOL_INITIALIZE")
    exact_keys(message["video"], {"video_id", "duration_sec"})
    units = message["units"]
    if not isinstance(units, list) or not units:
        raise ValueError("PROTOCOL_UNITS")
    seen = set()
    for unit in units:
        exact_keys(unit, {"unit_id", "start_sec", "end_sec"})
        if (
            not UNIT_RE.fullmatch(str(unit["unit_id"]))
            or unit["unit_id"] in seen
            or float(unit["end_sec"]) <= float(unit["start_sec"])
        ):
            raise ValueError("PROTOCOL_UNIT")
        seen.add(unit["unit_id"])
    return str(message["run_id"]), units


def validate_choose(message: dict, known: set[str]) -> tuple[int, dict]:
    exact_keys(message, {"type", "step_id", "state"})
    if message["type"] != "choose_action":
        raise ValueError("PROTOCOL_CHOOSE")
    step = message["step_id"]
    state = message["state"]
    exact_keys(
        state,
        {
            "step_id",
            "public_protocol_version",
            "scanned_unit_ids",
            "current_unit_id",
            "remaining_budget_sec",
            "past_action_costs_sec",
            "geometric_coverage",
            "revealed_observations",
        },
    )
    if not isinstance(step, int) or step < 0 or state["step_id"] != step:
        raise ValueError("PROTOCOL_STEP")
    if state["public_protocol_version"] != PROTOCOL:
        raise ValueError("PROTOCOL_VERSION")
    scanned = state["scanned_unit_ids"]
    if (
        not isinstance(scanned, list)
        or len(scanned) != len(set(scanned))
        or not set(scanned).issubset(known)
    ):
        raise ValueError("PROTOCOL_SCANNED")
    exact_keys(state["geometric_coverage"], {"fraction", "covered_duration_sec"})
    exact_keys(
        state["revealed_observations"],
        {"candidate_ids", "last_completed_unit_id", "result_class"},
    )
    return step, state


class Policy:
    def __init__(self, policy_id: str, seed: int, units: list[dict]):
        if policy_id not in POLICIES:
            raise ValueError("UNKNOWN_POLICY")
        self.policy_id = policy_id
        self.units = list(units)
        self.rng = random.Random(seed)

    def choose(self, state: dict) -> str:
        scanned = set(state["scanned_unit_ids"])
        remaining = [unit for unit in self.units if unit["unit_id"] not in scanned]
        if not remaining:
            raise ValueError("NO_ACTION")
        if self.policy_id == "SEQUENTIAL":
            return remaining[0]["unit_id"]
        if self.policy_id == "RANDOM_WITHOUT_REPLACEMENT":
            return remaining[self.rng.randrange(len(remaining))]["unit_id"]
        if self.policy_id == "UNIFORM_PREFIX":
            count = len(self.units)
            for levels in range(int(math.ceil(math.log2(max(2, count)))) + 1):
                stride = max(1, count // (2**levels))
                for index in range(0, count, stride):
                    candidate = self.units[index]["unit_id"]
                    if candidate not in scanned:
                        return candidate
            return remaining[0]["unit_id"]
        if not scanned:
            return remaining[len(remaining) // 2]["unit_id"]
        index_by_id = {
            unit["unit_id"]: index for index, unit in enumerate(self.units)
        }
        observed = [index_by_id[value] for value in scanned]
        return max(
            remaining,
            key=lambda unit: (
                min(
                    abs(index_by_id[unit["unit_id"]] - index)
                    for index in observed
                ),
                -index_by_id[unit["unit_id"]],
            ),
        )["unit_id"]


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--policy-id", required=True)
    parser.add_argument("--seed", required=True, type=int)
    args = parser.parse_args()
    try:
        initialize = read_message()
        if initialize is None:
            return 2
        run_id, units = validate_initialize(initialize)
        known = {unit["unit_id"] for unit in units}
        policy = Policy(args.policy_id, args.seed, units)
        send_message(
            {
                "type": "initialized",
                "run_id": run_id,
                "protocol_version": PROTOCOL,
            }
        )
        while True:
            message = read_message()
            if message is None:
                return 0
            if message.get("type") == "terminate":
                exact_keys(message, {"type", "reason"})
                return 0
            step, state = validate_choose(message, known)
            selected = policy.choose(state)
            send_message({"step_id": step, "unit_id": selected})
    except BaseException:
        traceback.print_exc(file=sys.stderr)
        try:
            send_message(
                {"type": "policy_error", "code": "POLICY_PROTOCOL_ERROR"}
            )
        except BaseException:
            pass
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
