"""shadow_scribe.cmd_list — `watchdog list` (deterministic catalog filter, no LLM).

Spec: vault/projects/shadow-scribe/plans/watchdog_list_spec.md
ADR-010: INDEX_MATRIX is single source of truth; derived views are command outputs.

Flags: --project (substring) --since (YYYY-MM-DD) --tag (substring) --top N
All flags = AND. No flags = list all (capped by --top).
"""

import sys
from typing import Optional

import shadow_scribe.config as _cfg
from shadow_scribe.cmd_query import IndexRow, _parse_index_rows, _render_table


def _filter_list_rows(
    rows: list[IndexRow],
    project: Optional[str],
    since: Optional[str],
    tag: Optional[str],
) -> list[IndexRow]:
    """Deterministic AND-filter on IndexRow list. No LLM, no grep scoring."""
    result = []
    for row in rows:
        if project and project.lower() not in row.project.lower():
            continue
        if tag and tag.lower() not in row.tags.lower():
            continue
        if since:
            # Date column is DD/MM, convert to YYYY-MM-DD for ISO compare
            try:
                dd, mm = row.date.split("/")[:2]
                row_iso = f"2026-{mm}-{dd}"  # vault started 2026; good enough for now
                if row_iso < since:
                    continue
            except (ValueError, IndexError):
                pass  # unparseable date → include row (lenient)
        result.append(row)
    return result


def cmd_list(
    project: Optional[str] = None,
    since: Optional[str] = None,
    tag: Optional[str] = None,
    top: int = 20,
) -> None:
    """Deterministic filter on INDEX_MATRIX — no Gemini, no cost, ~50ms."""
    index_file = _cfg.INDEX_FILE
    if not index_file.exists():
        print(f"❌ Index Matrix not found at {index_file}")
        sys.exit(1)

    content = index_file.read_text(encoding="utf-8")
    rows = _parse_index_rows(content)
    hits = _filter_list_rows(rows, project=project, since=since, tag=tag)

    print("\n" + "═" * 60)
    print("📋 SHADOW SCRIBE — Vault List")
    filters = []
    if project:
        filters.append(f"project={project!r}")
    if since:
        filters.append(f"since={since!r}")
    if tag:
        filters.append(f"tag={tag!r}")
    print(f"   Filters: {', '.join(filters) if filters else '(none)'}")
    print("═" * 60)

    print(_render_table(hits, top))
    print("═" * 60)
