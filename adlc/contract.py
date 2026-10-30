"""The contract: AGENTS.md + its fenced `adlc` block. This is the ONLY machine-readable
part of the contract; everything else in AGENTS.md is prose for the agent."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from adlc import SCHEMA_VERSION

BLOCK_RE = re.compile(r"```ya?ml\s*\n(adlc:\n(?:[ \t]+.*\n)+?)```", re.MULTILINE)
VALID_CONTEXT = {"graphify", "serena"}
VALID_FRESHNESS = {"two-tier", "strict", "advisory"}
REQUIRED = ("schema", "context", "artifact", "freshness", "kit")


@dataclass
class Contract:
    schema: int
    context: list[str]
    artifact: str
    sensitive: list[str] = field(default_factory=list)
    freshness: str = "two-tier"
    kit: str = "0.0.0"
    stale_threshold: int = 10
    extra: dict = field(default_factory=dict)

    def to_yaml(self) -> str:
        data = {
            "adlc": {
                "schema": self.schema,
                "context": list(self.context),
                "artifact": self.artifact,
                "sensitive": list(self.sensitive),
                "freshness": self.freshness,
                "kit": self.kit,
                **({"stale_threshold": self.stale_threshold} if self.stale_threshold != 10 else {}),
                **self.extra,
            }
        }
        return yaml.safe_dump(data, sort_keys=False, default_flow_style=None).rstrip() + "\n"


class ContractError(ValueError):
    pass


def find_block(text: str) -> tuple[str, int, int] | None:
    m = BLOCK_RE.search(text)
    return (m.group(1), m.start(), m.end()) if m else None


def parse(text: str) -> Contract:
    found = find_block(text)
    if not found:
        raise ContractError("AGENTS.md has no fenced ```yaml adlc: block")
    raw, _, _ = found
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as e:  # pragma: no cover - message passthrough
        raise ContractError(f"adlc block is not valid YAML: {e}") from e
    body = (data or {}).get("adlc")
    if not isinstance(body, dict):
        raise ContractError("adlc block must be a mapping under key `adlc`")
    missing = [k for k in REQUIRED if k not in body]
    if missing:
        raise ContractError(f"adlc block missing keys: {', '.join(missing)}")
    if not isinstance(body["schema"], int):
        raise ContractError("adlc.schema must be an integer")
    ctx = body["context"]
    if not isinstance(ctx, list) or not set(ctx) <= VALID_CONTEXT:
        raise ContractError(f"adlc.context must be a list drawn from {sorted(VALID_CONTEXT)}")
    if body["freshness"] not in VALID_FRESHNESS:
        raise ContractError(f"adlc.freshness must be one of {sorted(VALID_FRESHNESS)}")
    known = set(REQUIRED) | {"sensitive", "stale_threshold"}
    return Contract(
        schema=body["schema"], context=list(ctx), artifact=str(body["artifact"]),
        sensitive=[str(s) for s in body.get("sensitive", [])], freshness=body["freshness"],
        kit=str(body["kit"]), stale_threshold=int(body.get("stale_threshold", 10)),
        extra={k: v for k, v in body.items() if k not in known},
    )


def load(repo: Path) -> Contract:
    agents = repo / "AGENTS.md"
    if not agents.exists():
        raise ContractError(f"{agents} not found — run `adlc init`")
    return parse(agents.read_text())


def replace_block(text: str, contract: Contract) -> str:
    """Rewrite the fenced block in place, leaving all prose untouched."""
    found = find_block(text)
    new = "```yaml\n" + contract.to_yaml() + "```"
    if not found:
        return text.rstrip() + "\n\n" + new + "\n"
    _, start, end = found
    return text[:start] + new + text[end:]


def referenced_paths(text: str, repo: Path | None = None) -> list[str]:
    """Backtick-quoted relative paths in AGENTS.md prose that the drift lint checks.

    Every backticked path must exist in this repo. Convention for paths in OTHER repos:
    write them as `repo:path` (the colon keeps them out of this check). Placeholders
    containing NNNN, YYYY, <...> or * are skipped; a single word needs a file extension
    to count as a path."""
    out = []
    for m in re.finditer(r"`([A-Za-z0-9_./-]+)`", text):
        p = m.group(1).rstrip("/").rstrip(".")
        if not p or p.startswith(("http", "-", ".")) or re.search(r"NNNN|YYYY|[<>*]", p):
            continue
        if "/" in p:
            out.append(p)
        elif re.search(r"\.[a-z]{1,5}$", p) and p not in {"e.g", "i.e", "vs", "etc"}:
            out.append(p)
    return sorted(set(out))


def current_schema() -> int:
    return SCHEMA_VERSION
