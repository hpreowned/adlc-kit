"""Stub runner for the reusable workflows: `act` needs Docker, which the pilot machine
does not have, so we execute each workflow's `run:` steps that call `adlc` directly
against fixture repos and assert the exit codes the workflow relies on."""
import re
import subprocess
import sys
from pathlib import Path

import yaml

WF = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def _adlc_steps(name: str) -> list[str]:
    wf = yaml.safe_load((WF / name).read_text())
    steps = []
    for job in wf["jobs"].values():
        for st in job["steps"]:
            run = st.get("run", "")
            if isinstance(run, str) and run.strip().startswith("adlc "):
                steps.append(run.strip().split("\n")[0])
    return steps


def _run(step: str, cwd: Path) -> int:
    cmd = step.replace("${{ inputs.level }}", "repo").split()
    cmd[0] = str(Path(sys.executable).parent / "adlc")
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True).returncode


def test_all_workflows_parse_and_are_workflow_call():
    for p in WF.glob("adlc-*.yml"):
        wf = yaml.safe_load(p.read_text())
        assert "workflow_call" in (wf.get("on") or wf.get(True) or {}), p.name


def test_contract_lint_fails_repo_missing_block(repo):
    (repo / "AGENTS.md").write_text("# no block here\n")
    steps = _adlc_steps("adlc-contract-lint.yml")
    assert steps == ["adlc lint"]
    assert _run(steps[0], repo) == 1


def test_contract_lint_fails_malformed_block(repo):
    text = (repo / "AGENTS.md").read_text().replace("  context: [graphify, serena]\n", "  context: [sourcegraph]\n")
    (repo / "AGENTS.md").write_text(text)
    assert _run("adlc lint", repo) == 1


def test_contract_lint_passes_initialised_repo(repo):
    from adlc.init import run_init
    (repo / "pyproject.toml").write_text("[project]\nname='x'\nversion='0'\n")
    run_init(repo, ["graphify", "serena"])
    agents = repo / "AGENTS.md"
    agents.write_text(re.sub(r"`TODO`|TODO", "n/a", agents.read_text()))
    assert _run("adlc lint", repo) == 0


def test_drift_step_exit_code_matches_stale(repo):
    steps = _adlc_steps("adlc-drift.yml")
    assert any(s.startswith("adlc stale") for s in steps)
    assert _run("adlc stale --all", repo) == 2  # nothing built yet → stale
