#!/usr/bin/env python3
from __future__ import annotations

import subprocess

from repair_common import PROJECT_ROOT, REPAIR_DIR, append_progress, ensure_dirs


def run(cmd: list[str]) -> str:
    return subprocess.run(cmd, cwd=PROJECT_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False).stdout


def main() -> None:
    ensure_dirs()
    status = run(["git", "status"])
    (REPAIR_DIR / "reports/GIT_STATUS_SNAPSHOT.txt").write_text(status, encoding="utf-8")
    short = run(["git", "status", "--short", "--", "AGENTS.md"])
    if short.strip():
        diff = run(["git", "diff", "--", "AGENTS.md"])
        (REPAIR_DIR / "reports/AGENTS_MD_DIFF.txt").write_text(diff or "AGENTS.md modified, but git diff produced no text.\n", encoding="utf-8")
    else:
        (REPAIR_DIR / "reports/AGENTS_MD_DIFF.txt").write_text("AGENTS.md is clean.\n", encoding="utf-8")
    append_progress(
        "R6 git hygiene snapshot",
        "python scripts/r60_git_hygiene_snapshot.py",
        "wrote GIT_STATUS_SNAPSHOT.txt and AGENTS_MD_DIFF.txt without modifying git state",
    )


if __name__ == "__main__":
    main()
