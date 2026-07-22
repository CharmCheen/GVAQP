"""Process-isolated, non-enumerable oracle capability.

The full frozen table is loaded only inside the service child.  A selector is
never given this accessor; the wall-clock runtime owns it and appends returned
observations to an EvidenceLedger before constructing a SelectorView.
"""

from __future__ import annotations

import multiprocessing as mp
from pathlib import Path
from typing import Callable


_RETURN_FIELDS = (
    "unit_id", "start_time", "end_time", "parsed_label", "confidence",
    "event_start_absolute", "event_end_absolute", "event_type", "involved_object",
)
_PUBLIC_ACCESSOR_NAMES = frozenset({"query", "queried_ids", "query_count"})


def _oracle_service_main(connection, cache_path: str) -> None:
    import pandas as pd

    table = pd.read_csv(cache_path).set_index("unit_id", drop=False)
    queried: set[int] = set()
    try:
        while True:
            request = connection.recv()
            operation = request[0]
            if operation == "shutdown":
                connection.send(("ok", None)); break
            if operation == "query":
                unit_id = int(request[1])
                if unit_id in queried:
                    connection.send(("error", f"duplicate query: {unit_id}")); continue
                if unit_id not in table.index:
                    connection.send(("error", f"unknown unit: {unit_id}")); continue
                queried.add(unit_id)
                row = table.loc[unit_id]
                result = {key: row[key] for key in _RETURN_FIELDS if key in row.index}
                result["unit_id"] = unit_id
                connection.send(("ok", result)); continue
            if operation == "queried_ids":
                connection.send(("ok", tuple(sorted(queried)))); continue
            if operation == "query_count":
                connection.send(("ok", len(queried))); continue
            connection.send(("error", "operation is not in the oracle capability protocol"))
    finally:
        connection.close()


class OracleAccessor:
    """Restricted runtime facade: exactly query/queried_ids/query_count."""

    __slots__ = ("__request",)

    def __init__(self, request: Callable[[tuple], object]) -> None:
        object.__setattr__(self, "_OracleAccessor__request", request)

    def __dir__(self) -> list[str]:
        return sorted(_PUBLIC_ACCESSOR_NAMES)

    def __getattribute__(self, name: str):
        if name in _PUBLIC_ACCESSOR_NAMES or name in {
            "__class__", "__dir__", "__doc__", "__slots__", "__getattribute__"
        }:
            return object.__getattribute__(self, name)
        raise AttributeError(f"OracleAccessor exposes no attribute {name!r}")

    def query(self, unit_id: int) -> dict:
        request = object.__getattribute__(self, "_OracleAccessor__request")
        return dict(request(("query", int(unit_id))))

    def queried_ids(self) -> tuple[int, ...]:
        request = object.__getattribute__(self, "_OracleAccessor__request")
        return tuple(request(("queried_ids",)))

    def query_count(self) -> int:
        request = object.__getattribute__(self, "_OracleAccessor__request")
        return int(request(("query_count",)))


class OracleServiceHandle:
    """Launcher-owned lifecycle handle. Never pass this object to a selector."""

    __slots__ = ("_accessor", "_connection", "_process")

    def __init__(self, accessor: OracleAccessor, connection, process: mp.Process) -> None:
        self._accessor = accessor
        self._connection = connection
        self._process = process

    def runtime_accessor(self) -> OracleAccessor:
        return self._accessor

    def close(self) -> None:
        if self._process.is_alive():
            self._connection.send(("shutdown",))
            self._connection.recv()
            self._process.join(timeout=10)
        self._connection.close()
        if self._process.is_alive():
            self._process.terminate(); self._process.join(timeout=5)


def start_oracle_service(cache_path: Path) -> OracleServiceHandle:
    """Start service; cache_path remains launcher/service-side, not runtime config."""

    path = Path(cache_path).resolve(strict=True)
    context = mp.get_context("spawn")
    parent, child = context.Pipe(duplex=True)
    process = context.Process(target=_oracle_service_main, args=(child, str(path)), daemon=True)
    process.start(); child.close()

    def request(message: tuple):
        parent.send(message)
        status, payload = parent.recv()
        if status != "ok":
            raise RuntimeError(str(payload))
        return payload

    accessor = OracleAccessor(request)
    return OracleServiceHandle(accessor, parent, process)
