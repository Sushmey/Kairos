"""Kairos CLI — heartbeat, agent harness, and server."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path


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

    x_cmd = sub.add_parser("x", help="X API utilities")
    x_sub = x_cmd.add_subparsers(dest="x_command", required=True)
    whoami_parser = x_sub.add_parser(
        "whoami", help="Print authenticated user id from GET /2/users/me"
    )
    whoami_parser.add_argument(
        "--write-env",
        action="store_true",
        help="Write numeric X_USER_ID to .env",
    )
    whoami_parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Path to .env file (default: ./.env)",
    )
    refresh_parser = x_sub.add_parser(
        "refresh", help="Refresh X_ACCESS_TOKEN using X_REFRESH_TOKEN"
    )
    refresh_parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Path to .env file to update (default: ./.env)",
    )
    refresh_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Refresh tokens but do not write .env",
    )

    auth_parser = x_sub.add_parser(
        "auth", help="OAuth 2.0 Authorization Code flow with PKCE"
    )
    auth_parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Path to .env file to update (default: ./.env)",
    )
    auth_parser.add_argument(
        "--redirect-uri",
        default=None,
        help="Override X_OAUTH_REDIRECT_URI (must match X app callback URL)",
    )
    auth_parser.add_argument(
        "--scope",
        default=None,
        help="Override X_OAUTH_SCOPES (space-separated)",
    )
    auth_parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Print authorize URL only; do not open a browser",
    )
    auth_parser.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        help="Seconds to wait for OAuth callback (default: 300)",
    )
    auth_parser.add_argument(
        "--minimal-scopes",
        action="store_true",
        help="Use users.read tweet.read offline.access (skip bookmark.read for OAuth debugging)",
    )

    x_sub.add_parser("auth-check", help="Validate X OAuth config and print setup checklist")

    ingest_cmd = sub.add_parser("ingest", help="Bookmark ingest pipelines")
    ingest_sub = ingest_cmd.add_subparsers(dest="ingest_command", required=True)
    sync_parser = ingest_sub.add_parser("sync", help="Sync bookmarks from X API to MongoDB")
    sync_parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Limit pagination (default: all pages)",
    )
    sync_parser.add_argument(
        "--skip-enrich",
        action="store_true",
        help="Skip Gemini enrichment (faster smoke test)",
    )
    sync_parser.add_argument(
        "--enrich-existing",
        action="store_true",
        help="Re-run enrichment even when raw_text unchanged",
    )

    bookmarks_cmd = sub.add_parser("bookmarks", help="Read bookmarks from MongoDB")
    bookmarks_sub = bookmarks_cmd.add_subparsers(dest="bookmarks_command", required=True)
    list_parser = bookmarks_sub.add_parser("list", help="List stored bookmarks")
    list_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Max bookmarks to return (default: 20)",
    )
    list_parser.add_argument(
        "--skip",
        type=int,
        default=0,
        help="Number of bookmarks to skip (default: 0)",
    )
    list_parser.add_argument(
        "--json",
        action="store_true",
        help="Output full JSON",
    )
    get_parser = bookmarks_sub.add_parser("get", help="Get one bookmark by x_tweet_id")
    get_parser.add_argument("x_tweet_id", help="X tweet id")
    get_parser.add_argument(
        "--json",
        action="store_true",
        help="Output full JSON",
    )
    enrich_parser = bookmarks_sub.add_parser(
        "enrich", help="Backfill Gemini enrichment on stored bookmarks"
    )
    enrich_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max bookmarks to process (default: all)",
    )
    enrich_parser.add_argument(
        "--force",
        action="store_true",
        help="Re-enrich even when consumption_mode is already set",
    )
    enrich_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List what would be enriched without calling Gemini",
    )
    enrich_parser.add_argument(
        "--concurrency",
        type=int,
        default=None,
        help="Parallel Gemini requests (default: ENRICH_CONCURRENCY or 10)",
    )

    embed_parser = bookmarks_sub.add_parser(
        "embed", help="Compute embeddings for stored bookmarks"
    )
    embed_parser.add_argument("--limit", type=int, default=None)
    embed_parser.add_argument(
        "--force",
        action="store_true",
        help="Re-embed even when embedding exists",
    )

    cluster_parser = bookmarks_sub.add_parser(
        "cluster", help="HDBSCAN cluster bookmarks by embedding"
    )
    cluster_parser.add_argument(
        "--min-cluster-size",
        type=int,
        default=None,
        help="HDBSCAN min_cluster_size (default: HDBSCAN_MIN_CLUSTER_SIZE or 3)",
    )

    clusters_parser = bookmarks_sub.add_parser(
        "clusters", help="List persisted topic clusters"
    )
    clusters_parser.add_argument("--json", action="store_true")
    clusters_parser.add_argument("--limit", type=int, default=20)

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
    elif args.command == "x":
        if args.x_command == "whoami":
            if args.write_env:
                from kairos.ingest.x.auth import persist_x_user_id

                result = asyncio.run(persist_x_user_id(args.env_file))
                print(f"✓ X_USER_ID={result.user_id}")
                if result.username:
                    print(f"  username: @{result.username}")
                if result.name:
                    print(f"  name:     {result.name}")
                print(f"  updated:  {result.env_path.resolve()}")
            else:
                from kairos.ingest.sync import fetch_x_user_id

                user_id = asyncio.run(fetch_x_user_id())
                print(user_id)
        elif args.x_command == "auth-check":
            from kairos.ingest.x.auth_check import run_auth_check

            check = run_auth_check()
            print("\n".join(check.lines))
            sys.exit(0 if check.ok else 1)
        elif args.x_command == "auth":
            from kairos.ingest.x.auth import run_pkce_auth_flow
            from kairos.ingest.x.auth_check import MINIMAL_SCOPES
            from kairos.ingest.x.client import XApiError

            scopes = args.scope
            if args.minimal_scopes:
                scopes = MINIMAL_SCOPES

            try:
                result = asyncio.run(
                    run_pkce_auth_flow(
                        args.env_file,
                        redirect_uri=args.redirect_uri,
                        scopes=scopes,
                        open_browser=not args.no_browser,
                        timeout=args.timeout,
                    )
                )
            except XApiError as exc:
                print(f"✗ OAuth failed: {exc}", file=sys.stderr)
                sys.exit(1)
            except TimeoutError as exc:
                print(f"✗ OAuth timed out: {exc}", file=sys.stderr)
                sys.exit(1)

            print("✓ OAuth authorization complete")
            print(f"  user_id:  {result.user_id}")
            if result.username:
                print(f"  username: @{result.username}")
            if result.tokens.expires_in is not None:
                print(f"  expires:  {result.tokens.expires_in}s")
            if result.tokens.scope:
                print(f"  scope:    {result.tokens.scope}")
            print(f"  updated:  {result.env_path.resolve()}")
            print(f"  keys:     {', '.join(result.keys_written)}")
        elif args.x_command == "refresh":
            from kairos.ingest.x.auth import refresh_tokens_to_env

            result = asyncio.run(
                refresh_tokens_to_env(args.env_file, dry_run=args.dry_run)
            )
            tokens = result.tokens
            print("✓ Token refresh OK")
            if tokens.expires_in is not None:
                print(f"  expires_in: {tokens.expires_in}s")
            if tokens.scope:
                print(f"  scope:      {tokens.scope}")
            if args.dry_run:
                print("  dry-run:    .env not modified")
                print(f"  access_token:  {tokens.access_token[:8]}...{tokens.access_token[-4:]}")
                if tokens.refresh_token:
                    rt = tokens.refresh_token
                    print(f"  refresh_token: {rt[:8]}...{rt[-4:]}")
            else:
                print(f"  updated:    {result.env_path.resolve()}")
                print(f"  keys:       {', '.join(result.keys_written)}")
        else:
            parser.print_help()
            sys.exit(1)
    elif args.command == "ingest":
        if args.ingest_command == "sync":
            from kairos.ingest.sync import sync_bookmarks_from_x

            result = asyncio.run(
                sync_bookmarks_from_x(
                    max_pages=args.max_pages,
                    enrich=not args.skip_enrich,
                    enrich_existing=args.enrich_existing,
                )
            )
            print(json.dumps(result.__dict__, indent=2))
            if result.errors:
                sys.exit(1)
        else:
            parser.print_help()
            sys.exit(1)
    elif args.command == "bookmarks":
        from kairos.bookmarks.cli import (
            fetch_bookmarks,
            format_bookmarks_json,
            format_bookmarks_table,
        )

        if args.bookmarks_command == "list":
            result = asyncio.run(fetch_bookmarks(limit=args.limit, skip=args.skip))
            print(format_bookmarks_json(result) if args.json else format_bookmarks_table(result))
            if result["total"] == 0:
                sys.exit(1)
        elif args.bookmarks_command == "get":
            result = asyncio.run(fetch_bookmarks(x_tweet_id=args.x_tweet_id))
            if not result["bookmarks"]:
                print(f"Bookmark not found: {args.x_tweet_id}", file=sys.stderr)
                sys.exit(1)
            if args.json:
                print(format_bookmarks_json(result))
            else:
                print(format_bookmarks_table(result))
        elif args.bookmarks_command == "enrich":
            from kairos.bookmarks.enrich import enrich_stored_bookmarks

            result = asyncio.run(
                enrich_stored_bookmarks(
                    limit=args.limit,
                    force=args.force,
                    dry_run=args.dry_run,
                    concurrency=args.concurrency,
                )
            )
            print(json.dumps(result.__dict__, indent=2))
            if result.errors:
                sys.exit(1)
        elif args.bookmarks_command == "embed":
            from kairos.bookmarks.index import embed_stored_bookmarks

            result = asyncio.run(
                embed_stored_bookmarks(limit=args.limit, force=args.force)
            )
            print(json.dumps(result.__dict__, indent=2))
            if result.errors:
                sys.exit(1)
        elif args.bookmarks_command == "cluster":
            from kairos.bookmarks.index import cluster_stored_bookmarks

            result = asyncio.run(
                cluster_stored_bookmarks(min_cluster_size=args.min_cluster_size)
            )
            print(json.dumps(result.__dict__, indent=2, default=str))
            if result.errors:
                sys.exit(1)
        elif args.bookmarks_command == "clusters":
            from kairos.bookmarks.index import fetch_cluster_catalog

            clusters = asyncio.run(fetch_cluster_catalog())
            clusters = clusters[: args.limit]
            if args.json:
                printable = []
                for cluster in clusters:
                    item = dict(cluster)
                    if item.get("_id"):
                        item["id"] = str(item.pop("_id"))
                    if item.get("last_updated") and hasattr(item["last_updated"], "isoformat"):
                        item["last_updated"] = item["last_updated"].isoformat()
                    printable.append(item)
                print(json.dumps(printable, indent=2))
            else:
                if not clusters:
                    print("No clusters — run: kairos bookmarks embed && kairos bookmarks cluster")
                    sys.exit(1)
                print(f"Clusters ({len(clusters)} shown)\n")
                for cluster in clusters:
                    name = cluster.get("name") or "(unnamed)"
                    count = cluster.get("member_count", 0)
                    summary = (cluster.get("summary") or "").replace("\n", " ")[:100]
                    cid = cluster.get("cluster_id") or "?"
                    print(f"{cid[:8]}…  {name} ({count})")
                    if summary:
                        print(f"  {summary}…")
                    print()
        else:
            parser.print_help()
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
