"""`adlc eval`: run the golden tasks per (task, arm, run). `--lint` validates tasks and
writes INDEX.md; `--dry-run` uses the stub driver + stub judge so the pipeline is
trusted before it costs anything; `--adoption-test` is Phase 8's timed walkthrough."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from adlc.paths import harness_dir

ARMS_DEFAULT = ["baseline", "serena", "graphify", "graphify-guard"]
TIER_ARMS = {1: ARMS_DEFAULT, 2: ARMS_DEFAULT, 3: ["baseline", "graphify", "graphify-federated", "both"]}


def _tasks_root(args) -> Path:
    return Path(args.tasks) if args.tasks else harness_dir() / "tasks"


def lint(args) -> int:
    from harness.tasklint import index_md, lint_all
    repos = Path(args.repos).resolve() if args.repos else None
    errs, tasks = lint_all(_tasks_root(args), repos)
    for e in errs:
        print(f"  FAIL  {e}")
    (_tasks_root(args) / "INDEX.md").write_text(index_md(tasks))
    print(f"task lint: {len(tasks)} tasks, " + ("OK" if not errs else f"{len(errs)} problem(s)"))
    return 1 if errs else 0


def select_tasks(args) -> list[dict]:
    from harness.tasklint import load_tasks
    tasks = load_tasks(_tasks_root(args))
    if args.tier:
        tasks = [t for t in tasks if t["tier"] == args.tier]
    if args.task:
        tasks = [t for t in tasks if t["id"] in set(args.task)]
    if args.repo:
        tasks = [t for t in tasks if t["repo"] in set(args.repo)]
    return tasks


def baseline_sha(repo_dir: Path) -> str:
    return subprocess.run(["git", "-C", str(repo_dir), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()


def _lock_out(out: Path):
    """Exclusive, non-blocking lock on <out>.lock for the life of the process (2026-11-01:
    two chains once wrote the same file concurrently and contaminated wall-clock)."""
    import fcntl
    fh = open(str(out) + ".lock", "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    return fh



def _done_runs(results: Path) -> set[str]:
    """run_ids that count as finished, across EVERY results/*.jsonl — the --out file is where
    new records go, not the only place old ones live. Invalid records (quota/session error,
    non-zero exit with no answer, `valid: false`) stay as history and are re-run on resume."""
    from harness.scorecard import is_valid
    done: set[str] = set()
    for f in sorted(results.glob("*.jsonl")):
        for l in f.read_text().splitlines():
            if l.strip():
                r = json.loads(l)
                if is_valid(r):
                    done.add(r["run_id"])
    return done


def add_parser(sub) -> None:
    p = sub.add_parser("eval", help="golden-task evaluation (lint / run / dry-run)")
    p.add_argument("--lint", action="store_true")
    p.add_argument("--tasks", default=None, help="tasks dir (default: kit harness/tasks)")
    p.add_argument("--repos", default="repos", help="dir holding the consuming repos")
    p.add_argument("--tier", type=int, default=None)
    p.add_argument("--task", action="append", default=None)
    p.add_argument("--repo", action="append", default=None)
    p.add_argument("--arms", default=None, help="comma list (default per tier)")
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--results", default="results")
    p.add_argument("--out", default=None, help="results file name (default <date>.jsonl)")
    p.add_argument("--dry-run", action="store_true", help="stub driver + stub judge, no spend")
    p.add_argument("--timeout", type=int, default=900)
    p.add_argument("--model", default=None, help="pin Copilot model for agent runs (default auto)")
    p.add_argument("--judge-model", default=None)
    p.add_argument("--adoption-test", default=None, metavar="REPO", help="Phase 8 timed walkthrough (see adlc/adoption.py)")
    p.add_argument("--judge-only", default=None, metavar="RESULTS_JSONL", help="(re)judge records in a results file; arm never passed to the judge")
    p.add_argument("--rejudge", action="store_true", help="with --judge-only: re-score even already-judged records")
    p.set_defaults(func=run)


def judge_only(args) -> int:
    from harness import judge as J
    from harness.tasklint import load_tasks
    path = Path(args.judge_only)
    tasks = {t["id"]: t for t in load_tasks(_tasks_root(args))}
    judge = J.StubJudge() if args.dry_run else J.CopilotJudge(model=args.judge_model)
    recs = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    n = 0
    for r in recs:
        if r.get("judge_score") is None or args.rejudge:
            J.judge_record(r, tasks[r["task"]], judge)
            n += 1
    path.write_text("".join(json.dumps(r) + "\n" for r in recs))
    print(f"judged {n} record(s) in {path}")
    return 0


def run(args) -> int:
    if args.lint:
        return lint(args)
    if args.judge_only:
        return judge_only(args)
    if args.adoption_test:
        from adlc.adoption import run_adoption
        return run_adoption(Path(args.adoption_test).resolve(), Path(args.results).resolve(),
                            task_id=(args.task or [None])[0], tasks_root=Path(args.tasks).resolve() if args.tasks else None)
    return run_eval(args)
