"""`adlc regress` — implemented in a later phase."""
from __future__ import annotations


def add_parser(sub) -> None:
    p = sub.add_parser("regress", help="(not yet implemented)")
    p.set_defaults(func=run)


def run(args) -> int:
    print("adlc regress: not implemented yet")
    return 2
