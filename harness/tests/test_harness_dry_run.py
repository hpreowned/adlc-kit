import json
import subprocess
from pathlib import Path

import pytest

from harness import judge as J
from harness.runner import RunSpec, StubDriver, execute, final_answer, result_event
from harness.scrub import scrub_text, scrub_jsonl

FIX = Path(__file__).parent / "fixtures" / "events_smoke.jsonl"
TASK = {"id": "t-001", "repo": "repo", "category": "trace", "languages": ["python"], "tier": 1, "judge": "rubric",
        "prompt": "who calls x?", "expected": "y", "rubric": "2 if y", "cwd": "."}
EDIT = {**TASK, "id": "t-002", "category": "edit", "judge": "tests", "test_command": "test -f README.md"}


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    for a in (["init", "-q", "-b", "main"], ["config", "user.email", "t@e"], ["config", "user.name", "t"]):
        subprocess.run(["git", "-C", str(r), *a], check=True)
    (r / "README.md").write_text("hi\n")
    (r / "graphify-out").mkdir()
    (r / "graphify-out" / "graph.json").write_text(json.dumps({"graph": {}, "nodes": [], "links": []}))
    subprocess.run(["git", "-C", str(r), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(r), "commit", "-q", "-m", "init"], check=True)
    sha = subprocess.run(["git", "-C", str(r), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    (r / "graphify-out" / "adlc-stamp.json").write_text(json.dumps({"commit_sha": sha}))
    subprocess.run(["git", "-C", str(r), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(r), "commit", "-q", "-m", "stamp"], check=True)
    return r


def _sha(r):
    return subprocess.run(["git", "-C", str(r), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


def test_dry_run_produces_full_record(repo, tmp_path):
    spec = RunSpec(task=TASK, arm="baseline", run=1, repo_dir=repo, baseline_sha=_sha(repo), results_dir=tmp_path / "results")
    res = execute(spec, StubDriver(FIX, answer="y is called by z"))
    rec = res.record
    assert rec["run_id"] == "t-001__baseline__r1" and rec["arm"] == "baseline"
    assert rec["input_tokens"] > 0 and rec["model_calls"] == 2 and rec["premium_requests"] is not None
    assert rec["answer"] == "y is called by z" and rec["freshness_exit"] == 0
    assert (res.raw_dir / "events.jsonl").exists() and (res.raw_dir / "stdout.jsonl").exists()
    assert "gho_" not in (res.raw_dir / "events.jsonl").read_text()
    rec = J.judge_record(rec, TASK, J.StubJudge(1))
    assert rec["judge_score"] == 1


def test_guard_arm_installs_hook_only_in_working_copy(repo, tmp_path):
    spec = RunSpec(task=TASK, arm="graphify-guard", run=1, repo_dir=repo, baseline_sha=_sha(repo), results_dir=tmp_path / "results")
    execute(spec, StubDriver(FIX))
    assert not (repo / ".github" / "hooks").exists()  # pristine repo untouched


def test_edit_task_is_judged_by_tests(repo, tmp_path):
    spec = RunSpec(task=EDIT, arm="serena", run=2, repo_dir=repo, baseline_sha=_sha(repo), results_dir=tmp_path / "results")
    rec = J.judge_record(execute(spec, StubDriver(FIX)).record, EDIT, J.StubJudge(0))
    assert rec["tests_passed"] is True and rec["judge_score"] == 2 and rec["judge_reason"] == "tests"


def test_parse_score_variants():
    assert J.parse_score('{"score": 2, "reason": "ok"}') == (2, "ok")
    assert J.parse_score("Score: 1")[0] == 1
    assert J.parse_score("no idea")[0] is None


def test_scrub():
    assert scrub_text("token gho_abcdefghijklmnopqrstuvwxyz0123 and api_key=ABCDEFGHIJKLMNOP1234") == "token <redacted> and api_key=<redacted>"
    out = scrub_jsonl('{"type":"system.message","data":{"content":"secret prompt","requestId":"x"}}\n')
    assert "scrubbed system prompt" in out and "requestId" not in out


def test_stdout_helpers():
    s = '{"type":"assistant.message","data":{"content":"a"}}\n{"type":"assistant.message","data":{"content":"b"}}\n{"type":"result","usage":{"premiumRequests":3}}\n'
    assert final_answer(s) == "b" and result_event(s)["usage"]["premiumRequests"] == 3


def test_spotcheck_hides_arm():
    recs = [{"run_id": "t-001__graphify__r1", "task": "t-001", "judge_score": 2, "answer": "y", "arm": "graphify"}]
    md = J.spotcheck_md(recs, {"t-001": TASK}, fraction=1.0)
    assert "graphify" not in md.split("## ")[1].split("(ref")[0] and "human: ___" in md


ROUTING = """# AGENTS.md

prose

<!-- adlc:routing:start -->
## Context routing
- **Graph** (`/graphify query`): structural
  questions continue here.
- **grep / file read**: literals.
- **Serena (LSP)**: symbol edits.
- Before trusting the graph run `adlc stale`.
- Levels: project and org.
<!-- adlc:routing:end -->

```yaml
adlc:
  schema: 1
```
"""


def test_filter_routing_modes():
    from harness.runner import filter_routing
    none = filter_routing(ROUTING, "none")
    assert "Context routing" not in none and "prose" in none and "schema: 1" in none
    lsp = filter_routing(ROUTING, "lsp")
    assert "Serena" in lsp and "Graph" not in lsp and "continue here" not in lsp
    graph = filter_routing(ROUTING, "graph")
    assert "Graph" in graph and "continue here" in graph and "Serena" not in graph and "adlc stale" in graph


def test_arm_strip_removes_other_context(repo, tmp_path):
    (repo / ".mcp.json").write_text("{}"); (repo / ".github" / "skills" / "graphify").mkdir(parents=True)
    (repo / ".github" / "skills" / "graphify" / "SKILL.md").write_text("x"); (repo / "AGENTS.md").write_text(ROUTING)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True); subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "ctx"], check=True)
    from harness.runner import prepare_working_copy
    for arm, gone, kept in (("baseline", ["graphify-out", ".mcp.json", ".github/skills/graphify"], []),
                            ("serena", ["graphify-out", ".github/skills/graphify"], [".mcp.json"]),
                            ("graphify", [".mcp.json"], ["graphify-out", ".github/skills/graphify"])):
        spec = RunSpec(task=TASK, arm=arm, run=1, repo_dir=repo, baseline_sha=_sha(repo), results_dir=tmp_path / "r")
        wc = prepare_working_copy(spec, tmp_path / f"run-{arm}")
        assert all(not (wc / g).exists() for g in gone), arm
        assert all((wc / k).exists() for k in kept), arm
