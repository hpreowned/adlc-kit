"""`adlc query` — implemented in a later phase."""
from __future__ import annotations


def add_parser(sub) -> None:
    p = sub.add_parser("query", help="(not yet implemented)")
    p.set_defaults(func=run)


def run(args) -> int:
    print("adlc query: not implemented yet")
    return 2
