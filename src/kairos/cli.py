"""Kairos CLI — run agent harness and decision cycles."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="Kairos bookmark surfacing agent")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("cycle", help="Run one bandit decision cycle")
    sub.add_parser("chat", help="Interactive agent turn").add_argument(
        "prompt", nargs="?", default="Run one decision cycle."
    )

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.command == "cycle":
        from kairos.agent.harness import run_decision_cycle

        result = asyncio.run(run_decision_cycle())
        print(result.model_dump_json(indent=2) if result else "No structured result")
    elif args.command == "chat":
        from kairos.agent.harness import run_interactive

        text = asyncio.run(run_interactive(args.prompt))
        print(text)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
