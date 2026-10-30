"""Thin git helpers (subprocess; no GitPython dependency)."""
from __future__ import annotations

import subprocess
from pathlib import Path


def _git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout.strip()


def head_sha(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD")


def commits_between(repo: Path, old: str, new: str = "HEAD") -> int | None:
    """Commits in `new` not in `old`; None if `old` is unknown to this clone."""
    try:
        return int(_git(repo, "rev-list", "--count", f"{old}..{new}"))
    except RuntimeError:
        return None


def is_dirty(repo: Path) -> bool:
    return bool(_git(repo, "status", "--porcelain"))
