"""`adlc` entry point. Each subcommand lives in its own module (adlc/<name>.py) and
exposes `add_parser(subparsers)` and `run(args) -> int`."""
from __future__ import annotations

import argparse
import importlib
import sys

from adlc import __version__

SUBCOMMANDS = [
    "init", "doctor", "baseline", "stale", "eval", "regress", "scorecard",
    "upgrade", "federate", "query", "pins", "lint",
]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="adlc", description=__doc__)
    p.add_argument("--version", action="version", version=f"adlc {__version__}")
    sub = p.add_subparsers(dest="command", required=True)
    for name in SUBCOMMANDS:
        mod = importlib.import_module(f"adlc.{name}")
        mod.add_parser(sub)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    mod = importlib.import_module(f"adlc.{args.command}")
    try:
        return int(mod.run(args) or 0)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
