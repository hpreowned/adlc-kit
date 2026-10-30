"""`adlc upgrade`: migrate a repo's adlc block from schema N to N+1 and bump `kit:`.
Each migration is a pure function Contract -> Contract plus an optional repo hook."""
from __future__ import annotations

from pathlib import Path

from adlc import __version__
from adlc import contract as C
from adlc.init import run_init


def _default_owner(repo: Path) -> str:
    for cand in (repo / "CODEOWNERS", repo / ".github" / "CODEOWNERS"):
        if cand.exists():
            for line in cand.read_text().splitlines():
                parts = line.split()
                if parts and parts[0] == "*" and len(parts) > 1:
                    return parts[1]
    return "TODO"


def migrate_1_to_2(c: C.Contract, repo: Path) -> C.Contract:
    """Schema 2 adds `owner` (default CODEOWNERS team) so org-level graphs can attach
    ownership without re-parsing CODEOWNERS."""
    c.schema = 2
    c.extra.setdefault("owner", _default_owner(repo))
    return c


MIGRATIONS = {1: migrate_1_to_2}


def upgrade(repo: Path, target: int) -> C.Contract:
    agents = repo / "AGENTS.md"
    text = agents.read_text()
    c = C.parse(text)
    while c.schema < target:
        step = MIGRATIONS.get(c.schema)
        if step is None:
            raise SystemExit(f"no migration from schema {c.schema}")
        c = step(c, repo)
    c.kit = __version__
    agents.write_text(C.replace_block(text, c))
    run_init(repo, c.context)  # refresh kit-owned files for the new schema
    return c


def add_parser(sub) -> None:
    p = sub.add_parser("upgrade", help="migrate adlc block to a newer schema")
    p.add_argument("--repo", default=".")
    p.add_argument("--to", type=int, default=None, help="target schema (default: highest known)")
    p.set_defaults(func=run)


def run(args) -> int:
    target = args.to or (max(MIGRATIONS) + 1)
    c = upgrade(Path(args.repo).resolve(), target)
    print(f"upgraded to schema {c.schema}, kit {c.kit}")
    return 0
