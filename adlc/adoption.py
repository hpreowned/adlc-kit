"""Phase 8: the timed adoption walkthrough — exactly the steps in ADOPT.md, as a stranger
would run them, with a clock. Writes results/adoption-test.md; every deviation is a kit bug."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def _run(cmd: list[str], cwd: Path, env: dict | None = None) -> tuple[int, str, float]:
    t0 = time.time()
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env or os.environ)
    return r.returncode, (r.stdout + r.stderr)[-4000:], time.time() - t0


def run_adoption(repo: Path, results: Path, kit_url: str | None = None, task_id: str | None = None, tasks_root: Path | None = None) -> int:
    results.mkdir(parents=True, exist_ok=True)
    adlc = os.environ.get("ADLC_BIN", str(Path(sys.executable).parent / "adlc"))
    env = {**os.environ, "GRAPHIFY_BACKEND": "none", "GRAPHIFY_NO_TIPS": "1", "PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")}
    log, deviations = [], []
    start = time.time()
    log.append(f"# Adoption test — {repo.name}\n\nStarted {datetime.now(timezone.utc).isoformat(timespec='seconds')} (UTC). Following ADOPT.md only.\n")
    steps = [
        ("0 install kit", [adlc, "--version"]),
        ("1 adlc init", [adlc, "init", "--yes"]),
        ("2 fill AGENTS.md prose", None),
        ("3 adlc doctor", [adlc, "doctor"]),
        ("4 adlc baseline", [adlc, "baseline", "--no-viz"]),
        ("4b adlc stale", [adlc, "stale"]),
        ("3b adlc doctor (after baseline)", [adlc, "doctor"]),
        ("6 commit", ["git", "add", "-A"]),
    ]
    for name, cmd in steps:
        t = time.time()
        if cmd is None:
            agents = repo / "AGENTS.md"
            text = agents.read_text()
            fill = (repo / "ADOPTION_PROSE.md")
            if fill.exists():  # the stranger's prepared prose for this repo
                head, _, tail = text.partition("<!-- adlc:routing:start -->")
                text = head.split("\n## Build")[0].rstrip() + "\n\n" + fill.read_text().strip() + "\n\n<!-- adlc:routing:start -->" + tail
                agents.write_text(text)
                fill.unlink()
            rc, out = (0, "prose filled from ADOPTION_PROSE.md") if "TODO" not in agents.read_text() else (1, "TODOs remain")
        else:
            rc, out, _ = _run(cmd, repo, env)
        dt = time.time() - t
        status = "OK" if rc == 0 else f"EXIT {rc}"
        log.append(f"## {name} — {status} — {dt:.1f}s\n\n```\n{out.strip()[-1500:]}\n```\n")
        if rc != 0:
            deviations.append(f"{name}: exit {rc}")
    if task_id:
        t = time.time()
        cmd = [adlc, "eval", "--task", task_id, "--runs", "1", "--arms", "baseline,graphify", "--repos", str(repo.parent),
               "--results", str(results / "adoption-runs"), "--out", "adoption.jsonl"]
        if tasks_root:
            cmd += ["--tasks", str(tasks_root)]
        rc, out, _ = _run(cmd, repo.parent, env)
        log.append(f"## 5 one golden task in two arms — {'OK' if rc == 0 else 'EXIT ' + str(rc)} — {time.time() - t:.1f}s\n\n```\n{out.strip()[-2000:]}\n```\n")
        if rc != 0:
            deviations.append(f"golden task run: exit {rc}")
    total = time.time() - start
    log.append(f"## Result\n\nElapsed **{total / 60:.1f} min**. Deviations: {len(deviations)}" + ("".join(f"\n- {d}" for d in deviations) or " (none)") + "\n")
    (results / "adoption-test.md").write_text("\n".join(log))
    print(f"adoption test: {total / 60:.1f} min, {len(deviations)} deviation(s) → {results / 'adoption-test.md'}")
    return 1 if deviations or total > 15 * 60 else 0
