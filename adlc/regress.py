"""`adlc regress`: the 5-task smoke set on the winning arm, N runs, appended to
monitor/trend.jsonl as one aggregated row (never single-run numbers)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

from adlc.paths import harness_dir, monitor_dir


def trend_row(recs: list[dict], arm: str, pilot: dict | None) -> dict:
    from harness.scorecard import summarise
    s = summarise(recs)
    row = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "arm": arm, "runs": s["n"],
           "prompt_tokens_p50": s["prompt_tokens"]["p50"], "input_tokens_p50": s["input_tokens"]["p50"], "model_calls_p50": s["model_calls"]["p50"],
           "wall_ms_p50": s["wall_ms"]["p50"], "correctness": s["correctness"], "edit_pass_rate": s["edit_pass_rate"],
           "models": s["models"], "copilot_versions": s["copilot_versions"],
           "graphify": _pin("graphify"), "serena": _pin("serena")[:12]}
    for k, v in (pilot or {}).items():
        row.setdefault("pilot_median_" + k, v)
    return row


def _pin(name: str) -> str:
    from adlc.pins import load_pins
    p = load_pins()[name]
    return p.get("version") or p.get("commit", "")


def add_parser(sub) -> None:
    p = sub.add_parser("regress", help="smoke set on the winning arm → monitor/trend.jsonl")
    p.add_argument("--arm", default=None)
    p.add_argument("--runs", type=int, default=None)
    p.add_argument("--repos", default="repos")
    p.add_argument("--out", default="monitor/trend.jsonl")
    p.add_argument("--smoke", default=None, help="smoke.yml (default kit monitor/smoke.yml)")
    p.add_argument("--pilot-results", default="results", help="results dir whose medians become the drift baseline")
    p.add_argument("--repo", default=None, help="only smoke tasks of this repo (per-repo CI runs)")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=run)


def run(args) -> int:
    from types import SimpleNamespace
    from adlc.eval import run_eval
    cfg = yaml.safe_load(Path(args.smoke or monitor_dir() / "smoke.yml").read_text())
    arm, runs = args.arm or cfg["arm"], args.runs or cfg["runs"]
    smoke_ids = cfg["smoke"]
    if args.repo:
        from harness.tasklint import load_tasks
        smoke_ids = [t["id"] for t in load_tasks(harness_dir() / "tasks") if t["id"] in smoke_ids and t["repo"] == args.repo]
        if not smoke_ids:
            print(f"no smoke tasks for repo {args.repo}"); return 2
    tmp_results = Path(args.out).parent / ".regress-results"
    tmp_results.mkdir(parents=True, exist_ok=True)
    ns = SimpleNamespace(tasks=None, repos=args.repos, tier=None, task=smoke_ids, repo=None, arms=arm, runs=runs,
                         results=str(tmp_results), out="regress.jsonl", dry_run=args.dry_run, timeout=900, model=None, judge_model=None)
    (tmp_results / "regress.jsonl").unlink(missing_ok=True)
    rc = run_eval(ns)
    if rc:
        return rc
    recs = [json.loads(l) for l in (tmp_results / "regress.jsonl").read_text().splitlines() if l.strip()]
    pilot = None
    pr = Path(args.pilot_results)
    if pr.exists():
        from harness.scorecard import load_records, summarise
        base = [r for r in load_records(pr) if r.get("arm") == arm]
        if base:
            s = summarise(base)
            pilot = {"prompt_tokens_p50": s["prompt_tokens"]["p50"], "input_tokens_p50": s["input_tokens"]["p50"], "model_calls_p50": s["model_calls"]["p50"],
                     "wall_ms_p50": s["wall_ms"]["p50"], "correctness": s["correctness"]}
    row = trend_row(recs, arm, pilot)
    row["dry_run"] = bool(args.dry_run)
    if args.repo:
        row["repo"] = args.repo
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a") as fh:
        fh.write(json.dumps(row) + "\n")
    print(f"regress: {row['runs']} runs on {arm} → {out} (prompt tokens p50 {row['prompt_tokens_p50']}, correctness {row['correctness']})")
    return 0
