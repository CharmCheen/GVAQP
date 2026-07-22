"""Leakage-safe D0/D1/D2/D3 policies for H-SCAN1A revision 0."""

from __future__ import annotations

import hashlib
import json
import math
import multiprocessing as mp
import os
import tempfile

from garc_eval.psvr_pilot.policy_service import (
    _coverage_grid_batch,
    _local_signal,
    _unobserved_blocks,
    coverage_state,
)
from garc_eval.psvr_runtime.sandbox import _enter_empty_unprivileged_jail, _recv_with_timeout


METHODS = frozenset({"D0", "D1", "D2", "D3"})
COMPONENTS = {
    "D1": frozenset({"duration", "level_debt", "local_proxy"}),
    "D2": frozenset({"duration", "level_debt"}),
    "D3": frozenset({"local_proxy"}),
}
FIXED_SCAN_EPOCHS = 29


def _parent_and_level(n: int, target: tuple[int, int]) -> tuple[str | None, int]:
    current, parent, level = (0, n - 1), None, 0
    while current != target:
        left, right = current; midpoint = (left + right) // 2
        children = [(left, midpoint - 1), (midpoint + 1, right)]
        child = next((item for item in children if item[0] <= item[1] and
                      item[0] <= target[0] <= target[1] <= item[1]), None)
        if child is None:
            span = target[1] - target[0] + 1
            return None, int(math.ceil(math.log2(n / span))) if span < n else 0
        parent, current, level = current, child, level + 1
    return (None if parent is None else f"{parent[0]}:{parent[1]}", level)


def eligible_cells(n: int, observed: set[int]) -> list[dict]:
    result = []
    for left, right in _unobserved_blocks(n, observed):
        unit = (left + right) // 2
        result.append({"cell_id": f"{left}:{right}", "unit_id": unit,
                       "unobserved_span_units": right - left + 1})
    return result


def priority_batch(n: int, observed: set[int], scores: dict[int, float], batch_size: int,
                   method: str) -> tuple[list[int], list[dict]]:
    if method not in COMPONENTS:
        raise ValueError("priority_batch supports D1/D2/D3")
    temporary = set(observed); chosen, details = [], []
    log_norm = math.log2(n + 1.0)
    for _ in range(batch_size):
        candidates = []
        for cell in eligible_cells(n, temporary):
            unit = cell["unit_id"]; span = cell["unobserved_span_units"]
            duration = span / n
            level_debt = math.log2(span + 1.0) / log_norm
            proxy = _local_signal(unit, scores)
            weighted_structural = duration + 0.5 * level_debt
            weighted_proxy = 0.25 * proxy
            included = COMPONENTS[method]
            total = ((duration if "duration" in included else 0.0) +
                     (0.5 * level_debt if "level_debt" in included else 0.0) +
                     (weighted_proxy if "local_proxy" in included else 0.0))
            left, right = map(int, cell["cell_id"].split(":"))
            parent, level = _parent_and_level(n, (left, right))
            candidates.append({**cell, "parent_cell_id": parent, "scan_level": level,
                               "normalized_unobserved_duration": duration,
                               "scan_level_debt": level_debt,
                               "observed_local_proxy_signal": proxy,
                               "structural_group_contribution": weighted_structural,
                               "proxy_group_contribution": weighted_proxy,
                               "full_priority": weighted_structural + weighted_proxy,
                               "priority": total})
        if not candidates:
            break
        ordered = sorted(candidates, key=lambda row: (-row["priority"], row["unit_id"]))
        selected = dict(ordered[0]); selected["selected_rank"] = 1
        selected["next_best_cell"] = None if len(ordered) < 2 else {
            "cell_id": ordered[1]["cell_id"], "unit_id": ordered[1]["unit_id"],
            "priority": ordered[1]["priority"]}
        selected["included_components"] = sorted(COMPONENTS[method])
        chosen.append(selected["unit_id"]); details.append(selected); temporary.add(selected["unit_id"])
    return chosen, details


def decide(payload: dict) -> dict:
    expected = {"method", "public_units", "proxy_rows", "queried_ids", "batch_size", "parameters"}
    if not isinstance(payload, dict) or set(payload) != expected:
        raise ValueError("H-SCAN1A payload schema mismatch")
    method = str(payload["method"])
    if method not in METHODS:
        raise ValueError("unknown H-SCAN1A method")
    ids = sorted(int(row["unit_id"]) for row in payload["public_units"])
    if ids != list(range(len(ids))):
        raise ValueError("units must be contiguous public identifiers")
    n = len(ids); batch_size = int(payload["batch_size"])
    if batch_size != 4:
        raise ValueError("batch size frozen at four")
    scores: dict[int, float] = {}
    for row in payload["proxy_rows"]:
        unit = int(row["unit_id"]); score = float(row["proxy_score"])
        if unit not in ids or not math.isfinite(score):
            raise ValueError("invalid observed proxy row")
        scores[unit] = max(score, scores.get(unit, float("-inf")))
    observed = set(scores); queried = {int(value) for value in payload["queried_ids"]}
    if not queried.issubset(observed):
        raise ValueError("queried unit was not physically scanned")
    available = sorted(observed - queried, key=lambda unit: (-scores[unit], unit))
    scans = int(dict(payload["parameters"]).get("scan_actions", 0))
    action = "scan" if scans < FIXED_SCAN_EPOCHS else ("query" if available else "stop")
    scan, priorities = [], []
    if action == "scan":
        if method == "D0":
            scan, legacy = _coverage_grid_batch(n, observed, batch_size)
            priorities = [{**row, "cell_id": f"fixed_grid:{row['unit_id']}",
                           "parent_cell_id": None, "scan_level": 0,
                           "included_components": ["fixed_coverage_order"]} for row in legacy]
        else:
            scan, priorities = priority_batch(n, observed, scores, batch_size, method)
        if not scan:
            action = "query" if available else "stop"
    response = {"action": action, "scan_unit_ids": scan,
                "candidate_unit_id": None if not available else int(available[0]),
                "scan_priorities": priorities, "coverage_state_before": coverage_state(n, observed),
                "worker_uid": os.geteuid(), "worker_root": os.getcwd(),
                "visible_proxy_units": len(observed), "visible_queried_units": len(queried),
                "allocation": "A0", "method_definition": method}
    response["decision_sha256"] = hashlib.sha256(
        json.dumps(response, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return response


def _worker(connection, jail: str) -> None:
    try:
        _enter_empty_unprivileged_jail(jail)
        connection.send(("ready", {"worker_uid": os.geteuid(), "worker_root": os.getcwd()}))
        while True:
            operation, *rest = connection.recv()
            if operation == "shutdown":
                connection.send(("ok", None)); break
            if operation != "decide":
                connection.send(("error", "operation not allowed")); continue
            try:
                connection.send(("ok", decide(rest[0])))
            except Exception as exc:
                connection.send(("error", f"{type(exc).__name__}: {exc}"))
    except Exception as exc:
        try:
            connection.send(("startup_error", f"{type(exc).__name__}: {exc}"))
        except Exception:
            pass
    finally:
        connection.close()


class HScan1APolicyService:
    def __init__(self, connection, process, jail, initialization: dict) -> None:
        self._connection, self._process, self._jail = connection, process, jail
        self.initialization = dict(initialization)

    def decide(self, payload: dict) -> dict:
        self._connection.send(("decide", payload))
        status, response = _recv_with_timeout(self._connection, 10.0, "H-SCAN1A policy decision")
        if status != "ok":
            raise RuntimeError(str(response))
        return dict(response)

    def close(self) -> None:
        try:
            if self._process.is_alive():
                self._connection.send(("shutdown",))
                status, _ = _recv_with_timeout(self._connection, 10.0, "H-SCAN1A policy shutdown")
                if status != "ok":
                    raise RuntimeError("H-SCAN1A policy rejected shutdown")
                self._process.join(timeout=10)
        finally:
            self._connection.close()
            if self._process.is_alive():
                self._process.terminate(); self._process.join(timeout=5)
            self._jail.cleanup()


def start_hscan1a_policy_service() -> HScan1APolicyService:
    context = mp.get_context("spawn"); receiver, sender = context.Pipe(duplex=True)
    jail = tempfile.TemporaryDirectory(prefix="psvr_hscan1a_jail_")
    process = context.Process(target=_worker, args=(sender, jail.name)); process.start(); sender.close()
    try:
        status, payload = _recv_with_timeout(receiver, 20.0, "H-SCAN1A startup")
        if status != "ready":
            raise RuntimeError(str(payload))
        return HScan1APolicyService(receiver, process, jail, payload)
    except Exception:
        receiver.close()
        if process.is_alive():
            process.terminate(); process.join(timeout=5)
        jail.cleanup(); raise
