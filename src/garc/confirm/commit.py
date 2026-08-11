from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any


class DurableCommitLog:
    """Transactional, fsync-backed snapshot of completed actions and final STOP."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.rows: list[dict[str, Any]] = []
        self.utility_ids: set[str] = set()
        self.final_result: dict[str, Any] | None = None

    def _write(self, value: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(value, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
            directory_fd = os.open(self.path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    @staticmethod
    def _snapshot(rows: list[dict[str, Any]], utility_ids: set[str], *,
                  status: str, final_result: dict[str, Any] | None = None,
                  stop_reason: str | None = None, error: dict[str, Any] | None = None) -> dict[str, Any]:
        value: dict[str, Any] = {
            "status": status,
            "actions": rows,
            "distinct_utility_ids": sorted(utility_ids),
        }
        if final_result is not None:
            value["final_result"] = final_result
        if stop_reason is not None:
            value["stop_reason"] = stop_reason
        if error is not None:
            value["error"] = error
        return value

    def append(self, row: dict[str, Any], utility_ids: tuple[str, ...] = ()) -> None:
        if not row.get("completed"):
            raise ValueError("only complete actions may be durably committed")
        new_rows = [*self.rows, dict(row)]
        new_utility = self.utility_ids | set(utility_ids)
        self._write(self._snapshot(new_rows, new_utility, status="RUNNING"))
        self.rows = new_rows
        self.utility_ids = new_utility

    def finalize(self, final_result: dict[str, Any], *, stop_reason: str,
                 error: dict[str, Any] | None = None) -> None:
        """Durably record STOP/final state without inventing an action row."""
        final = dict(final_result)
        self._write(self._snapshot(self.rows, self.utility_ids, status="FINAL",
                                   final_result=final, stop_reason=stop_reason, error=error))
        self.final_result = final
