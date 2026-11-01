"""`adlc lint`: the contract lint that `adlc-contract-lint` runs on every PR. Exit 1 on
any failure. Checks the block, the routing section, referenced paths, single source
of instructions, and that pins in the repo match the installed kit."""
from __future__ import annotations

import json
from pathlib import Path

from adlc import SCHEMA_VERSION, __version__
from adlc import contract as C
from adlc.pins import load_pins

SUPPORTED_SCHEMAS = {1, 2}


def lint(repo: Path) -> tuple[list[str], list[str]]:
    fails: list[str] = []
    warns: list[str] = []
    agents = repo / "AGENTS.md"
    if not agents.exists():
        return ["AGENTS.md missing (run `adlc init`)"], warns
    text = agents.read_text()
    try:
        c = C.parse(text)
    except C.ContractError as e:
        return [f"adlc block: {e}"], warns
    if c.schema not in SUPPORTED_SCHEMAS:
        fails.append(f"adlc.schema {c.schema} unsupported by kit {__version__} (supports {sorted(SUPPORTED_SCHEMAS)})")
    elif c.schema < SCHEMA_VERSION:
        warns.append(f"adlc.schema {c.schema} < kit default {SCHEMA_VERSION}; run `adlc upgrade`")
    if c.kit != __version__:
        warns.append(f"adlc.kit {c.kit} != installed kit {__version__}")
    if "<!-- adlc:routing:start -->" not in text:
        fails.append("CONTEXT ROUTING section missing (kit-owned; `adlc init` restores it)")
    if "TODO" in text:
        warns.append("AGENTS.md still has TODO placeholders")
    for p in C.referenced_paths(text, repo):
        if not (repo / p).exists():
            fails.append(f"AGENTS.md references `{p}` which does not exist")
    if (repo / ".github" / "copilot-instructions.md").exists():
        fails.append(".github/copilot-instructions.md exists — AGENTS.md is the single source; delete it")
    if not (repo / c.artifact).exists():
        warns.append(f"artifact {c.artifact} not built yet (`adlc baseline`)")
    pins = load_pins()
    if "serena" in c.context:
        from adlc.init import mcp_paths
        for mcp in mcp_paths(repo):
            rel = str(mcp.relative_to(repo))
            if not mcp.exists():
                fails.append(f"{rel} missing but context includes serena (Copilot loads .mcp.json from cwd only)")
                continue
            servers = json.loads(mcp.read_text()).get("mcpServers", {})
            for name, srv in servers.items():
                if srv.get("type") not in (None, "local", "stdio"):
                    fails.append(f"{rel} server `{name}` is {srv.get('type')} — hosted MCP is not allowed (GUARDRAILS 5)")
                if "graphify.com" in json.dumps(srv):
                    fails.append(f"{rel} server `{name}` points at Graphify Cloud (GUARDRAILS 5)")
                if name != "serena":
                    fails.append(f"{rel} server `{name}` has no entry in policy/CLI_FIRST.md")
            entry = servers.get("serena", {})
            args = " ".join(entry.get("args", []))
            if pins["serena"]["commit"] not in args:
                fails.append(f"{rel} serena pin != kit pin {pins['serena']['commit'][:12]}")
            if set(entry.get("tools", [])) != set(pins["serena"]["tools"]):
                fails.append(f"{rel} serena tools allowlist differs from kit allowlist")
        from adlc.init import serena_roots
        for root in serena_roots(repo):
            if not (root / ".serena" / "adlc-context.yml").exists():
                fails.append(f"{(root / '.serena/adlc-context.yml').relative_to(repo)} missing (Serena tool trim)")
    if "graphify" in c.context and not (repo / ".github" / "skills" / "graphify" / "SKILL.md").exists():
        fails.append(".github/skills/graphify/SKILL.md missing")
    warns += sensitive_edit_warnings(repo, c)
    wf = repo / ".github" / "workflows" / "adlc.yml"
    if not wf.exists():
        fails.append(".github/workflows/adlc.yml missing")
    elif pins["kit"]["ref"] not in wf.read_text():
        warns.append(f"workflow does not reference kit ref {pins['kit']['ref']}")
    return fails, warns


def sensitive_edit_warnings(repo: Path, c: C.Contract, base: str = "origin/main") -> list[str]:
    """GUARDRAILS 12: commits touching `sensitive:` paths must cite a ticket id."""
    import re
    import subprocess
    if not c.sensitive:
        return []
    r = subprocess.run(["git", "-C", str(repo), "log", "--format=%H %s", f"{base}..HEAD", "--", *c.sensitive],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return []
    out = []
    for line in r.stdout.splitlines():
        sha, _, subject = line.partition(" ")
        if not re.search(r"\b[A-Z]{2,6}-\d+\b", subject):
            out.append(f"commit {sha[:8]} touches a sensitive path without a ticket id: {subject!r}")
    return out


def add_parser(sub) -> None:
    p = sub.add_parser("lint", help="contract lint (what CI enforces on PRs)")
    p.add_argument("--repo", default=".")
    p.set_defaults(func=run)


def run(args) -> int:
    fails, warns = lint(Path(args.repo).resolve())
    for w in warns:
        print(f"  warn  {w}")
    for f in fails:
        print(f"  FAIL  {f}")
    print("contract lint: " + ("OK" if not fails else f"{len(fails)} failure(s)"))
    return 1 if fails else 0
