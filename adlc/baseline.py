"""`adlc baseline`: build the canonical L0 graph (code only, GRAPHIFY_BACKEND=none),
cluster it, stamp it with commit_sha/generated_at. `--incremental` uses `graphify update`."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from adlc import __version__
from adlc import contract as C
from adlc.gitinfo import head_sha, is_dirty
from adlc.pins import load_pins
from adlc.stale import STAMP_NAME


def _env() -> dict:
    env = dict(os.environ)
    env.update({"GRAPHIFY_BACKEND": "none", "GRAPHIFY_NO_TIPS": "1", "GRAPHIFY_QUERY_LOG_DISABLE": "1",
                "PATH": str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")})
    env.pop("GEMINI_API_KEY", None); env.pop("OPENAI_API_KEY", None); env.pop("ANTHROPIC_API_KEY", None)
    return env


def _run(args: list[str], cwd: Path) -> str:
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, env=_env())
    if r.returncode != 0:
        raise SystemExit(f"{' '.join(args)} failed ({r.returncode}):\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    return r.stdout + r.stderr


def stamp(repo: Path, artifact: str, extra: dict | None = None) -> dict:
    gp = repo / artifact
    data = json.loads(gp.read_text())
    info = {
        "commit_sha": head_sha(repo), "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dirty": is_dirty(repo), "kit": __version__, "graphify": load_pins()["graphify"]["version"],
        "nodes": len(data.get("nodes", [])), "edges": len(data.get("links", [])), **(extra or {}),
    }
    data.setdefault("graph", {})["adlc"] = info
    gp.write_text(json.dumps(data, indent=None, separators=(",", ":")))
    (gp.parent / STAMP_NAME).write_text(json.dumps(info, indent=2) + "\n")
    return info


def build(repo: Path, incremental: bool = False, viz: bool = True) -> dict:
    c = C.load(repo)
    t0 = time.time()
    out_dir = (repo / c.artifact).parent
    if incremental and (repo / c.artifact).exists():
        log = _run(["graphify", "update", str(repo)], repo)
        mode = "incremental"
    else:
        log = _run(["graphify", "extract", str(repo)], repo)
        mode = "full"
    cluster = ["graphify", "cluster-only", str(repo), "--no-label"] + ([] if viz else ["--no-viz"])
    log += _run(cluster, repo)
    info = stamp(repo, c.artifact, {"mode": mode, "build_seconds": round(time.time() - t0, 1)})
    root = out_dir / ".graphify_root"
    if root.exists():  # absolute path; never committed (gitignored by init), harmless locally
        pass
    return info


def add_parser(sub) -> None:
    p = sub.add_parser("baseline", help="build + stamp the repo graph (code only, no LLM)")
    p.add_argument("--repo", default=".")
    p.add_argument("--incremental", action="store_true", help="graphify update instead of full extract")
    p.add_argument("--no-viz", action="store_true")
    p.set_defaults(func=run)


def run(args) -> int:
    repo = Path(args.repo).resolve()
    info = build(repo, incremental=args.incremental, viz=not args.no_viz)
    print(f"baseline {info['mode']}: {info['nodes']} nodes, {info['edges']} edges, {info['build_seconds']}s, stamped {info['commit_sha'][:10]}{' (dirty)' if info['dirty'] else ''}")
    return 0
