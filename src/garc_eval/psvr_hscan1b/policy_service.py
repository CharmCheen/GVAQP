"""Leakage-safe H-SCAN1B exact-tie and structural-factorial policies."""

from __future__ import annotations

import hashlib
import json
import math
import multiprocessing as mp
import os
import tempfile

from garc_eval.psvr_hscan1a.policy_service import _parent_and_level, eligible_cells
from garc_eval.psvr_pilot.policy_service import _local_signal, coverage_state
from garc_eval.psvr_runtime.sandbox import _enter_empty_unprivileged_jail, _recv_with_timeout


METHODS = frozenset({"TB0", "TB1", "TB2", "F00", "F10", "F01", "F11"})
FIXED_SCAN_EPOCHS = 29
TB2_SEED = 20260715


def _tie_key(row: dict, method: str) -> tuple:
    if method == "TB1":
        return (-row["priority"], -row["unit_id"])
    if method == "TB2":
        digest = hashlib.sha256(f"{TB2_SEED}:{row['cell_id']}".encode()).hexdigest()
        return (-row["priority"], digest)
    return (-row["priority"], row["unit_id"])


def priority_batch(n: int, observed: set[int], scores: dict[int, float], batch_size: int,
                   method: str) -> tuple[list[int], list[dict]]:
    if method not in METHODS:
        raise ValueError("unknown H-SCAN1B method")
    temporary = set(observed); chosen, details = [], []
    log_norm = math.log2(n + 1.0)
    for _ in range(batch_size):
        candidates = []
        for cell in eligible_cells(n, temporary):
            unit = cell["unit_id"]; span = cell["unobserved_span_units"]
            u = span / n
            l = 0.5 * math.log2(span + 1.0) / log_norm
            if method == "F00":
                priority, included = 0.0, []
            elif method == "F10":
                priority, included = u, ["U_span_fraction"]
            elif method == "F01":
                priority, included = l, ["L_log_span_debt"]
            else:
                priority, included = u + l, ["U_span_fraction", "L_log_span_debt"]
            left, right = map(int, cell["cell_id"].split(":"))
            parent, level = _parent_and_level(n, (left, right))
            candidates.append({**cell, "parent_cell_id": parent, "scan_level": level,
                               "U_span_fraction": u, "L_log_span_debt": l,
                               "priority": priority, "included_components": included,
                               "tie_policy": method if method.startswith("TB") else "TB0"})
        if not candidates:
            break
        tie_method = method if method.startswith("TB") else "TB0"
        ordered = sorted(candidates, key=lambda row: _tie_key(row, tie_method))
        selected = dict(ordered[0]); selected["selected_rank"] = 1
        selected["next_best_cell"] = None if len(ordered) < 2 else {
            "cell_id": ordered[1]["cell_id"], "unit_id": ordered[1]["unit_id"],
            "priority": ordered[1]["priority"]}
        chosen.append(selected["unit_id"]); details.append(selected); temporary.add(selected["unit_id"])
    return chosen, details


def decide(payload: dict) -> dict:
    expected = {"method", "public_units", "proxy_rows", "queried_ids", "batch_size", "parameters"}
    if not isinstance(payload, dict) or set(payload) != expected:
        raise ValueError("H-SCAN1B payload schema mismatch")
    method = str(payload["method"])
    if method not in METHODS:
        raise ValueError("unknown H-SCAN1B method")
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


class HScan1BPolicyService:
    def __init__(self, connection, process, jail, initialization: dict) -> None:
        self._connection, self._process, self._jail = connection, process, jail
        self.initialization = dict(initialization)

    def decide(self, payload: dict) -> dict:
        self._connection.send(("decide", payload))
        status, response = _recv_with_timeout(self._connection, 10.0, "H-SCAN1B policy decision")
        if status != "ok":
            raise RuntimeError(str(response))
        return dict(response)

    def close(self) -> None:
        try:
            if self._process.is_alive():
                self._connection.send(("shutdown",))
                status, _ = _recv_with_timeout(self._connection, 10.0, "H-SCAN1B policy shutdown")
                if status != "ok":
                    raise RuntimeError("H-SCAN1B policy rejected shutdown")
                self._process.join(timeout=10)
        finally:
            self._connection.close()
            if self._process.is_alive():
                self._process.terminate(); self._process.join(timeout=5)
            self._jail.cleanup()


def start_hscan1b_policy_service() -> HScan1BPolicyService:
    context = mp.get_context("spawn"); receiver, sender = context.Pipe(duplex=True)
    jail = tempfile.TemporaryDirectory(prefix="psvr_hscan1b_jail_")
    process = context.Process(target=_worker, args=(sender, jail.name)); process.start(); sender.close()
    try:
        status, payload = _recv_with_timeout(receiver, 20.0, "H-SCAN1B startup")
        if status != "ready":
            raise RuntimeError(str(payload))
        return HScan1BPolicyService(receiver, process, jail, payload)
    except Exception:
        receiver.close()
        if process.is_alive():
            process.terminate(); process.join(timeout=5)
        jail.cleanup(); raise
