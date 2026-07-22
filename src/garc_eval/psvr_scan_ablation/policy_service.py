"""Sandboxed S2/S3/S4 scan component policies for H-SCAN-COMP1."""

from __future__ import annotations

import hashlib
import json
import math
import multiprocessing as mp
import os
import tempfile

from garc_eval.psvr_pilot.policy_service import _local_signal, _unobserved_blocks, coverage_state
from garc_eval.psvr_runtime.sandbox import _enter_empty_unprivileged_jail, _recv_with_timeout


METHODS = frozenset({"S2", "S3", "S4"})
INCLUDED = {
    "S2": frozenset({"duration", "proxy"}),
    "S3": frozenset({"duration", "debt"}),
    "S4": frozenset({"debt", "proxy"}),
}
FIXED_SCAN_EPOCHS = 29


def _canonical_cell(n: int, target: tuple[int, int]) -> tuple[str | None, int]:
    """Return canonical binary-tree parent and depth for a midpoint-split cell."""
    current = (0, n - 1); parent = None; level = 0
    while current != target:
        left, right = current; midpoint = (left + right) // 2
        children = []
        if left <= midpoint - 1:
            children.append((left, midpoint - 1))
        if midpoint + 1 <= right:
            children.append((midpoint + 1, right))
        match = next((child for child in children if child[0] <= target[0] and target[1] <= child[1]), None)
        if match is None:
            raise ValueError(f"non-canonical cell {target}")
        parent = current; current = match; level += 1
    return (None if parent is None else f"{parent[0]}:{parent[1]}", level)


def component_batch(n: int, observed: set[int], scores: dict[int, float], batch_size: int,
                    method: str) -> tuple[list[int], list[dict]]:
    if method not in METHODS:
        raise ValueError("unknown component method")
    temporary = set(observed); chosen, details = [], []
    norm = math.log2(n + 1.0)
    for _ in range(batch_size):
        candidates = []
        for left, right in _unobserved_blocks(n, temporary):
            span = right - left + 1; unit = (left + right) // 2
            duration = span / n
            debt = 0.5 * math.log2(span + 1.0) / norm
            proxy = 0.25 * _local_signal(unit, scores)
            terms = {"duration": duration, "debt": debt, "proxy": proxy}
            total = sum(value for name, value in terms.items() if name in INCLUDED[method])
            parent, level = _canonical_cell(n, (left, right))
            candidates.append({
                "unit_id": unit, "cell_id": f"{left}:{right}", "parent_cell_id": parent,
                "scan_level": level, "unobserved_span_units": span,
                "unobserved_duration_component": duration, "debt_component": debt,
                "proxy_component": proxy, "total_priority": total,
            })
        if not candidates:
            break
        ordered = sorted(candidates, key=lambda row: (-row["total_priority"], row["unit_id"]))
        selected = dict(ordered[0]); selected["selected_rank"] = 1
        selected["next_best_cell"] = None if len(ordered) == 1 else {
            "cell_id": ordered[1]["cell_id"], "unit_id": ordered[1]["unit_id"],
            "total_priority": ordered[1]["total_priority"],
        }
        selected["included_components"] = sorted(INCLUDED[method])
        chosen.append(selected["unit_id"]); details.append(selected); temporary.add(selected["unit_id"])
    return chosen, details


def decide(payload: dict) -> dict:
    expected = {"method", "public_units", "proxy_rows", "queried_ids", "batch_size", "parameters"}
    if not isinstance(payload, dict) or set(payload) != expected:
        raise ValueError("scan ablation payload schema mismatch")
    method = str(payload["method"])
    if method not in METHODS:
        raise ValueError("unknown scan ablation method")
    ids = sorted(int(row["unit_id"]) for row in payload["public_units"])
    if ids != list(range(len(ids))):
        raise ValueError("units must be contiguous public identifiers")
    n = len(ids); batch_size = int(payload["batch_size"])
    if batch_size != 4:
        raise ValueError("batch size is frozen at four")
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
        scan, priorities = component_batch(n, observed, scores, batch_size, method)
        if not scan:
            action = "query" if available else "stop"
    response = {
        "action": action, "scan_unit_ids": scan,
        "candidate_unit_id": None if not available else int(available[0]),
        "scan_priorities": priorities, "coverage_state_before": coverage_state(n, observed),
        "worker_uid": os.geteuid(), "worker_root": os.getcwd(),
        "visible_proxy_units": len(observed), "visible_queried_units": len(queried),
        "allocation": "A0", "component_variant": method,
    }
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


class ScanAblationPolicyService:
    def __init__(self, connection, process, jail, initialization: dict) -> None:
        self._connection, self._process, self._jail = connection, process, jail
        self.initialization = dict(initialization)

    def decide(self, payload: dict) -> dict:
        self._connection.send(("decide", payload))
        status, response = _recv_with_timeout(self._connection, 10.0, "scan ablation decision")
        if status != "ok":
            raise RuntimeError(str(response))
        return dict(response)

    def close(self) -> None:
        try:
            if self._process.is_alive():
                self._connection.send(("shutdown",))
                status, _ = _recv_with_timeout(self._connection, 10.0, "scan ablation shutdown")
                if status != "ok":
                    raise RuntimeError("scan ablation policy rejected shutdown")
                self._process.join(timeout=10)
        finally:
            self._connection.close()
            if self._process.is_alive():
                self._process.terminate(); self._process.join(timeout=5)
            self._jail.cleanup()


def start_scan_ablation_policy_service() -> ScanAblationPolicyService:
    context = mp.get_context("spawn"); receiver, sender = context.Pipe(duplex=True)
    jail = tempfile.TemporaryDirectory(prefix="psvr_scan_ablation_jail_")
    process = context.Process(target=_worker, args=(sender, jail.name)); process.start(); sender.close()
    try:
        status, payload = _recv_with_timeout(receiver, 20.0, "scan ablation startup")
        if status != "ready":
            raise RuntimeError(str(payload))
        return ScanAblationPolicyService(receiver, process, jail, payload)
    except Exception:
        receiver.close()
        if process.is_alive():
            process.terminate(); process.join(timeout=5)
        jail.cleanup(); raise
