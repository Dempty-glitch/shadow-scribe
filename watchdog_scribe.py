#!/usr/bin/env python3
"""Shadow Scribe v1.2.2 — Watchdog Agent for AI sessions.

Thin entry point: argparse only. All logic lives in shadow_scribe/ package.
"""
import argparse

from shadow_scribe.config import VERSION, load_env

load_env()  # Explicit — no side-effect on import

from shadow_scribe.cmd_audit import cmd_audit
from shadow_scribe.cmd_digest import cmd_digest
from shadow_scribe.cmd_scribe import cmd_scribe


def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"Shadow Scribe v{VERSION} — Watchdog Agent for AI sessions"
    )
    subparsers = parser.add_subparsers(dest="command")

    # scribe (cuối ngày, destructive)
    scribe_parser = subparsers.add_parser("scribe", help="Cuối ngày: ghi Session Log + cập nhật Index")
    scribe_parser.add_argument("--mock", action="store_true", help="Dry-run với mock data")

    # audit (giữa giờ, read-only)
    audit_parser = subparsers.add_parser("audit", help="Giữa giờ: soi goal drift (read-only)")
    audit_parser.add_argument("--plan", default="", help="Đường dẫn tới file implementation_plan.md")

    # digest (tổng hợp nhiều sessions, project-filtered)
    digest_parser = subparsers.add_parser("digest", help="Tổng hợp digest theo project")
    digest_parser.add_argument(
        "--project", default="",
        help="Filter theo project (vd: shadow-scribe, z-zero). Bỏ trống = tất cả."
    )
    digest_parser.add_argument(
        "--last", type=int, default=0, metavar="N",
        help="Chỉ lấy sessions trong N ngày gần nhất (vd: --last 30). Bỏ trống = tất cả."
    )

    args = parser.parse_args()

    if args.command == "scribe":
        cmd_scribe(mock=args.mock)
    elif args.command == "audit":
        cmd_audit(plan_path_arg=args.plan)
    elif args.command == "digest":
        cmd_digest(project_filter=args.project, last_days=args.last)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
