"""Kairos CLI — heartbeat, agent harness, and server."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="Kairos bookmark surfacing agent")
    sub = parser.add_subparsers(dest="command", required=True)

    heartbeat = sub.add_parser("heartbeat", help="Run one policy heartbeat")
    heartbeat.add_argument(
        "--delivery",
        choices=["auto", "return_only", "none"],
        default="auto",
    )

    sub.add_parser("cycle", help="Alias for heartbeat")
    agent_cycle = sub.add_parser("agent-cycle", help="Run heartbeat via Antigravity agent")
    sub.add_parser("chat", help="Interactive agent turn").add_argument(
        "prompt", nargs="?", default="Run one heartbeat cycle."
    )
    sub.add_parser("serve", help="Start web gateway (stub)")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.command in ("heartbeat", "cycle"):
        from kairos.agent.harness import run_decision_cycle

        delivery = getattr(args, "delivery", "auto")
        result = asyncio.run(run_decision_cycle(delivery=delivery))
        print(json.dumps(result.model_dump(), indent=2, default=str))
    elif args.command == "agent-cycle":
        from kairos.agent.harness import run_decision_cycle_via_agent

        result = asyncio.run(run_decision_cycle_via_agent())
        print(result.model_dump_json(indent=2) if result else "No structured result")
    elif args.command == "chat":
        from kairos.agent.harness import run_interactive

        text = asyncio.run(run_interactive(args.prompt))
        print(text)
    elif args.command == "serve":
        print("Web gateway not yet implemented — use event_bus SSE stub for now.")
        sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
