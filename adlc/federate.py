"""`adlc federate` — implemented in a later phase."""
from __future__ import annotations


def add_parser(sub) -> None:
    p = sub.add_parser("federate", help="(not yet implemented)")
    p.set_defaults(func=run)


def run(args) -> int:
    print("adlc federate: not implemented yet")
    return 2


def stale_federated(repo, level: str, as_json: bool = False) -> int:
    print(f"adlc stale --level {level}: federation not built yet")
    return 2
