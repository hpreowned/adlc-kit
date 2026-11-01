import json

from adlc import force_hook
from harness.runner import RunSpec, arm_config, prepare_working_copy
from tests.conftest import git


def test_force_hook_denies_text_search_only():
    deny = {"permissionDecision": "deny"}
    for ev in ({"toolName": "rg", "toolArgs": {"pattern": "x"}}, {"toolName": "grep_search"},
               {"toolName": "search_code_subagent"},
               {"toolName": "bash", "toolArgs": {"command": "rg -n foo src"}},
               {"toolName": "bash", "toolArgs": {"command": "cat a | grep foo"}},
               {"toolName": "shell", "toolArgs": {"command": "git grep -n foo"}}):
        d = force_hook.decide(ev)
        assert d["permissionDecision"] == "deny" and "find_symbol" in d["permissionDecisionReason"], ev
    for ev in ({"toolName": "view", "toolArgs": {"path": "a.py"}}, {"toolName": "glob"}, {"toolName": "file_search"},
               {"toolName": "serena-find_symbol"}, {"toolName": "bash", "toolArgs": {"command": "pytest -q"}},
               {"toolName": "bash", "toolArgs": {"command": "ls -la && cat regress.py"}}, {}):
        assert force_hook.decide(ev) == {"permissionDecision": "allow"}, ev


def test_serena_forced_arm_writes_hook_and_routing(repo, tmp_path):
    from adlc import init
    (repo / "pyproject.toml").write_text("[project]\nname='x'\nversion='0'\n")
    (repo / "AGENTS.md").unlink()
    init.run_init(repo, ["graphify", "serena"])
    git(repo, "add", "-A"); git(repo, "commit", "-q", "-m", "init")
    cfg = arm_config("serena-forced")
    assert cfg["force_hook"] and "rg" in cfg["deny_tools"]
    spec = RunSpec(task={"id": "t"}, arm="serena-forced", run=1, repo_dir=repo,
                   baseline_sha=git(repo, "rev-parse", "HEAD"), results_dir=tmp_path / "res")
    wc = prepare_working_copy(spec, tmp_path / "run")
    hook = json.loads((wc / ".github/hooks/adlc-force.json").read_text())
    assert hook["hooks"]["preToolUse"][0]["bash"] == "adlc force-hook"
    agents = (wc / "AGENTS.md").read_text()
    assert "<!-- adlc:routing:start -->" in agents and "find_referencing_symbols" in agents and "**Graph**" not in agents
    assert not (wc / "graphify-out").exists() and not (wc / ".github/skills/graphify").exists()
    assert (wc / ".mcp.json").exists()
    assert "find_referencing_symbols" not in (repo / "AGENTS.md").read_text()  # source untouched
