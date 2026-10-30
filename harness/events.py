"""Parser for Copilot CLI `events.jsonl` (schema: harness/EVENTS_SCHEMA.md).

Primary metric source for the pilot. Everything here is derived from fields observed
in real sessions; unknown event types are counted, never fatal."""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

READ_TOOLS = {"view", "grep", "glob", "bash", "read_file", "search", "list_dir", "find"}


@dataclass
class RunMetrics:
    session_id: str = ""
    copilot_version: str = ""
    models: list[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0
    premium_requests: float | None = None      # shutdown.totalPremiumRequests (billing: per prompt × multiplier)
    premium_cost_sum: float | None = None      # sum(usage_record.cost): model calls × multiplier ("AI credits" proxy)
    model_calls: int = 0                        # count of session.usage_record (one per model API call)
    nano_aiu: int | None = None                 # shutdown/usage_checkpoint totalNanoAiu (AI units, undocumented)
    api_duration_ms: int = 0
    wall_ms: int = 0
    turns: int = 0
    tool_calls: dict[str, int] = field(default_factory=dict)
    mcp_tool_calls: dict[str, int] = field(default_factory=dict)
    bytes_read: int = 0                         # proxy: result length of read-ish tools
    files_modified: list[str] = field(default_factory=list)
    lines_added: int = 0
    lines_removed: int = 0
    skills_invoked: list[str] = field(default_factory=list)
    session_error: str | None = None            # session.error message (e.g. quota exhausted)
    shutdown_seen: bool = False
    unknown_event_types: dict[str, int] = field(default_factory=dict)
    event_count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def _ts(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _tool_bucket(name: str) -> str:
    return name.split("(")[0].split("__")[0] if name else "?"


def parse_events(lines) -> RunMetrics:
    m = RunMetrics()
    tools: Counter = Counter()
    mcp: Counter = Counter()
    unknown: Counter = Counter()
    first = last = None
    cost = 0.0
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            ev = json.loads(raw)
        except json.JSONDecodeError:
            continue
        m.event_count += 1
        t, d = ev.get("type", ""), ev.get("data", {}) or {}
        ts = _ts(ev.get("timestamp"))
        if ts:
            first = first or ts
            last = ts
        if t == "session.start":
            m.session_id = d.get("sessionId", "")
            m.copilot_version = d.get("copilotVersion", "")
        elif t == "assistant.turn_start":
            m.turns += 1
            if d.get("model") and d["model"] not in m.models:
                m.models.append(d["model"])
        elif t == "tool.execution_start":
            name = d.get("toolName", "?")
            tools[name] += 1
            if "-" in name or name.startswith("mcp") or "__" in name:
                mcp[name] += 1
        elif t == "tool.execution_complete":
            name = _tool_bucket(_tool_name_from_complete(d))
            metrics = (d.get("toolTelemetry") or {}).get("metrics") or {}
            size = metrics.get("resultLength") or metrics.get("resultForLlmLength")
            if size is None:
                size = len(((d.get("result") or {}).get("content") or ""))
            if name in READ_TOOLS:
                m.bytes_read += int(size or 0)
        elif t == "session.usage_record":
            u = d.get("usage") or {}
            m.model_calls += 1
            cost += float(u.get("cost") or 0)
            if u.get("model") and u["model"] not in m.models:
                m.models.append(u["model"])
        elif t == "session.error":
            m.session_error = str(d.get("message") or d.get("content") or d)[:300]
        elif t == "skill.invoked":
            m.skills_invoked.append(d.get("name", "?"))
        elif t == "session.shutdown":
            m.shutdown_seen = True
            td = d.get("tokenDetails") or {}
            m.input_tokens = int((td.get("input") or {}).get("tokenCount", 0))
            m.output_tokens = int((td.get("output") or {}).get("tokenCount", 0))
            m.cache_read_tokens = int((td.get("cache_read") or {}).get("tokenCount", 0))
            m.cache_write_tokens = int((td.get("cache_write") or {}).get("tokenCount", 0))
            for mm in (d.get("modelMetrics") or {}).values():
                m.reasoning_tokens += int((mm.get("usage") or {}).get("reasoningTokens", 0))
            m.premium_requests = d.get("totalPremiumRequests")
            m.nano_aiu = d.get("totalNanoAiu")
            m.api_duration_ms = int(d.get("totalApiDurationMs") or 0)
            cc = d.get("codeChanges") or {}
            m.files_modified = list(cc.get("filesModified") or [])
            m.lines_added = int(cc.get("linesAdded") or 0)
            m.lines_removed = int(cc.get("linesRemoved") or 0)
        elif t.startswith(("session.", "assistant.", "user.", "system.", "model.", "skill.")):
            pass
        else:
            unknown[t] += 1
    m.tool_calls = dict(tools)
    m.mcp_tool_calls = dict(mcp)
    m.premium_cost_sum = cost if m.model_calls else None
    m.unknown_event_types = dict(unknown)
    if first and last:
        m.wall_ms = int((last - first).total_seconds() * 1000)
    return m


_START_NAMES: dict[str, str] = {}


def _tool_name_from_complete(d: dict) -> str:
    # execution_complete lacks toolName; correlate via toolCallId recorded at start.
    return _START_NAMES.get(d.get("toolCallId", ""), "")


def parse_file(path: Path) -> RunMetrics:
    text = path.read_text().splitlines()
    _START_NAMES.clear()
    for raw in text:
        try:
            ev = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "tool.execution_start":
            d = ev.get("data") or {}
            _START_NAMES[d.get("toolCallId", "")] = d.get("toolName", "")
    return parse_events(text)


def find_events_file(copilot_home: Path) -> Path | None:
    cands = sorted((copilot_home / "session-state").glob("*/events.jsonl"),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    return cands[0] if cands else None
