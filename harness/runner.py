"""One (task, arm, run): fresh working copy at the baseline commit → COPILOT_HOME from the
arm template → `copilot -p … --output-format json` → events.jsonl + stdout → one result
record. The `Driver` is swappable: `CopilotDriver` (real) or `StubDriver` (dry runs)."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from harness.events import RunMetrics, find_events_file, parse_file
from harness.scrub import scrub_jsonl, scrub_text

ARMS_DIR = Path(__file__).parent / "arms"
SAFE_ENV = ("PATH", "HOME", "USER", "SHELL", "TERM", "LANG", "LC_ALL", "TMPDIR", "JAVA_HOME", "DOTNET_ROOT",
            "DOTNET_CLI_TELEMETRY_OPTOUT", "DOTNET_NOLOGO", "NVM_DIR", "COPILOT_GITHUB_TOKEN")


@dataclass
class RunSpec:
    task: dict
    arm: str
    run: int
    repo_dir: Path          # pristine checkout of the consuming repo
    baseline_sha: str
    results_dir: Path
    project_graph: Path | None = None
    timeout: int = 900
    model: str | None = None
    tasks_root: Path | None = None


@dataclass
class RunResult:
    record: dict
    raw_dir: Path


def arm_config(arm: str) -> dict:
    return json.loads((ARMS_DIR / arm / "arm.json").read_text())


def child_env(copilot_home: Path, run_dir: Path) -> dict:
    env = {k: os.environ[k] for k in SAFE_ENV if k in os.environ}
    env.update({"COPILOT_HOME": str(copilot_home), "GRAPHIFY_BACKEND": "none", "GRAPHIFY_NO_TIPS": "1",
                "GRAPHIFY_QUERY_LOG": str(run_dir / "queries.log"), "PATH": str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")})
    return env


def prepare_working_copy(spec: RunSpec, run_dir: Path) -> Path:
    wc = run_dir / "wc"
    subprocess.run(["git", "clone", "-q", "--no-hardlinks", str(spec.repo_dir), str(wc)], check=True)
    subprocess.run(["git", "-C", str(wc), "checkout", "-q", spec.baseline_sha], check=True)
    cfg = arm_config(spec.arm)
    apply_strip(wc, cfg.get("strip") or {})
    if cfg.get("skill_profile") == "lean":
        from adlc.init import Report, write_lean_skill
        write_lean_skill(wc, Report())
    if cfg.get("guard"):
        from adlc.guard_hook import hook_json
        hooks = wc / ".github" / "hooks"
        hooks.mkdir(parents=True, exist_ok=True)
        (hooks / "adlc-guard.json").write_text(json.dumps(hook_json(strict=False), indent=2))
    if cfg.get("federated") and spec.project_graph and spec.project_graph.exists():
        (wc / "graphify-out").mkdir(exist_ok=True)
        shutil.copy(spec.project_graph, wc / "graphify-out" / "project-graph.json")
    return wc


ROUTING_KEEP = {"none": (), "lsp": ("Serena",), "graph": ("Graph", "grep", "adlc stale", "Levels"), "all": ("Graph", "grep", "Serena", "adlc stale", "Levels")}


def filter_routing(text: str, mode: str) -> str:
    """Arm purity: the kit-owned CONTEXT ROUTING section only advertises the tools the
    arm actually has. `none` removes the section (baseline = AGENTS.md prose only)."""
    start, end = "<!-- adlc:routing:start -->", "<!-- adlc:routing:end -->"
    if start not in text or end not in text:
        return text
    a, b = text.index(start), text.index(end) + len(end)
    if mode == "none":
        return text[:a].rstrip() + "\n\n" + text[b:].lstrip()
    keep = ROUTING_KEEP.get(mode, ())
    out, skipping = [], False
    for line in text[a:b].splitlines():
        if line.startswith("- **") or line.startswith("- Before") or line.startswith("- Levels"):
            skipping = not any(k in line for k in keep)
        elif not line.startswith("  "):
            skipping = False
        if not skipping:
            out.append(line)
    return text[:a] + "\n".join(out) + text[b:]


def apply_strip(wc: Path, strip: dict) -> None:
    for rel in strip.get("paths", []):
        target = wc / rel
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
    mode = strip.get("routing", "all")
    for agents in [wc / "AGENTS.md", *wc.glob("*/AGENTS.md")]:
        if agents.exists():
            agents.write_text(filter_routing(agents.read_text(), mode))


def prepare_home(spec: RunSpec, run_dir: Path) -> Path:
    home = run_dir / "home"
    shutil.copytree(ARMS_DIR / spec.arm / "home", home, dirs_exist_ok=True)
    return home


def copilot_args(spec: RunSpec, cfg: dict) -> list[str]:
    args = ["copilot", "-p", spec.task["prompt"], "--allow-all-tools", "--no-ask-user", "--trust-folder", "--output-format", "json"]
    args += cfg.get("copilot_flags", [])
    for d in cfg.get("deny_tools", []) + spec.task.get("deny_tools", []):
        args += ["--deny-tool", d]
    model = spec.model or os.environ.get("ADLC_COPILOT_MODEL")
    if model:
        args += ["--model", model]
    return args


class CopilotDriver:
    def run(self, args: list[str], cwd: Path, env: dict, timeout: int) -> tuple[int, str, str]:
        r = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr


class StubDriver:
    """Dry runs: copies a fixture events.jsonl into the fake COPILOT_HOME and returns a
    plausible stdout result line. Lets the whole pipeline be tested without spend."""
    def __init__(self, fixture: Path, answer: str = "stub answer"):
        self.fixture, self.answer = fixture, answer

    def run(self, args, cwd, env, timeout):
        home = Path(env["COPILOT_HOME"])
        sess = home / "session-state" / "stub-session"
        sess.mkdir(parents=True, exist_ok=True)
        shutil.copy(self.fixture, sess / "events.jsonl")
        stdout = json.dumps({"type": "assistant.message", "data": {"content": self.answer}}) + "\n" + json.dumps(
            {"type": "result", "sessionId": "stub-session", "exitCode": 0,
             "usage": {"premiumRequests": 1, "totalApiDurationMs": 1200, "sessionDurationMs": 2000, "codeChanges": {"linesAdded": 0, "linesRemoved": 0, "filesModified": []}}})
        return 0, stdout, ""


def final_answer(stdout: str) -> str:
    ans = ""
    for line in stdout.splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "assistant.message" and (ev.get("data") or {}).get("content"):
            ans = ev["data"]["content"]
    return ans


def result_event(stdout: str) -> dict:
    for line in reversed(stdout.splitlines()):
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "result":
            return ev
    return {}


def run_setup(wc: Path, task: dict, env: dict) -> dict:
    """Environment preparation that is NOT part of the measurement (venv, npm ci)."""
    cmd = task.get("setup_command")
    if not cmd:
        return {}
    r = subprocess.run(cmd, shell=True, cwd=wc / task.get("cwd", "."), env=env, capture_output=True, text=True, timeout=900)
    return {"setup_ok": r.returncode == 0}


def apply_overlay(wc: Path, task: dict, tasks_root: Path | None) -> int:
    """Edit tasks: copy the task's overlay tests into the working copy AFTER the agent
    ran, so the tests can tell 'fixed' from 'did nothing' (they fail on the pristine repo)."""
    rel = task.get("overlay")
    if not rel or tasks_root is None:
        return 0
    src = tasks_root / rel
    n = 0
    for f in src.rglob("*"):
        if f.is_file():
            dest = wc / task.get("cwd", ".") / f.relative_to(src)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(f, dest)
            n += 1
    return n


def diff_and_tests(wc: Path, task: dict, env: dict, tasks_root: Path | None = None) -> dict:
    diff = subprocess.run(["git", "-C", str(wc), "diff", "--", ".", ":(exclude).github/hooks", ":(exclude)graphify-out"],
                          capture_output=True, text=True).stdout
    out = {"diff_hash": hashlib.sha256(diff.encode()).hexdigest()[:16] if diff.strip() else None, "diff_lines": diff.count("\n")}
    if task.get("judge") == "tests" and task.get("test_command"):
        out["overlay_files"] = apply_overlay(wc, task, tasks_root)
        cwd = wc / task.get("cwd", ".")
        try:
            r = subprocess.run(task["test_command"], shell=True, cwd=cwd, env=env, capture_output=True, text=True, timeout=900)
            out["tests_passed"] = r.returncode == 0
            (wc.parent / "tests.log").write_text(scrub_text(r.stdout[-20000:] + r.stderr[-20000:]))
        except subprocess.TimeoutExpired:
            out["tests_passed"] = False
    return out


def execute(spec: RunSpec, driver=None) -> RunResult:
    driver = driver or CopilotDriver()
    cfg = arm_config(spec.arm)
    run_id = f"{spec.task['id']}__{spec.arm}__r{spec.run}"
    run_dir = Path(tempfile.mkdtemp(prefix=f"adlc-{run_id}-"))
    raw_dir = spec.results_dir / "runs" / run_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    wc = prepare_working_copy(spec, run_dir)
    home = prepare_home(spec, run_dir)
    env = child_env(home, run_dir)
    from adlc.stale import check as stale_check
    freshness = stale_check(spec.repo_dir, "graphify-out/graph.json")  # pristine repo, before arm stripping
    setup = run_setup(wc, spec.task, env)
    cwd = wc / spec.task.get("cwd", ".")
    t0 = time.time()
    rc, stdout, stderr = driver.run(copilot_args(spec, cfg), cwd, env, spec.timeout)
    wall_ms = int((time.time() - t0) * 1000)
    ev_path = find_events_file(home)
    metrics: RunMetrics = parse_file(ev_path) if ev_path else RunMetrics()
    res = result_event(stdout)
    roots = [str(run_dir), str(wc), str(home)]
    (raw_dir / "stdout.jsonl").write_text(scrub_jsonl(stdout, roots))
    (raw_dir / "stderr.txt").write_text(scrub_text(stderr[-20000:], roots))
    if ev_path:
        (raw_dir / "events.jsonl").write_text(scrub_jsonl(ev_path.read_text(), roots))
    ql = run_dir / "queries.log"
    if ql.exists():
        (raw_dir / "queries.log").write_text(scrub_text(ql.read_text(), roots))
    edit = diff_and_tests(wc, spec.task, env, spec.tasks_root)
    edit.update(setup)
    record = {
        "run_id": run_id, "task": spec.task["id"], "repo": spec.task["repo"], "category": spec.task["category"],
        "languages": spec.task["languages"], "tier": spec.task["tier"], "arm": spec.arm, "run": spec.run,
        "started_at": datetime.fromtimestamp(t0, timezone.utc).isoformat(timespec="seconds"),
        "exit_code": rc, "wall_ms": wall_ms, "api_duration_ms": metrics.api_duration_ms,
        "prompt_tokens": metrics.input_tokens + metrics.cache_read_tokens + metrics.cache_write_tokens,
        "input_tokens": metrics.input_tokens, "output_tokens": metrics.output_tokens,
        "cache_read_tokens": metrics.cache_read_tokens, "cache_write_tokens": metrics.cache_write_tokens,
        "reasoning_tokens": metrics.reasoning_tokens,
        "premium_requests": metrics.premium_requests, "premium_requests_stdout": (res.get("usage") or {}).get("premiumRequests"),
        "premium_reason": None if metrics.premium_requests is not None else "no session.shutdown in events.jsonl",
        "model_calls": metrics.model_calls, "premium_cost_sum": metrics.premium_cost_sum, "nano_aiu": metrics.nano_aiu,
        "models": metrics.models, "copilot_version": metrics.copilot_version, "turns": metrics.turns,
        "tool_calls": metrics.tool_calls, "mcp_tool_calls": metrics.mcp_tool_calls, "bytes_read": metrics.bytes_read,
        "skills_invoked": metrics.skills_invoked, "graph_queries": _count_lines(ql),
        "session_error": metrics.session_error, "valid": metrics.session_error is None and rc == 0,
        "freshness_exit": freshness.exit_code, "freshness_behind": freshness.behind,
        "answer": scrub_text(final_answer(stdout), roots)[:6000], "judge_score": None,
        **edit, "raw": str(raw_dir.relative_to(spec.results_dir)),
    }
    (raw_dir / "record.json").write_text(json.dumps(record, indent=2))
    shutil.rmtree(run_dir, ignore_errors=True)
    return RunResult(record, raw_dir)


def _count_lines(p: Path) -> int:
    return sum(1 for _ in p.open()) if p.exists() else 0
