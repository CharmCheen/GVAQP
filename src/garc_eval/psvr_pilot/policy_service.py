"""Leakage-safe deterministic policies for the PSVR physical pilot.

The worker is loaded before entering the same empty-chroot/unprivileged boundary
used by the frozen selector.  It receives only public unit rows, proxy values
already materialized by the physical producer, and queried unit identifiers.
"""

from __future__ import annotations

import hashlib
import json
import math
import multiprocessing as mp
import os
import tempfile

from garc_eval.psvr_runtime.sandbox import _enter_empty_unprivileged_jail, _recv_with_timeout


METHODS = frozenset({
    "scan_then_verify",
    "sequential_interleave",
    "uniform_temporal_interleave",
    "coverage_interleave",
    "coverage_debt_psvr",
})


def _unobserved_blocks(n: int, observed: set[int]) -> list[tuple[int, int]]:
    blocks: list[tuple[int, int]] = []
    start = None
    for unit_id in range(n):
        if unit_id not in observed and start is None:
            start = unit_id
        if unit_id in observed and start is not None:
            blocks.append((start, unit_id - 1)); start = None
    if start is not None:
        blocks.append((start, n - 1))
    return blocks


def coverage_state(n: int, observed_ids: set[int]) -> dict:
    blocks = _unobserved_blocks(n, observed_ids)
    spans = [right - left + 1 for left, right in blocks]
    return {
        "observed_units": len(observed_ids),
        "temporal_coverage": len(observed_ids) / n,
        "max_unobserved_units": max(spans, default=0),
        "coverage_debt": sum(span * span for span in spans) / float(n * n),
    }


def _sequential_batch(n: int, observed: set[int], batch_size: int) -> tuple[list[int], list[dict]]:
    chosen = [unit_id for unit_id in range(n) if unit_id not in observed][:batch_size]
    return chosen, [{"unit_id": unit_id, "rule": "chronological"} for unit_id in chosen]


def _coverage_grid_batch(n: int, observed: set[int], batch_size: int) -> tuple[list[int], list[dict]]:
    coarse = list(range(1, n, 3))
    chosen = [unit_id for unit_id in coarse if unit_id not in observed][:batch_size]
    return chosen, [{"unit_id": unit_id, "rule": "fixed_30_second_grid"} for unit_id in chosen]


def _farthest_batch(n: int, observed: set[int], batch_size: int) -> tuple[list[int], list[dict]]:
    temporary = set(observed); chosen: list[int] = []; details: list[dict] = []
    for _ in range(batch_size):
        blocks = _unobserved_blocks(n, temporary)
        if not blocks:
            break
        left, right = max(blocks, key=lambda pair: (pair[1] - pair[0] + 1, -pair[0]))
        unit_id = (left + right) // 2
        chosen.append(unit_id); temporary.add(unit_id)
        details.append({"unit_id": unit_id, "rule": "largest_gap_midpoint",
                        "unobserved_span_units": right - left + 1})
    return chosen, details


def _local_signal(unit_id: int, scores: dict[int, float]) -> float:
    if not scores:
        return 0.0
    scale = max(1.0, max(abs(value) for value in scores.values()))
    return max((max(0.0, value) / scale) / (1.0 + abs(unit_id - seen))
               for seen, value in scores.items())


def _coverage_debt_batch(n: int, observed: set[int], scores: dict[int, float],
                         batch_size: int, lam: float, beta: float) -> tuple[list[int], list[dict]]:
    temporary = set(observed); chosen: list[int] = []; details: list[dict] = []
    log_norm = math.log2(n + 1.0)
    for _ in range(batch_size):
        candidates: list[tuple[float, int, dict]] = []
        for left, right in _unobserved_blocks(n, temporary):
            span = right - left + 1
            # The cell representative is its temporal midpoint.  No unobserved
            # proxy value enters this priority.
            unit_id = (left + right) // 2
            duration_term = span / n
            level_debt = math.log2(span + 1.0) / log_norm
            signal = _local_signal(unit_id, scores)
            priority = duration_term + lam * level_debt + beta * signal
            detail = {
                "unit_id": unit_id,
                "rule": "coverage_debt",
                "unobserved_span_units": span,
                "normalized_unobserved_duration": duration_term,
                "scan_level_debt": level_debt,
                "observed_local_proxy_signal": signal,
                "priority": priority,
            }
            candidates.append((priority, -unit_id, detail))
        if not candidates:
            break
        _, _, detail = max(candidates)
        unit_id = int(detail["unit_id"])
        chosen.append(unit_id); details.append(detail); temporary.add(unit_id)
    return chosen, details


def decide(payload: dict) -> dict:
    expected = {"method", "public_units", "proxy_rows", "queried_ids", "batch_size", "parameters"}
    if not isinstance(payload, dict) or set(payload) != expected:
        raise ValueError("pilot policy payload schema mismatch")
    method = str(payload["method"])
    if method not in METHODS:
        raise ValueError("unknown pilot method")
    units = list(payload["public_units"])
    ids = sorted(int(row["unit_id"]) for row in units)
    if ids != list(range(len(ids))):
        raise ValueError("pilot units must be contiguous public identifiers")
    n = len(ids); batch_size = int(payload["batch_size"])
    if batch_size != 4:
        raise ValueError("physical pilot batch size is frozen at four")
    scores: dict[int, float] = {}
    for row in payload["proxy_rows"]:
        unit_id = int(row["unit_id"]); value = float(row["proxy_score"])
        if unit_id not in ids or not math.isfinite(value):
            raise ValueError("invalid observed proxy row")
        scores[unit_id] = max(value, scores.get(unit_id, float("-inf")))
    observed = set(scores)
    queried = {int(value) for value in payload["queried_ids"]}
    if not queried.issubset(observed):
        raise ValueError("queried unit was not physically scanned")
    available = sorted(observed - queried, key=lambda unit_id: (-scores[unit_id], unit_id))
    parameters = dict(payload["parameters"])

    if method == "scan_then_verify":
        if len(observed) < n:
            action = "scan"
            scan, priorities = _sequential_batch(n, observed, batch_size)
        elif available:
            action, scan, priorities = "query", [], []
        else:
            action, scan, priorities = "stop", [], []
    elif method == "coverage_interleave":
        coarse = set(range(1, n, 3))
        if not coarse.issubset(observed):
            action = "scan"
            scan, priorities = _coverage_grid_batch(n, observed, batch_size)
        elif available:
            action, scan, priorities = "query", [], []
        else:
            action, scan, priorities = "stop", [], []
    else:
        # One scan batch followed by one verification gives the three true
        # interleaving methods identical action granularity.
        scan_actions = int(parameters.get("scan_actions", 0))
        query_actions = len(queried)
        if not available or scan_actions <= query_actions:
            action = "scan"
            if method == "sequential_interleave":
                scan, priorities = _sequential_batch(n, observed, batch_size)
            elif method == "uniform_temporal_interleave":
                scan, priorities = _farthest_batch(n, observed, batch_size)
            else:
                lam = float(parameters.get("lambda", 0.5))
                beta = float(parameters.get("beta", 0.25))
                scan, priorities = _coverage_debt_batch(n, observed, scores, batch_size, lam, beta)
            if not scan:
                action = "query" if available else "stop"
        else:
            action, scan, priorities = "query", [], []

    candidate = None if not available else int(available[0])
    state = coverage_state(n, observed)
    response = {
        "action": action,
        "scan_unit_ids": scan,
        "candidate_unit_id": candidate,
        "scan_priorities": priorities,
        "coverage_state_before": state,
        "worker_uid": os.geteuid(),
        "worker_root": os.getcwd(),
        "visible_proxy_units": len(observed),
        "visible_queried_units": len(queried),
    }
    response["decision_sha256"] = hashlib.sha256(
        json.dumps(response, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
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


class PilotPolicyService:
    def __init__(self, connection, process, jail, initialization: dict) -> None:
        self._connection = connection; self._process = process; self._jail = jail
        self.initialization = dict(initialization)

    def decide(self, payload: dict) -> dict:
        self._connection.send(("decide", payload))
        status, response = _recv_with_timeout(self._connection, 10.0, "pilot policy decision")
        if status != "ok":
            raise RuntimeError(str(response))
        return dict(response)

    def close(self) -> None:
        try:
            if self._process.is_alive():
                self._connection.send(("shutdown",))
                status, _ = _recv_with_timeout(self._connection, 10.0, "pilot policy shutdown")
                if status != "ok":
                    raise RuntimeError("pilot policy rejected shutdown")
                self._process.join(timeout=10)
        finally:
            self._connection.close()
            if self._process.is_alive():
                self._process.terminate(); self._process.join(timeout=5)
            self._jail.cleanup()


def start_pilot_policy_service() -> PilotPolicyService:
    context = mp.get_context("spawn")
    receiver, sender = context.Pipe(duplex=True)
    jail = tempfile.TemporaryDirectory(prefix="psvr_pilot_policy_jail_")
    process = context.Process(target=_worker, args=(sender, jail.name))
    process.start(); sender.close()
    try:
        status, payload = _recv_with_timeout(receiver, 20.0, "pilot policy startup")
        if status != "ready":
            raise RuntimeError(f"pilot policy startup failed: {payload}")
        return PilotPolicyService(receiver, process, jail, payload)
    except Exception:
        receiver.close()
        if process.is_alive():
            process.terminate(); process.join(timeout=5)
        jail.cleanup()
        raise
