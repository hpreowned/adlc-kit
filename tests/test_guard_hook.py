import json
from types import SimpleNamespace

from adlc import guard_hook


def _runner(rc, out):
    def run(cmd, **kw):
        return SimpleNamespace(returncode=rc, stdout=out, stderr="")
    return run


def test_non_read_tools_pass_through():
    assert guard_hook.decide({"toolName": "edit"}, False) == {"permissionDecision": "allow"}
    assert guard_hook.decide({"toolName": "bash", "toolArgs": {}}, False) == {"permissionDecision": "allow"}


def test_non_strict_allows_with_reminder():
    d = guard_hook.decide({"toolName": "view", "toolArgs": {"path": "a.py"}}, False, runner=_runner(0, "graph has a.py: try /graphify explain"))
    assert d["permissionDecision"] == "allow" and "graphify" in d["additionalContext"]


def test_strict_denies_when_graph_covers():
    d = guard_hook.decide({"toolName": "view", "toolArgs": {"path": "x.py"}}, True,
                          runner=_runner(0, json.dumps({"hookSpecificOutput": {"permissionDecision": "deny", "permissionDecisionReason": "covered"}})))
    assert d["permissionDecision"] == "deny" and d["permissionDecisionReason"] == "covered"
    # search kinds are nudge-only even in strict mode (graphify never blocks them)
    d = guard_hook.decide({"toolName": "grep", "toolArgs": {"pattern": "x"}}, True, runner=_runner(0, "nudge"))
    assert d["permissionDecision"] == "allow" and d["additionalContext"] == "nudge"


def test_graphify_missing_is_fail_open():
    def boom(cmd, **kw):
        raise OSError("no graphify")
    d = guard_hook.decide({"toolName": "view", "toolArgs": {"path": "a"}}, True, runner=boom)
    assert d["permissionDecision"] == "allow" and "unavailable" in d["additionalContext"]


def test_hook_json_shape():
    h = guard_hook.hook_json(strict=False)
    assert h["version"] == 1 and h["hooks"]["preToolUse"][0]["bash"] == "adlc guard-hook"
    assert guard_hook.hook_json(True)["hooks"]["preToolUse"][0]["bash"].startswith("GRAPHIFY_HOOK_STRICT=1")
