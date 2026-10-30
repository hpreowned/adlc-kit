"""Redaction for anything that lands in results/: tokens, API keys, absolute temp paths,
system prompts, opaque reasoning blobs. GUARDRAILS 1."""
from __future__ import annotations

import json
import re

TOKEN_RES = [
    re.compile(r"gh[opsur]_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9\-_]{20,}"),
    re.compile(r"AIza[0-9A-Za-z\-_]{30,}"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password)(['\"]?\s*[:=]\s*['\"]?)[A-Za-z0-9\-_./+]{12,}"),
]
DROP_KEYS = {"reasoningOpaque", "requestId", "clientRequestId", "serviceRequestId", "apiCallId"}


def scrub_text(text: str, roots: list[str] | None = None) -> str:
    for rx in TOKEN_RES:
        text = rx.sub(lambda m: (m.group(1) + m.group(2) + "<redacted>") if m.lastindex and m.lastindex >= 2 else "<redacted>", text)
    for root in roots or []:
        if root:
            text = text.replace(root, "<run>")
    text = re.sub(r"/private/tmp/[^\s\"']+|/tmp/[^\s\"']+", "<tmp>", text)
    return text


def scrub_event(ev: dict, roots: list[str] | None = None) -> dict:
    d = ev.get("data")
    if isinstance(d, dict):
        if ev.get("type") == "system.message":
            d["content"] = "<scrubbed system prompt>"
        for k in DROP_KEYS:
            d.pop(k, None)
    return json.loads(scrub_text(json.dumps(ev), roots))


def scrub_jsonl(text: str, roots: list[str] | None = None) -> str:
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.dumps(scrub_event(json.loads(line), roots)))
        except json.JSONDecodeError:
            out.append(scrub_text(line, roots))
    return "\n".join(out) + ("\n" if out else "")
