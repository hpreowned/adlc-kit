"""`adlc guard-hook`: Copilot CLI preToolUse adapter for graphify's hook-guard.
Reads {toolName, toolArgs} on stdin; maps view→read, grep/rg→grep, glob→find; runs
`graphify hook-guard <kind>` and emits Copilot's decision JSON. Non-strict (default):
allow + additionalContext carrying graphify's reminder. Strict (GRAPHIFY_HOOK_STRICT=1):
deny when graphify says the read is covered by the graph. ONLY the graphify-guard arm
installs this hook (harness/arms/graphify-guard); `adlc init` never does."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# Copilot tool -> graphify hook-guard kind (graphify knows "read" and "search")
KIND = {"view": "read", "read": "read", "grep": "search", "rg": "search", "glob": "search", "bash": "search"}
ARG_KEYS = {"read": ("path", "file_path", "file"), "search": ("pattern", "query", "command", "glob", "path")}


def _tool_input(kind: str, args: dict) -> dict:
    """Translate Copilot toolArgs into the Claude-Code-shaped tool_input graphify reads."""
    out = {}
    for key in ARG_KEYS[kind]:
        v = args.get(key)
        if isinstance(v, str) and v:
            out["file_path" if kind == "read" else ("command" if key == "command" else "pattern")] = v
            break
    return out


def decide(event: dict, strict: bool, runner=subprocess.run) -> dict:
    kind = KIND.get(str(event.get("toolName", "")).lower())
    if not kind:
        return {"permissionDecision": "allow"}
    tool_input = _tool_input(kind, event.get("toolArgs") or {})
    if not tool_input:
        return {"permissionDecision": "allow"}
    cmd = ["graphify", "hook-guard", kind] + (["--strict"] if strict and kind == "read" else [])
    env = {**os.environ, "GRAPHIFY_NO_TIPS": "1", "CLAUDE_PROJECT_DIR": event.get("cwd") or os.getcwd(),
           "PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")}
    try:
        r = runner(cmd, input=json.dumps({"tool_input": tool_input}), capture_output=True, text=True, timeout=15, env=env, cwd=env["CLAUDE_PROJECT_DIR"])
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"permissionDecision": "allow", "additionalContext": f"adlc guard-hook: graphify unavailable ({e.__class__.__name__}); proceeding"}
    text = (r.stdout or "").strip()
    if not text:
        return {"permissionDecision": "allow"}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {"permissionDecision": "allow", "additionalContext": text[:1500]}
    hso = payload.get("hookSpecificOutput") or {}
    decision = payload.get("permissionDecision") or hso.get("permissionDecision")
    reason = payload.get("permissionDecisionReason") or hso.get("permissionDecisionReason") or "graph covers this read — use /graphify query"
    if strict and decision == "deny":
        return {"permissionDecision": "deny", "permissionDecisionReason": reason[:1500]}
    ctx = payload.get("additionalContext") or hso.get("additionalContext") or reason
    return {"permissionDecision": "allow", "additionalContext": str(ctx)[:1500]}


def hook_json(strict: bool) -> dict:
    env = "GRAPHIFY_HOOK_STRICT=1 " if strict else ""
    return {"version": 1, "hooks": {"preToolUse": [{"type": "command", "bash": f"{env}adlc guard-hook", "timeoutSec": 20}]}}


def add_parser(sub) -> None:
    p = sub.add_parser("guard-hook", help="Copilot preToolUse adapter for graphify hook-guard (guard arm only)")
    p.set_defaults(func=run)


def run(args) -> int:
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        event = {}
    strict = os.environ.get("GRAPHIFY_HOOK_STRICT", "").lower() in ("1", "true", "yes")
    print(json.dumps(decide(event, strict)))
    return 0
