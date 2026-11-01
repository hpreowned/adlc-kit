"""`adlc force-hook`: Copilot preToolUse adapter for the serena-forced arm ONLY.

Denies every text-search tool (the built-in `rg` / `grep_search` / `search_code_subagent`
tools and any shell command that runs a grep-family program) so the agent has to reach for
Serena's symbol tools. File listing (`glob`, `file_search`) and reading (`view`,
`read_file`) stay allowed. Never installed by `adlc init`; the harness writes it into the
working copy of that arm and nowhere else.
"""
from __future__ import annotations

import json
import re
import sys

DENIED_TOOLS = {"rg", "grep_search", "search_code_subagent"}
SHELL_TOOLS = {"bash", "shell", "run_in_terminal", "powershell"}
GREP_RE = re.compile(r"(^|[\s|;&(`])(rg|grep|egrep|fgrep|zgrep|ag|ack|ugrep)(\s|$)|\bgit\s+grep\b")
REASON = ("Text search is disabled in this session. Use Serena: find_symbol (name or substring), "
          "get_symbols_overview (a file's symbols), find_referencing_symbols (who uses it), "
          "find_implementations; then view the file it points at.")


def decide(event: dict) -> dict:
    name = str(event.get("toolName", "")).lower()
    if name in DENIED_TOOLS:
        return {"permissionDecision": "deny", "permissionDecisionReason": REASON}
    if name in SHELL_TOOLS:
        args = event.get("toolArgs") or {}
        cmd = args.get("command") or args.get("cmd") or ""
        if isinstance(cmd, list):
            cmd = " ".join(map(str, cmd))
        if GREP_RE.search(str(cmd)):
            return {"permissionDecision": "deny", "permissionDecisionReason": REASON}
    return {"permissionDecision": "allow"}


def hook_json() -> dict:
    return {"version": 1, "hooks": {"preToolUse": [{"type": "command", "bash": "adlc force-hook", "timeoutSec": 10}]}}


def add_parser(sub) -> None:
    p = sub.add_parser("force-hook", help="preToolUse adapter that denies text search (serena-forced arm only)")
    p.set_defaults(func=run)


def run(args) -> int:
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        event = {}
    print(json.dumps(decide(event)))
    return 0
