import json
import subprocess

from adlc import contract as C
from adlc import doctor, init, lint, upgrade
from tests.conftest import commit, git


def _init(repo, context=("graphify", "serena")):
    (repo / "pyproject.toml").write_text("[project]\nname='x'\nversion='0'\n")
    (repo / "AGENTS.md").unlink()
    return init.run_init(repo, list(context))


def test_init_creates_contract_files(repo):
    rep = _init(repo)
    created = {p for s, p in rep.rows if s == "created"}
    for rel in ("AGENTS.md", ".mcp.json", ".serena/adlc-context.yml", ".serena/project.yml",
                ".github/skills/graphify/SKILL.md", ".github/workflows/adlc.yml", ".devcontainer/devcontainer.json",
                "renovate.json", ".graphifyrc", ".gitignore"):
        assert any(p.endswith(rel) for p in created), rel
    c = C.load(repo)
    assert c.schema == 1 and c.context == ["graphify", "serena"]
    skill = (repo / ".github/skills/graphify/SKILL.md").read_text()
    assert skill.startswith("---") and "ADLC freshness check" in skill and "# /graphify" in skill
    ctx = (repo / ".serena/adlc-context.yml").read_text()
    assert "- serena_repl" in ctx and "find_symbol" not in ctx.split("excluded_tools:")[1]


def test_init_is_idempotent_and_keeps_prose(repo):
    _init(repo)
    agents = repo / "AGENTS.md"
    agents.write_text(agents.read_text().replace("- Build: `TODO`", "- Build: `make`"))
    (repo / ".serena/project.yml").write_text('project_name: "custom"\nlanguage_servers: ["python", "go"]\n')
    rep = init.run_init(repo, ["graphify", "serena"])
    statuses = {p.split("/")[-1]: s for s, p in rep.rows}
    assert "- Build: `make`" in agents.read_text()
    assert statuses["project.yml"].startswith("kept")
    assert all(s in ("unchanged", "updated", "kept (team-owned)") for s, _ in rep.rows)
    assert agents.read_text().count("adlc:routing:start") == 1


def test_lint_fails_on_missing_path_and_copilot_instructions(repo):
    _init(repo)
    agents = repo / "AGENTS.md"
    agents.write_text(agents.read_text().replace("- Build: `TODO`", "- Build: see `scripts/build.sh`"))
    fails, _ = lint.lint(repo)
    assert any("scripts/build.sh" in f for f in fails)
    (repo / "scripts").mkdir()
    (repo / "scripts/build.sh").write_text("")
    (repo / ".github/copilot-instructions.md").write_text("x")
    fails, _ = lint.lint(repo)
    assert any("single source" in f for f in fails) and not any("build.sh" in f for f in fails)


def test_lint_fails_on_pin_drift(repo):
    _init(repo)
    mcp = repo / ".mcp.json"
    data = json.loads(mcp.read_text())
    data["mcpServers"]["serena"]["args"] = [a.replace("@ede329", "@000000") for a in data["mcpServers"]["serena"]["args"]]
    mcp.write_text(json.dumps(data))
    fails, _ = lint.lint(repo)
    assert any("pin" in f for f in fails)


def test_lint_rejects_malformed_block(repo):
    _init(repo)
    agents = repo / "AGENTS.md"
    agents.write_text(agents.read_text().replace("  freshness: two-tier\n", ""))
    fails, _ = lint.lint(repo)
    assert fails and "missing keys: freshness" in fails[0]


def test_upgrade_1_to_2_adds_owner_from_codeowners(repo):
    _init(repo)
    (repo / "CODEOWNERS").write_text("* @kestrel/platform-team\n")
    c = upgrade.upgrade(repo, 2)
    assert c.schema == 2 and c.extra["owner"] == "@kestrel/platform-team"
    reread = C.load(repo)
    assert reread.schema == 2 and reread.extra["owner"] == "@kestrel/platform-team"
    fails, _ = lint.lint(repo)
    assert not [f for f in fails if "schema" in f]


def test_doctor_runs_and_reports(repo, monkeypatch):
    _init(repo)
    monkeypatch.delenv("COPILOT_GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("GRAPHIFY_BACKEND", "none")
    checks = doctor.run_checks(repo)
    names = {c.name for c in checks}
    assert "env COPILOT_GITHUB_TOKEN" in names and "artifact freshness" in names
    tok = next(c for c in checks if c.name == "env COPILOT_GITHUB_TOKEN")
    assert not tok.ok and tok.warn


def test_lint_rejects_hosted_or_unknown_mcp(repo):
    _init(repo)
    mcp = repo / ".mcp.json"
    data = json.loads(mcp.read_text())
    data["mcpServers"]["cloud"] = {"type": "http", "url": "https://app.graphify.com/mcp"}
    mcp.write_text(json.dumps(data))
    fails, _ = lint.lint(repo)
    assert any("hosted MCP" in f for f in fails) and any("Graphify Cloud" in f for f in fails)
    assert any("CLI_FIRST" in f for f in fails)


def test_sensitive_edit_without_ticket_warns(repo):
    _init(repo)
    (repo / "migrations").mkdir()
    git(repo, "add", "-A"); git(repo, "commit", "-q", "-m", "init contract")
    git(repo, "branch", "-f", "origin/main")
    (repo / "migrations" / "001.sql").write_text("create table t(x int);")
    git(repo, "add", "-A"); git(repo, "commit", "-q", "-m", "add table")
    c = C.load(repo); c.sensitive = ["migrations/"]
    warns = lint.sensitive_edit_warnings(repo, c, base="origin/main")
    assert warns and "without a ticket id" in warns[0]
    (repo / "migrations" / "002.sql").write_text("x")
    git(repo, "add", "-A"); git(repo, "commit", "-q", "-m", "BOOK-377: add fk")
    assert len(lint.sensitive_edit_warnings(repo, c, base="origin/main")) == 1
