#!/usr/bin/env python3
"""Shadow Scribe v1.3.0 — Watchdog Agent for AI sessions.

Thin entry point: argparse only. All logic lives in shadow_scribe/ package.
"""
import argparse

from shadow_scribe.config import VERSION, load_env

load_env()  # Explicit — no side-effect on import

from shadow_scribe.cmd_audit import cmd_audit
from shadow_scribe.cmd_digest import cmd_digest
from shadow_scribe.cmd_query import cmd_query
from shadow_scribe.cmd_scribe import cmd_scribe


def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"Shadow Scribe v{VERSION} — Watchdog Agent for AI sessions"
    )
    subparsers = parser.add_subparsers(dest="command")

    # scribe (end-of-day, destructive)
    scribe_parser = subparsers.add_parser("scribe", help="End-of-day: write Session Log + update Index")
    scribe_parser.add_argument("--mock", action="store_true", help="Dry-run with mock data")

    # audit (mid-session, read-only)
    audit_parser = subparsers.add_parser("audit", help="Mid-session: check goal drift (read-only)")
    audit_parser.add_argument("--plan", default="", help="Path to implementation_plan.md")

    # digest (aggregate multiple sessions, project-filtered)
    digest_parser = subparsers.add_parser("digest", help="Aggregate digest by project")
    digest_parser.add_argument(
        "--project", default="",
        help="Filter by project (e.g., shadow-scribe, z-zero). Empty = all."
    )
    digest_parser.add_argument(
        "--last", type=int, default=0, metavar="N",
        help="Only include sessions from the last N days (e.g., --last 30). Empty = all."
    )

    # query (Phase 6 — Lightweight Agentic RAG)
    query_parser = subparsers.add_parser(
        "query", help="Quick search the Vault (Lightweight Agentic RAG)"
    )
    query_parser.add_argument("keyword", help="Keyword or question to search")
    query_parser.add_argument(
        "--project", default=None,
        help="Filter by project (e.g., shadow-scribe, z-zero). Empty = all."
    )
    query_parser.add_argument(
        "--top", type=int, default=5, metavar="N",
        help="Max number of results (default: 5)"
    )
    query_parser.add_argument(
        "--smart", action="store_true",
        help="Force Stage 2 LLM rerank (skip grep, go straight to Gemini)"
    )

    args = parser.parse_args()

    if args.command == "scribe":
        cmd_scribe(mock=args.mock)
    elif args.command == "audit":
        cmd_audit(plan_path_arg=args.plan)
    elif args.command == "digest":
        cmd_digest(project_filter=args.project, last_days=args.last)
    elif args.command == "query":
        cmd_query(
            keyword=args.keyword, project=args.project,
            top=args.top, smart=args.smart,
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
