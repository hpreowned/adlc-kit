"""`adlc init`: make a repo contract-compliant. Idempotent and re-runnable; kit-owned
files are rewritten, team-owned prose (AGENTS.md body, .serena/project.yml) is kept."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from adlc import SCHEMA_VERSION, __version__
from adlc import contract as C
from adlc.paths import template_dir
from adlc.pins import load_pins
from adlc.render import SERENA_LS, detect_services, is_docs_only, render, repo_languages

ROUTING_START, ROUTING_END = "<!-- adlc:routing:start -->", "<!-- adlc:routing:end -->"
GI_START, GI_END = "# --- adlc (kit-owned) ---", "# --- end adlc ---"
ALL_SERENA_TOOLS = [
    "activate_project", "create_text_file", "delete_lines", "delete_memory", "edit_memory", "execute_shell_command",
    "find_declaration", "find_file", "find_implementations", "find_referencing_symbols", "find_symbol",
    "get_current_config", "get_diagnostics_for_file", "get_diagnostics_for_symbol", "get_symbols_overview",
    "initial_instructions", "insert_after_symbol", "insert_at_line", "insert_before_symbol", "list_dir",
    "list_memories", "list_queryable_projects", "onboarding", "open_dashboard", "query_project", "read_file",
    "read_memory", "remove_project", "rename_memory", "rename_symbol", "replace_content", "replace_in_files",
    "replace_lines", "replace_symbol_body", "restart_language_server", "safe_delete_symbol", "search_for_pattern",
    "serena_info", "serena_repl", "write_memory",
]


class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str]] = []

    def write(self, path: Path, content: str, owned: bool = True) -> None:
        if path.exists() and path.read_text() == content:
            self.rows.append(("unchanged", str(path)))
            return
        if path.exists() and not owned:
            self.rows.append(("kept (team-owned)", str(path)))
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        self.rows.append(("updated" if path.exists() else "created", str(path)))
        path.write_text(content)


def _tmpl(name: str) -> str:
    return (template_dir() / name).read_text()


def routing_section() -> str:
    return f"{ROUTING_START}\n{_tmpl('ROUTING.md').rstrip()}\n{ROUTING_END}"


def upsert_routing(text: str) -> str:
    sec = routing_section()
    if ROUTING_START in text and ROUTING_END in text:
        a, b = text.index(ROUTING_START), text.index(ROUTING_END) + len(ROUTING_END)
        return text[:a] + sec + text[b:]
    found = C.find_block(text)
    if found:
        _, start, _ = found
        return text[:start].rstrip() + "\n\n" + sec + "\n\n" + text[start:]
    return text.rstrip() + "\n\n" + sec + "\n"


def default_contract(repo: Path, context: list[str]) -> C.Contract:
    sensitive = [p for p in ("migrations/", "infra/", "db/") if (repo / p.rstrip("/")).exists()]
    return C.Contract(schema=SCHEMA_VERSION, context=context, artifact="graphify-out/graph.json",
                      sensitive=sensitive, freshness="two-tier", kit=__version__)


def write_agents(repo: Path, rep: Report, context: list[str]) -> None:
    agents = repo / "AGENTS.md"
    if agents.exists():
        text = agents.read_text()
        try:
            c = C.parse(text)
            c.kit = __version__
        except C.ContractError:
            c = default_contract(repo, context)
        text = C.replace_block(upsert_routing(text), c)
    else:
        c = default_contract(repo, context)
        text = render(_tmpl("AGENTS.md.tmpl"), repo_name=repo.name, routing=routing_section(), adlc_block=c.to_yaml())
    rep.write(agents, text)
    for svc in detect_services(repo):
        p = repo / svc / "AGENTS.md"
        if not p.exists():
            rep.write(p, render(_tmpl("AGENTS.service.md.tmpl"), service_name=svc, service_dir=svc + "/"))
        else:
            rep.rows.append(("kept (team-owned)", str(p)))


def _write_mcp(mcp_path: Path, rep: Report, s: dict, tools: list[str], context_path: str, project_args: str) -> None:
    existing = json.loads(mcp_path.read_text()) if mcp_path.exists() else {"mcpServers": {}}
    entry = json.loads(render(_tmpl("mcp.json.tmpl"), serena_repo=s["repo"], serena_commit=s["commit"],
                              serena_tools_json=json.dumps(tools), context_path=context_path,
                              project_args=project_args))["mcpServers"]["serena"]
    existing.setdefault("mcpServers", {})["serena"] = entry
    rep.write(mcp_path, json.dumps(existing, indent=2) + "\n")


def mcp_paths(repo: Path) -> list[Path]:
    """Every .mcp.json the kit owns: root plus one per detected service."""
    return [repo / ".mcp.json"] + [repo / svc / ".mcp.json" for svc in detect_services(repo)]


def write_serena(repo: Path, rep: Report, pins: dict) -> None:
    s = pins["serena"]
    tools = s["tools"]
    # Copilot CLI 1.0.105 loads .mcp.json from the *working directory only* (verified
    # 2026-11-01: from gateway/ the agent had no serena tools). Polyglot repos therefore get
    # one per service, pointing Serena at the repo-root project and context.
    _write_mcp(repo / ".mcp.json", rep, s, tools, context_path=".serena/adlc-context.yml", project_args='"--project-from-cwd",')
    for svc in detect_services(repo):
        _write_mcp(repo / svc / ".mcp.json", rep, s, tools, context_path="../.serena/adlc-context.yml", project_args='"--project", "..",')
    excluded = "\n".join(f"  - {t}" for t in ALL_SERENA_TOOLS if t not in tools)
    rep.write(repo / ".serena" / "adlc-context.yml",
              render(_tmpl("serena/adlc-context.yml.tmpl"), n_tools=str(len(tools)), excluded_tools_yaml=excluded))
    ls = [SERENA_LS[l] for l in repo_languages(repo)] or ["markdown"]
    rep.write(repo / ".serena" / "project.yml",
              render(_tmpl("serena/project.yml.tmpl"), repo_name=repo.name, language_servers_json=json.dumps(ls)), owned=False)
    keep = repo / ".serena" / "memories" / ".gitkeep"
    if not keep.exists():
        rep.write(keep, "")
    gi = repo / ".serena" / ".gitignore"
    rep.write(gi, "cache/\n*.log\n")


SKILL_PROFILES = ("vendor", "lean")


def write_lean_skill(repo: Path, rep: Report) -> None:
    """Kit-authored ~2 KB skill at the same path as the vendor one (routing text unchanged).
    Drops the vendor references/ dir so Copilot cannot load both."""
    dest = repo / ".github" / "skills" / "graphify"
    refs = dest / "references"
    if refs.exists():
        shutil.rmtree(refs)
        rep.rows.append(("removed", str(refs)))
    rep.write(dest / "SKILL.md", _tmpl("github/skills/graphify-lean/SKILL.md"))


def write_graphify_skill(repo: Path, rep: Report, pins: dict, profile: str = "vendor") -> None:
    if profile == "lean":
        write_lean_skill(repo, rep)
        return
    dest = repo / ".github" / "skills" / "graphify"
    with tempfile.TemporaryDirectory() as td:
        r = subprocess.run(["graphify", "install", "--platform", "copilot", "--project"], cwd=td,
                           capture_output=True, text=True, env={"PATH": _path_with_kit_bin(), "HOME": td,
                                                                 "GRAPHIFY_NO_TIPS": "1"})
        src = Path(td) / ".copilot" / "skills" / "graphify"
        if r.returncode != 0 or not src.exists():
            raise SystemExit(f"graphify install failed: {r.stderr.strip() or r.stdout.strip()}")
        skill = (src / "SKILL.md").read_text()
        head, _, body = skill.partition("\n---\n")
        if not skill.startswith("---"):
            head, body = "", skill
        stamped = (head + "\n---\n" if head else "") + "\n" + _tmpl("github/skills/graphify/PREAMBLE.md").rstrip() + "\n" + body
        staged = {}
        for f in src.rglob("*"):
            if f.is_file():
                staged[f.relative_to(src)] = stamped if f.name == "SKILL.md" else f.read_text()
    for rel, content in staged.items():
        rep.write(dest / rel, content)


def _path_with_kit_bin() -> str:
    import os
    import sys
    return str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")


def write_misc(repo: Path, rep: Report, pins: dict) -> None:
    k = pins["kit"]
    rep.write(repo / ".graphifyrc", render(_tmpl("graphifyrc.tmpl"), viz_node_limit="5000"))
    rep.write(repo / ".github" / "workflows" / "adlc.yml", render(_tmpl("github/workflows/adlc.yml.tmpl"), kit_repo=k["repo"], kit_ref=k["ref"]))
    rep.write(repo / "renovate.json", render(_tmpl("renovate.json.tmpl"), kit_repo=k["repo"], kit_ref=k["ref"]))
    gi = repo / ".gitignore"
    text = gi.read_text() if gi.exists() else ""
    snippet = _tmpl("gitignore.snippet").rstrip() + "\n"
    if GI_START in text and GI_END in text:
        a, b = text.index(GI_START), text.index(GI_END) + len(GI_END) + 1
        text = text[:a] + snippet + text[b:]
    else:
        text = text.rstrip() + ("\n\n" if text.strip() else "") + snippet
    rep.write(gi, text)


def run_init(repo: Path, context: list[str], skill_profile: str = "lean") -> Report:
    rep = Report()
    pins = load_pins()
    write_agents(repo, rep, context)
    if "serena" in context:
        write_serena(repo, rep, pins)
    if "graphify" in context:
        write_graphify_skill(repo, rep, pins, profile=skill_profile)
    write_misc(repo, rep, pins)
    return rep


def add_parser(sub) -> None:
    p = sub.add_parser("init", help="drop the contract layer into a repo (idempotent)")
    p.add_argument("--repo", default=".")
    p.add_argument("--context", default="graphify,serena", help="comma list: graphify,serena")
    p.add_argument("--yes", action="store_true", help="no prompts (there are none; kept for muscle memory)")
    p.add_argument("--skill-profile", choices=SKILL_PROFILES, default="lean",
                   help="graphify skill: 'lean' (kit-authored ~2 KB, default — measured better on every axis) or 'vendor' (as shipped, 48 KB + references)")
    p.set_defaults(func=run)


def run(args) -> int:
    repo = Path(args.repo).resolve()
    if not (repo / ".git").exists():
        print(f"error: {repo} is not a git repository")
        return 2
    context = [c.strip() for c in args.context.split(",") if c.strip()]
    if is_docs_only(repo) and "serena" in context:
        context = [c for c in context if c != "serena"]
        print("note: no code detected — Serena skipped for this repo (docs-only)")
    rep = run_init(repo, context, skill_profile=args.skill_profile)
    width = max(len(s) for s, _ in rep.rows)
    for status, path in rep.rows:
        print(f"  {status:<{width}}  {Path(path).relative_to(repo)}")
    print(f"adlc init done — {repo.name} (kit {__version__}, schema {SCHEMA_VERSION}). Fill the TODOs in AGENTS.md, then `adlc doctor`.")
    return 0
