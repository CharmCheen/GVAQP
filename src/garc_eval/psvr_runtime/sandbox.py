"""OS capability boundary for untrusted selector/runtime policy code.

The oracle accessor remains in the trusted launcher.  Selector, scheduler, and
runtime policy code execute in a freshly spawned process that is chrooted into an empty
directory and then permanently drops to the nobody uid/gid.  The worker gets
only a serialized SelectorView.  Consequently repository paths and evaluator
modules are absent as OS capabilities, not merely hidden Python attributes.
"""

from __future__ import annotations

import multiprocessing as mp
import gc
import hashlib
import importlib.util
import inspect
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Iterable, Mapping

from .views import SelectorView


PUBLIC_UNIT_COLUMNS = frozenset({
    "benchmark_id", "video_id", "video_sha256", "unit_id", "start_frame", "end_frame",
    "start_time", "end_time", "duration_seconds", "split_role", "eligible_for_query", "anchor_id",
})
MATERIALIZER_TRACE_COLUMNS = frozenset({"unit_id", "oracle_label_after_query"})
RUN_CONFIG_COLUMNS = frozenset({
    "benchmark_id", "run_id", "method", "method_variant", "seed", "horizon_budget",
})
SELECTOR_PROXY_COLUMNS = frozenset({"unit_id", "proxy_score", "timestamp_seconds"})
SELECTOR_ORACLE_COLUMNS = frozenset({"unit_id", "parsed_label", "confidence", "parse_status"})
_LABEL_DOMAIN = frozenset({"positive", "negative", "abstain"})


def _validate_exact_columns(rows: list[dict], allowed: frozenset[str], *, required: frozenset[str], kind: str) -> None:
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise TypeError(f"{kind} row {index} is not a mapping")
        columns = frozenset(map(str, row))
        extra = sorted(columns - allowed)
        missing = sorted(required - columns)
        if extra or missing:
            raise ValueError(f"invalid {kind} columns at row {index}: extra={extra}, missing={missing}")


def _validate_materializer_payload(payload: dict) -> None:
    if not isinstance(payload, dict) or frozenset(payload) != frozenset({"trace_rows", "unit_rows", "run_config"}):
        raise ValueError("materializer payload schema mismatch")
    trace_rows = payload["trace_rows"]
    unit_rows = payload["unit_rows"]
    run_config = payload["run_config"]
    if not isinstance(trace_rows, list) or not isinstance(unit_rows, list) or not isinstance(run_config, dict):
        raise TypeError("materializer payload types are invalid")
    _validate_exact_columns(
        trace_rows, MATERIALIZER_TRACE_COLUMNS, required=MATERIALIZER_TRACE_COLUMNS, kind="trace",
    )
    _validate_exact_columns(
        unit_rows, PUBLIC_UNIT_COLUMNS, required=PUBLIC_UNIT_COLUMNS, kind="public-unit",
    )
    if frozenset(run_config) != RUN_CONFIG_COLUMNS:
        raise ValueError("runtime materializer config schema mismatch")
    for key, value in run_config.items():
        if isinstance(value, (dict, list, tuple, set)):
            raise TypeError(f"nested runtime materializer config is forbidden: {key}")
        if isinstance(value, str) and (
            value.startswith(("/", "file:")) or "../" in value or "\\" in value
        ):
            raise ValueError(f"path-like runtime materializer config is forbidden: {key}")
    for row in trace_rows:
        try:
            int(row["unit_id"])
        except (TypeError, ValueError) as exc:
            raise ValueError("trace unit_id must be integral") from exc
        if str(row["oracle_label_after_query"]).lower() not in _LABEL_DOMAIN:
            raise ValueError("trace label is outside the frozen oracle domain")


def _recv_with_timeout(connection, timeout_seconds: float, context: str):
    if not connection.poll(timeout_seconds):
        raise TimeoutError(f"{context} timed out")
    try:
        return connection.recv()
    except EOFError as exc:
        raise RuntimeError(f"{context} closed unexpectedly") from exc


def _enter_empty_unprivileged_jail(jail: str) -> None:
    if os.geteuid() != 0:
        raise RuntimeError("filesystem capability sandbox requires root to chroot and drop uid")
    for name in tuple(sys.modules):
        if name == "garc_eval.psvr_evaluation" or name.startswith("garc_eval.psvr_evaluation."):
            del sys.modules[name]
    os.chroot(jail)
    os.chdir("/")
    os.setgroups([])
    os.setgid(65534)
    os.setuid(65534)


def _sandbox_probe_worker(sender, jail: str, public_units, scanned_proxy, queried_oracle,
                          forbidden_paths: tuple[str, ...]) -> None:
    result: dict = {}
    try:
        _enter_empty_unprivileged_jail(jail)

        view = SelectorView.build(public_units, scanned_proxy, queried_oracle)
        result["visible_labels"] = view.visible_label_count()
        result["visible_label_ids"] = sorted(
            int(row["unit_id"]) for row in view.queried_oracle_observations if "parsed_label" in row
        )
        result["worker_uid"] = os.geteuid()
        result["worker_root"] = os.getcwd()

        try:
            __import__("garc_eval.psvr_evaluation.reference_provider", fromlist=["load_reference"])
            result["evaluator_import"] = "EXPOSED"
        except Exception as exc:
            result["evaluator_import"] = f"BLOCKED:{type(exc).__name__}"

        path_results = {}
        for path in forbidden_paths:
            try:
                with open(path, "rb") as fh:
                    fh.read(1)
                path_results[path] = "EXPOSED"
            except Exception as exc:
                path_results[path] = f"BLOCKED:{type(exc).__name__}"
        result["direct_path_access"] = path_results
        # The accessor is deliberately not a worker argument/capability.
        result["oracle_accessor_present"] = "accessor" in locals()
        stack_names = {name for frame in inspect.stack() for name in frame.frame.f_locals}
        gc_sensitive = []
        for value in gc.get_objects():
            try:
                type_name = type(value).__name__
                if type_name in {"OracleAccessor", "OracleServiceHandle"}:
                    gc_sensitive.append(type_name)
                columns = set(map(str, getattr(value, "columns", ())))
                if {"parsed_label", "raw_output_path"} & columns or "event_id" in columns:
                    gc_sensitive.append(f"DataFrame:{sorted(columns)}")
            except Exception:
                continue
        result["memory_enumeration_attack"] = {
            "sensitive_stack_names": sorted(stack_names & {"accessor", "public_proxy", "reference", "oracle_table", "cache_table"}),
            "sensitive_gc_objects": gc_sensitive,
        }
        result["status"] = "ok"
    except Exception as exc:
        result = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
    sender.send(result)
    sender.close()


def adversarial_sandbox_probe(
    public_units: Iterable[Mapping],
    scanned_proxy: Iterable[Mapping],
    queried_oracle: Iterable[Mapping],
    forbidden_paths: Iterable[Path],
) -> dict:
    """Execute real import/open attacks inside the compliant runtime worker."""

    # spawn is mandatory: fork would inherit the sensitive launcher's heap.
    context = mp.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    # The jail exists only for this worker and contains no repository bind mounts.
    with tempfile.TemporaryDirectory(prefix="psvr_runtime_jail_") as jail:
        process = context.Process(
            target=_sandbox_probe_worker,
            args=(sender, jail, tuple(public_units), tuple(scanned_proxy), tuple(queried_oracle),
                  tuple(str(Path(path).resolve()) for path in forbidden_paths)),
        )
        process.start()
        sender.close()
        result = receiver.recv()
        process.join(timeout=20)
        receiver.close()
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
            raise RuntimeError("runtime sandbox probe timed out")
        result["exitcode"] = process.exitcode
    return result


def _materializer_worker(sender, jail: str, materializer_path: str, trace, units, run_config,
                         k3_profile: str, k3_config: dict) -> None:
    try:
        # Pandas imports this serializer lazily from DataFrame.to_dict(); preload
        # code only while the filesystem is present, before policy data executes.
        import pandas.core.methods.to_dict  # noqa: F401
        spec = importlib.util.spec_from_file_location("isolated_unchanged_k3", materializer_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load materializer")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _enter_empty_unprivileged_jail(jail)
        events = module.materialize_from_trace(trace, units, run_config, k3_profile, k3_config)
        sender.send({"status": "ok", "events": events.to_dict("records"), "worker_uid": os.geteuid()})
    except Exception as exc:
        sender.send({"status": "failed", "error": f"{type(exc).__name__}: {exc}"})
    sender.close()


def isolated_materialize(materializer_path: Path, trace, units, run_config: dict,
                         k3_profile: str, k3_config: dict):
    """Execute unchanged K3 in a clean spawned process with no reference capability."""

    context = mp.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    with tempfile.TemporaryDirectory(prefix="psvr_materializer_jail_") as jail:
        process = context.Process(
            target=_materializer_worker,
            args=(sender, jail, str(Path(materializer_path).resolve()), trace, units, run_config, k3_profile, k3_config),
        )
        process.start(); sender.close()
        result = receiver.recv(); process.join(timeout=20); receiver.close()
        if process.is_alive():
            process.terminate(); process.join(timeout=5)
            raise RuntimeError("isolated materializer timed out")
    if result.get("status") != "ok" or process.exitcode != 0:
        raise RuntimeError(result.get("error", f"materializer exit {process.exitcode}"))
    return result


def _persistent_materializer_main(connection, jail: str, materializer_path: str) -> None:
    try:
        import pandas as pd
        import pandas.core.methods.to_dict  # noqa: F401
        spec = importlib.util.spec_from_file_location("persistent_unchanged_k3", materializer_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load persistent materializer")
        module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
        _enter_empty_unprivileged_jail(jail)
        connection.send(("ready", {"worker_uid": os.geteuid(), "worker_root": os.getcwd()}))
        while True:
            request = connection.recv(); operation = request[0]
            if operation == "shutdown":
                connection.send(("ok", None)); break
            if operation != "materialize":
                connection.send(("error", "operation not allowed")); continue
            payload = request[1]
            try:
                _validate_materializer_payload(payload)
                trace = pd.DataFrame(payload["trace_rows"], columns=["unit_id", "oracle_label_after_query"])
                units = pd.DataFrame(payload["unit_rows"], columns=sorted(PUBLIC_UNIT_COLUMNS))
                events = module.materialize_from_trace(
                    trace, units, payload["run_config"], "k3_bridge_safe",
                    {"g_max": 1, "d_core_max": 40.0, "d_seg_max": 60.0},
                )
                connection.send(("ok", events.to_dict("records")))
            except Exception as exc:
                connection.send(("error", f"{type(exc).__name__}: {exc}"))
    except Exception as exc:
        try:
            connection.send(("startup_error", f"{type(exc).__name__}: {exc}"))
        except Exception:
            pass
    finally:
        connection.close()


class MaterializerServiceHandle:
    """Persistent clean-address-space K3 capability with no filesystem access."""

    def __init__(self, connection, process, jail, initialization: dict) -> None:
        self.__connection = connection; self.__process = process; self.__jail = jail
        self.initialization = dict(initialization)

    def materialize(self, trace_rows: list[dict], unit_rows: list[dict], run_config: dict) -> list[dict]:
        payload = {
            "trace_rows": trace_rows, "unit_rows": unit_rows, "run_config": run_config,
        }
        _validate_materializer_payload(payload)
        self.__connection.send(("materialize", payload))
        status, response = _recv_with_timeout(self.__connection, 30.0, "materializer request")
        if status != "ok":
            raise RuntimeError(str(response))
        return list(response)

    def close(self) -> None:
        try:
            if self.__process.is_alive():
                self.__connection.send(("shutdown",))
                status, _ = _recv_with_timeout(self.__connection, 10.0, "materializer shutdown")
                if status != "ok":
                    raise RuntimeError("materializer rejected shutdown")
                self.__process.join(timeout=10)
        finally:
            self.__connection.close()
            if self.__process.is_alive():
                self.__process.terminate(); self.__process.join(timeout=5)
            self.__jail.cleanup()


def start_materializer_service(materializer_path: Path) -> MaterializerServiceHandle:
    """Start K3 before the timed workload; subsequent calls measure K3 itself."""
    context = mp.get_context("spawn")
    receiver, sender = context.Pipe(duplex=True)
    jail = tempfile.TemporaryDirectory(prefix="psvr_persistent_materializer_jail_")
    process = context.Process(
        target=_persistent_materializer_main,
        args=(sender, jail.name, str(Path(materializer_path).resolve())),
    )
    process.start(); sender.close()
    try:
        # Importing the frozen pandas-based materializer from the shared
        # filesystem can exceed 30 seconds even though the isolated child is
        # healthy. Startup is predeadline; extending only this readiness wait
        # does not alter K3 execution or deadline accounting.
        status, payload = _recv_with_timeout(receiver, 120.0, "materializer startup")
        if status != "ready":
            raise RuntimeError(f"materializer service startup failed: {payload}")
        return MaterializerServiceHandle(receiver, process, jail, payload)
    except Exception:
        receiver.close()
        if process.is_alive():
            process.terminate(); process.join(timeout=5)
        jail.cleanup()
        raise


def _validate_selector_payload(payload: dict) -> None:
    expected = frozenset({"public_units", "scanned_proxy", "queried_oracle", "policy"})
    if not isinstance(payload, dict) or frozenset(payload) != expected:
        raise ValueError("selector payload schema mismatch")
    public_units = payload["public_units"]
    proxy = payload["scanned_proxy"]
    queried = payload["queried_oracle"]
    policy = payload["policy"]
    if not all(isinstance(rows, list) for rows in (public_units, proxy, queried)) or not isinstance(policy, dict):
        raise TypeError("selector payload types are invalid")
    _validate_exact_columns(public_units, PUBLIC_UNIT_COLUMNS, required=PUBLIC_UNIT_COLUMNS, kind="public-unit")
    _validate_exact_columns(
        proxy, SELECTOR_PROXY_COLUMNS, required=frozenset({"unit_id", "proxy_score"}), kind="proxy",
    )
    _validate_exact_columns(
        queried, SELECTOR_ORACLE_COLUMNS, required=frozenset({"unit_id"}), kind="queried-oracle",
    )
    mode = policy.get("mode")
    if mode == "ranked_proxy":
        if frozenset(policy) != frozenset({"mode", "rank_offset"}):
            raise ValueError("ranked selector policy schema mismatch")
        if int(policy["rank_offset"]) < 0:
            raise ValueError("rank_offset must be nonnegative")
    elif mode == "fixed_scanned_unit":
        if frozenset(policy) != frozenset({"mode", "unit_id"}):
            raise ValueError("fixed selector policy schema mismatch")
        int(policy["unit_id"])
    else:
        raise ValueError("unknown selector policy")


def _selector_service_main(connection, jail: str) -> None:
    try:
        _enter_empty_unprivileged_jail(jail)
        connection.send(("ready", {"worker_uid": os.geteuid(), "worker_root": os.getcwd()}))
        while True:
            request = connection.recv(); operation = request[0]
            if operation == "shutdown":
                connection.send(("ok", None)); break
            if operation != "select":
                connection.send(("error", "operation not allowed")); continue
            payload = request[1]
            try:
                _validate_selector_payload(payload)
                view = SelectorView.build(
                    payload["public_units"], payload["scanned_proxy"], payload["queried_oracle"],
                )
                public_ids = {int(row["unit_id"]) for row in view.public_units}
                queried_ids = {int(row["unit_id"]) for row in view.queried_oracle_observations}
                scores: dict[int, float] = {}
                for row in view.scanned_proxy_observations:
                    unit_id = int(row["unit_id"])
                    if unit_id not in public_ids:
                        raise ValueError("proxy observation is not a public unit")
                    scores[unit_id] = max(float(row["proxy_score"]), scores.get(unit_id, float("-inf")))
                policy = payload["policy"]
                if policy["mode"] == "fixed_scanned_unit":
                    selected = int(policy["unit_id"])
                    if selected not in scores or selected in queried_ids:
                        raise ValueError("fixed candidate is not scanned and unqueried")
                else:
                    ranked = [
                        unit_id for unit_id in sorted(scores, key=lambda item: (-scores[item], item))
                        if unit_id not in queried_ids
                    ]
                    offset = int(policy["rank_offset"])
                    if offset >= len(ranked):
                        raise ValueError("ranked selector exhausted")
                    selected = ranked[offset]
                trace = {
                    "candidate_unit_id": selected,
                    "visible_label_count": view.visible_label_count(),
                    "scanned_unit_count": len(scores),
                    "candidate_was_scanned": selected in scores,
                    "queried_ids": sorted(queried_ids),
                    "policy": policy,
                }
                trace["legal_action_trace_sha256"] = hashlib.sha256(
                    json.dumps(trace, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest()
                connection.send(("ok", trace))
            except Exception as exc:
                connection.send(("error", f"{type(exc).__name__}: {exc}"))
    except Exception as exc:
        try:
            connection.send(("startup_error", f"{type(exc).__name__}: {exc}"))
        except Exception:
            pass
    finally:
        connection.close()


class SelectorServiceHandle:
    """Persistent policy worker that can observe only serialized SelectorView data."""

    def __init__(self, connection, process, jail, initialization: dict) -> None:
        self.__connection = connection; self.__process = process; self.__jail = jail
        self.initialization = dict(initialization)

    def select(self, public_units: list[dict], scanned_proxy: list[dict],
               queried_oracle: list[dict], policy: dict) -> dict:
        payload = {
            "public_units": public_units, "scanned_proxy": scanned_proxy,
            "queried_oracle": queried_oracle, "policy": policy,
        }
        _validate_selector_payload(payload)
        self.__connection.send(("select", payload))
        status, response = _recv_with_timeout(self.__connection, 10.0, "selector request")
        if status != "ok":
            raise RuntimeError(str(response))
        return dict(response)

    def close(self) -> None:
        try:
            if self.__process.is_alive():
                self.__connection.send(("shutdown",))
                status, _ = _recv_with_timeout(self.__connection, 10.0, "selector shutdown")
                if status != "ok":
                    raise RuntimeError("selector rejected shutdown")
                self.__process.join(timeout=10)
        finally:
            self.__connection.close()
            if self.__process.is_alive():
                self.__process.terminate(); self.__process.join(timeout=5)
            self.__jail.cleanup()


def start_selector_service() -> SelectorServiceHandle:
    context = mp.get_context("spawn")
    receiver, sender = context.Pipe(duplex=True)
    jail = tempfile.TemporaryDirectory(prefix="psvr_selector_jail_")
    process = context.Process(target=_selector_service_main, args=(sender, jail.name))
    process.start(); sender.close()
    try:
        status, payload = _recv_with_timeout(receiver, 20.0, "selector startup")
        if status != "ready":
            raise RuntimeError(f"selector service startup failed: {payload}")
        return SelectorServiceHandle(receiver, process, jail, payload)
    except Exception:
        receiver.close()
        if process.is_alive():
            process.terminate(); process.join(timeout=5)
        jail.cleanup()
        raise
