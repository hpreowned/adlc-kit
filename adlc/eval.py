"""`adlc eval` — implemented in a later phase."""
from __future__ import annotations


def add_parser(sub) -> None:
    p = sub.add_parser("eval", help="(not yet implemented)")
    p.set_defaults(func=run)


def run(args) -> int:
    print("adlc eval: not implemented yet")
    return 2
