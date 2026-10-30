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


ARTIFACT_PATHS = ("graphify-out", ".serena/memories", "project-graph.json", "org-graph.json",
                  "PROJECT_REPORT.md", "ORG_REPORT.md")


def commits_between(repo: Path, old: str, new: str = "HEAD", ignore_artifacts: bool = True) -> int | None:
    """Commits in `new` not in `old` that touch something other than the artifacts
    themselves (the baseline commit that lands graphify-out/ must not count as drift).
    None if `old` is unknown to this clone."""
    args = ["rev-list", "--count", f"{old}..{new}"]
    if ignore_artifacts:
        args += ["--", ".", *(f":(exclude){p}" for p in ARTIFACT_PATHS)]
    try:
        return int(_git(repo, *args))
    except RuntimeError:
        return None


def is_dirty(repo: Path) -> bool:
    return bool(_git(repo, "status", "--porcelain"))
