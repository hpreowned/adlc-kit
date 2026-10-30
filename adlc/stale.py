"""`adlc stale`: is the context artifact current with HEAD?

Exit codes: 0 fresh · 1 stale-but-usable (≤ threshold commits behind) · 2 stale/missing.
The stamp lives in graphify-out/adlc-stamp.json (sidecar, survives graphify rewrites)
with a mirror inside graph.json["graph"]["adlc"]."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from adlc import contract as C
from adlc.gitinfo import commits_between, head_sha

STAMP_NAME = "adlc-stamp.json"


@dataclass
class Staleness:
    artifact: str
    exists: bool
    stamped_sha: str | None
    head: str
    behind: int | None          # commits HEAD is ahead of the stamp; None = unknown
    threshold: int
    level: str = "repo"

    @property
    def exit_code(self) -> int:
        if not self.exists or self.stamped_sha is None or self.behind is None:
            return 2
        if self.behind == 0:
            return 0
        return 1 if self.behind <= self.threshold else 2

    def line(self) -> str:
        state = {0: "FRESH", 1: "STALE (usable)", 2: "STALE"}[self.exit_code]
        b = "?" if self.behind is None else str(self.behind)
        sha = (self.stamped_sha or "none")[:10]
        return f"[{self.level}] {state}: {self.artifact} stamped {sha}, HEAD {self.head[:10]}, {b} commits behind (threshold {self.threshold})"


def stamp_path(repo: Path, artifact: str) -> Path:
    return (repo / artifact).parent / STAMP_NAME


def read_stamp(repo: Path, artifact: str) -> dict | None:
    sp = stamp_path(repo, artifact)
    if sp.exists():
        return json.loads(sp.read_text())
    gp = repo / artifact
    if gp.exists():
        try:
            return (json.loads(gp.read_text()).get("graph") or {}).get("adlc")
        except (json.JSONDecodeError, AttributeError):
            return None
    return None


def check(repo: Path, artifact: str, threshold: int = 10) -> Staleness:
    head = head_sha(repo)
    exists = (repo / artifact).exists()
    stamp = read_stamp(repo, artifact) if exists else None
    sha = (stamp or {}).get("commit_sha")
    behind = commits_between(repo, sha, head) if sha else None
    return Staleness(artifact, exists, sha, head, behind, threshold)


def add_parser(sub) -> None:
    p = sub.add_parser("stale", help="check artifact freshness vs HEAD (exit 0/1/2)")
    p.add_argument("--repo", default=".", help="repo root (default: cwd)")
    p.add_argument("--level", choices=["repo", "project", "org"], default="repo")
    p.add_argument("--all", action="store_true", help="check repo plus any federated levels configured")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=run)


def run(args) -> int:
    repo = Path(args.repo).resolve()
    if args.level != "repo":
        from adlc.federate import stale_federated
        return stale_federated(repo, args.level, as_json=args.json)
    c = C.load(repo)
    s = check(repo, c.artifact, c.stale_threshold)
    print(json.dumps(s.__dict__) if args.json else s.line())
    worst = s.exit_code
    if args.all:
        from adlc.federate import stale_federated
        for level in ("project", "org"):
            try:
                worst = max(worst, stale_federated(repo, level, as_json=args.json))
            except SystemExit as e:  # no federated graph reachable from here — report, don't fail
                print(f"[{level}] not configured ({e})")
    return worst
