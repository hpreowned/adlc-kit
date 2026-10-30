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


def run_eval(args) -> int:
    from harness import judge as J
    from harness.runner import CopilotDriver, RunSpec, StubDriver, execute
    tasks = select_tasks(args)
    if not tasks:
        print("no tasks selected"); return 2
    arms = args.arms.split(",") if args.arms else TIER_ARMS.get(args.tier or 1, ARMS_DEFAULT)
    results = Path(args.results).resolve()
    results.mkdir(parents=True, exist_ok=True)
    repos = Path(args.repos).resolve()
    out = results / (args.out or f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl")
    if args.dry_run:
        driver = StubDriver(harness_dir() / "tests" / "fixtures" / "events_smoke.jsonl", answer="dry-run answer")
        judge = J.StubJudge()
    else:
        if not os.environ.get("COPILOT_GITHUB_TOKEN"):
            print("COPILOT_GITHUB_TOKEN missing"); return 2
        driver, judge = CopilotDriver(), J.CopilotJudge(model=args.judge_model)
    done = {json.loads(l)["run_id"] for l in out.read_text().splitlines() if l.strip()} if out.exists() else set()
    project_graph = next(iter(sorted((repos.parent / "org").glob("*/project-graph.json"))), None)
    n = 0
    for t in tasks:
        repo_dir = repos / t["repo"]
        if not repo_dir.exists():
            print(f"skip {t['id']}: {repo_dir} missing"); continue
        sha = baseline_sha(repo_dir)
        for arm in arms:
            if t.get("federated") and arm not in ("graphify-federated", "both") and args.tier == 3:
                pass
            for r in range(1, args.runs + 1):
                rid = f"{t['id']}__{arm}__r{r}"
                if rid in done:
                    continue
                spec = RunSpec(task=t, arm=arm, run=r, repo_dir=repo_dir, baseline_sha=sha, results_dir=results,
                               project_graph=project_graph, timeout=args.timeout, model=args.model)
                res = execute(spec, driver)
                rec = J.judge_record(res.record, t, judge)
                (res.raw_dir / "record.json").write_text(json.dumps(rec, indent=2))
                with out.open("a") as fh:
                    fh.write(json.dumps(rec) + "\n")
                n += 1
                print(f"{rid}: score={rec.get('judge_score')} tokens={rec['input_tokens']}+{rec['output_tokens']} calls={rec['model_calls']} wall={rec['wall_ms']}ms")
    if n:
        from harness.tasklint import load_tasks
        allt = {x["id"]: x for x in load_tasks(_tasks_root(args))}
        recs = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
        (results / "spotcheck.md").write_text(J.spotcheck_md(recs, allt))
    print(f"eval: {n} new run(s) → {out}")
    return 0


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
    p.set_defaults(func=run)


def run(args) -> int:
    if args.lint:
        return lint(args)
    if args.adoption_test:
        from adlc.adoption import run_adoption
        return run_adoption(Path(args.adoption_test).resolve(), Path(args.results).resolve())
    return run_eval(args)
