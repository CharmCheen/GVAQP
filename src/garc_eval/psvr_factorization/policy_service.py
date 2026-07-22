"""Sandboxed policies for the preregistered H-FACT1 2x2 factorization."""

from __future__ import annotations

import hashlib
import json
import math
import multiprocessing as mp
import os
import tempfile

from garc_eval.psvr_pilot.policy_service import _coverage_debt_batch, _coverage_grid_batch, coverage_state
from garc_eval.psvr_runtime.sandbox import _enter_empty_unprivileged_jail, _recv_with_timeout


FACTOR_METHODS = frozenset({"C0", "C1", "C2", "C3"})
S0_METHODS = frozenset({"C0", "C2"})
A0_METHODS = frozenset({"C0", "C1"})
FIXED_SCAN_EPOCHS = 29


def decide(payload: dict) -> dict:
    expected = {"method", "public_units", "proxy_rows", "queried_ids", "batch_size", "parameters"}
    if not isinstance(payload, dict) or set(payload) != expected:
        raise ValueError("factor policy payload schema mismatch")
    method = str(payload["method"])
    if method not in FACTOR_METHODS:
        raise ValueError("unknown factor method")
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
    observed = set(scores)
    queried = {int(value) for value in payload["queried_ids"]}
    if not queried.issubset(observed):
        raise ValueError("queried unit was not physically scanned")
    available = sorted(observed - queried, key=lambda unit: (-scores[unit], unit))
    params = dict(payload["parameters"]); scans = int(params.get("scan_actions", 0))

    if method in A0_METHODS:
        desired = "scan" if scans < FIXED_SCAN_EPOCHS else ("query" if available else "stop")
    else:
        desired = "scan" if not available or scans <= len(queried) else "query"
    scan, priorities = [], []
    if desired == "scan":
        if method in S0_METHODS:
            scan, priorities = _coverage_grid_batch(n, observed, batch_size)
        else:
            scan, priorities = _coverage_debt_batch(n, observed, scores, batch_size,
                                                     float(params.get("lambda", 0.5)),
                                                     float(params.get("beta", 0.25)))
        if not scan:
            desired = "query" if available else "stop"

    response = {
        "action": desired, "scan_unit_ids": scan,
        "candidate_unit_id": None if not available else int(available[0]),
        "scan_priorities": priorities, "coverage_state_before": coverage_state(n, observed),
        "worker_uid": os.geteuid(), "worker_root": os.getcwd(),
        "visible_proxy_units": len(observed), "visible_queried_units": len(queried),
        "scan_factor": "S0" if method in S0_METHODS else "S1",
        "allocation_factor": "A0" if method in A0_METHODS else "A1",
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


class FactorPolicyService:
    def __init__(self, connection, process, jail, initialization: dict) -> None:
        self._connection, self._process, self._jail = connection, process, jail
        self.initialization = dict(initialization)

    def decide(self, payload: dict) -> dict:
        self._connection.send(("decide", payload))
        status, response = _recv_with_timeout(self._connection, 10.0, "factor policy decision")
        if status != "ok":
            raise RuntimeError(str(response))
        return dict(response)

    def close(self) -> None:
        try:
            if self._process.is_alive():
                self._connection.send(("shutdown",))
                status, _ = _recv_with_timeout(self._connection, 10.0, "factor policy shutdown")
                if status != "ok":
                    raise RuntimeError("factor policy rejected shutdown")
                self._process.join(timeout=10)
        finally:
            self._connection.close()
            if self._process.is_alive():
                self._process.terminate(); self._process.join(timeout=5)
            self._jail.cleanup()


def start_factor_policy_service() -> FactorPolicyService:
    context = mp.get_context("spawn"); receiver, sender = context.Pipe(duplex=True)
    jail = tempfile.TemporaryDirectory(prefix="psvr_factor_policy_jail_")
    process = context.Process(target=_worker, args=(sender, jail.name)); process.start(); sender.close()
    try:
        status, payload = _recv_with_timeout(receiver, 20.0, "factor policy startup")
        if status != "ready":
            raise RuntimeError(str(payload))
        return FactorPolicyService(receiver, process, jail, payload)
    except Exception:
        receiver.close()
        if process.is_alive():
            process.terminate(); process.join(timeout=5)
        jail.cleanup(); raise
