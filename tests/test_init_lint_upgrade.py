import json
import subprocess

from adlc import contract as C
from adlc import doctor, init, lint, upgrade
from tests.conftest import commit, git


def _init(repo, context=("graphify", "serena"), skill_profile="lean"):
    (repo / "pyproject.toml").write_text("[project]\nname='x'\nversion='0'\n")
    (repo / "AGENTS.md").unlink()
    return init.run_init(repo, list(context), skill_profile=skill_profile)


def test_init_creates_contract_files(repo):
    rep = _init(repo)
    created = {p for s, p in rep.rows if s == "created"}
    for rel in ("AGENTS.md", ".mcp.json", ".serena/adlc-context.yml", ".serena/project.yml",
                ".github/skills/graphify/SKILL.md", ".github/workflows/adlc.yml",
                "renovate.json", ".graphifyrc", ".gitignore"):
        assert any(p.endswith(rel) for p in created), rel
    c = C.load(repo)
    assert c.schema == 1 and c.context == ["graphify", "serena"]
    skill = (repo / ".github/skills/graphify/SKILL.md").read_text()
    assert skill.startswith("---\nname: graphify\n") and "ADLC freshness check" in skill and "# /graphify" in skill
    assert len(skill) < 4096 and not (repo / ".github/skills/graphify/references").exists()  # lean is the default
    ctx = (repo / ".serena/adlc-context.yml").read_text()
    assert "- serena_repl" in ctx and "find_symbol" not in ctx.split("excluded_tools:")[1]


def test_init_writes_no_container_and_doctor_never_asks(repo, monkeypatch):
    _init(repo)
    assert not (repo / ".devcontainer").exists()
    monkeypatch.setenv("GRAPHIFY_BACKEND", "none")
    assert not any("devcontainer" in c.name for c in doctor.run_checks(repo))
    errors, _ = lint.lint(repo)
    assert errors == []


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


def test_lean_skill_profile_replaces_vendor_skill(repo, tmp_path):
    _init(repo, skill_profile="vendor")  # vendor first: SKILL.md + references/
    assert (repo / ".github/skills/graphify/references").exists()
    assert "## Usage" in (repo / ".github/skills/graphify/SKILL.md").read_text()
    rep = init.run_init(repo, ["graphify", "serena"], skill_profile="lean")
    skill = repo / ".github/skills/graphify/SKILL.md"
    assert skill.stat().st_size < 4096 and skill.read_text().startswith("---\nname: graphify\n")
    assert "adlc stale" in skill.read_text() and "graphify query" in skill.read_text()
    assert not (repo / ".github/skills/graphify/references").exists()
    assert any(s == "removed" for s, _ in rep.rows)
    errors, _ = lint.lint(repo)
    assert errors == []
    # the arm swaps the skill in a working copy without touching the source repo
    from harness.runner import RunSpec, arm_config, prepare_working_copy
    init.run_init(repo, ["graphify", "serena"], skill_profile="vendor")  # back to vendor
    git(repo, "add", "-A"); git(repo, "commit", "-q", "-m", "vendor skill")
    assert arm_config("graphify-lean")["skill_profile"] == "lean"
    spec = RunSpec(task={"id": "t"}, arm="graphify-lean", run=1, repo_dir=repo,
                   baseline_sha=git(repo, "rev-parse", "HEAD"), results_dir=tmp_path / "res")
    wc = prepare_working_copy(spec, tmp_path / "run")
    assert (wc / ".github/skills/graphify/SKILL.md").stat().st_size < 4096
    assert not (wc / ".github/skills/graphify/references").exists()
    assert (repo / ".github/skills/graphify/references").exists()
    # and the vendor arm restores the shipped skill even when the repo has committed lean
    init.run_init(repo, ["graphify", "serena"])  # default = lean
    git(repo, "add", "-A"); git(repo, "commit", "-q", "-m", "lean skill")
    spec = RunSpec(task={"id": "t"}, arm="graphify", run=1, repo_dir=repo,
                   baseline_sha=git(repo, "rev-parse", "HEAD"), results_dir=tmp_path / "res2")
    wc2 = prepare_working_copy(spec, tmp_path / "run2")
    assert (wc2 / ".github/skills/graphify/references").exists()
    assert "## Usage" in (wc2 / ".github/skills/graphify/SKILL.md").read_text()


def test_polyglot_repo_gets_service_level_mcp_json(repo, monkeypatch):
    """Copilot CLI loads .mcp.json from the cwd only; a task run inside gateway/ must still see Serena."""
    (repo / "gateway").mkdir(); (repo / "gateway" / "pyproject.toml").write_text("[project]\nname='g'\nversion='0'\n")
    (repo / "gateway" / "app.py").write_text("x = 1\n")
    (repo / "AGENTS.md").unlink()
    init.run_init(repo, ["graphify", "serena"])
    root = json.loads((repo / ".mcp.json").read_text())["mcpServers"]["serena"]["args"]
    svc = json.loads((repo / "gateway" / ".mcp.json").read_text())["mcpServers"]["serena"]["args"]
    assert "--project-from-cwd" in root and ".serena/adlc-context.yml" in root
    assert "--project-from-cwd" in svc and ".serena/adlc-context.yml" in svc  # service = its own Serena project
    import yaml
    sp = yaml.safe_load((repo / "gateway" / ".serena" / "project.yml").read_text())
    assert sp["project_name"] == f"{repo.name}-gateway" and sp["language_servers"] == ["python"]
    assert (repo / "gateway" / ".serena" / "adlc-context.yml").exists()
    errors, _ = lint.lint(repo)
    assert errors == []
    (repo / "gateway" / ".mcp.json").unlink()
    errors, _ = lint.lint(repo)
    assert any("gateway/.mcp.json missing" in e for e in errors)
    monkeypatch.setenv("GRAPHIFY_BACKEND", "none")
    pin = next(c for c in doctor.run_checks(repo) if c.name.startswith(".mcp.json serena pin"))
    assert not pin.ok and "gateway/.mcp.json" in pin.detail
