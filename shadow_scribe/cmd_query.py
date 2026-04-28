"""shadow_scribe.cmd_query — `watchdog query` (Phase 6 Lightweight Agentic RAG).

Implementation per ADR-006 + ADR-007:
- Stage 1: Sparse grep on INDEX_MATRIX (cheap-fast, ~50ms local)
- Stage 2: Gemini LLM rerank (smart-fallback) when grep is vague or too many hits
- Parent-Child Retrieval: child=INDEX row, parent=session log, grandparent=ADR
- Output: ASCII table (Date | Project | TL;DR | Link), does NOT dump file contents
"""

import sys
from typing import NamedTuple, Optional

from shadow_scribe.config import INDEX_FILE
from shadow_scribe.gemini import call_gemini_query
from shadow_scribe.io_utils import _split_md_row

TOP_N_DEFAULT = 5
TLDR_MAX = 50
LINK_MAX = 35
PROJECT_MAX = 18


class IndexRow(NamedTuple):
    """One row from INDEX_MATRIX (master index, 7 columns)."""
    date: str
    project: str
    workspace: str
    tldr: str
    session_link: str
    artifacts: str
    tags: str
    raw: str


def _parse_index_rows(content: str) -> list[IndexRow]:
    """Parse INDEX_MATRIX.md → list of IndexRow.

    Format: | Date | Project | Workspace | TL;DR | Session | Artifacts | Tags |
    Skips header, separator, and non-master rows (e.g., ADR sub-tables with 5 columns).
    """
    rows: list[IndexRow] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            continue
        if "---" in line:
            continue
        cells = _split_md_row(line)
        if len(cells) != 7:
            if 6 <= len(cells) <= 8:  # near-miss: likely malformed Gemini output
                print(f"⚠️  _parse_index_rows: skipped row with {len(cells)} cols (expected 7): {line[:60]!r}")
            continue
        if cells[0].lower() in ("ngày", "date"):
            continue
        rows.append(IndexRow(
            date=cells[0], project=cells[1], workspace=cells[2],
            tldr=cells[3], session_link=cells[4],
            artifacts=cells[5], tags=cells[6], raw=line,
        ))
    return rows


def _filter_rows(
    rows: list[IndexRow], keyword: str, project: Optional[str]
) -> list[IndexRow]:
    """Stage 1: case-insensitive keyword search + optional project filter."""
    keyword_lower = keyword.lower()
    hits = []
    for row in rows:
        if project and project.lower() not in row.project.lower():
            continue
        searchable = " ".join([
            row.tldr, row.project, row.tags, row.workspace, row.artifacts
        ]).lower()
        if keyword_lower in searchable:
            hits.append(row)
    return hits


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len - 1] + "…"


def _render_table(hits: list[IndexRow], top_n: int) -> str:
    """ASCII table: Date | Project | TL;DR | Link. Caps results at top_n."""
    if not hits:
        return "(no results found)"

    rows_to_show = hits[:top_n]
    date_w = 5
    project_w = min(PROJECT_MAX, max(7, max(len(r.project) for r in rows_to_show)))
    tldr_w = min(TLDR_MAX, max(10, max(len(r.tldr) for r in rows_to_show)))
    link_w = min(LINK_MAX, max(8, max(len(r.session_link) for r in rows_to_show)))

    sep = f"+{'-'*(date_w+2)}+{'-'*(project_w+2)}+{'-'*(tldr_w+2)}+{'-'*(link_w+2)}+"
    header = (
        f"| {'Date':<{date_w}} | {'Project':<{project_w}} | "
        f"{'TL;DR':<{tldr_w}} | {'Link':<{link_w}} |"
    )

    lines = [sep, header, sep]
    for r in rows_to_show:
        lines.append(
            f"| {_truncate(r.date, date_w):<{date_w}} | "
            f"{_truncate(r.project, project_w):<{project_w}} | "
            f"{_truncate(r.tldr, tldr_w):<{tldr_w}} | "
            f"{_truncate(r.session_link, link_w):<{link_w}} |"
        )
    lines.append(sep)
    return "\n".join(lines)


def _parse_gemini_rerank(result: str) -> list[IndexRow]:
    """Parse Gemini's rerank output (markdown rows) → IndexRow list."""
    parsed: list[IndexRow] = []
    for line in result.splitlines():
        line = line.strip()
        if not line.startswith("|") or "---" in line:
            continue
        cells = _split_md_row(line)
        if len(cells) != 7:
            continue
        if cells[0].lower() in ("ngày", "date"):
            continue
        parsed.append(IndexRow(
            date=cells[0], project=cells[1], workspace=cells[2],
            tldr=cells[3], session_link=cells[4],
            artifacts=cells[5], tags=cells[6], raw=line,
        ))
    return parsed


def cmd_query(
    keyword: str,
    project: Optional[str] = None,
    top: int = TOP_N_DEFAULT,
    smart: bool = False,
) -> None:
    """Lightweight Agentic RAG query on Vault INDEX_MATRIX.

    Stage 2 trigger: smart=True OR hits<2 OR hits>top.
    """
    if not INDEX_FILE.exists():
        print(f"❌ Index Matrix not found at {INDEX_FILE}")
        sys.exit(1)

    print("\n" + "═" * 60)
    print("🔍 SHADOW SCRIBE — Vault Query")
    print(f"   Keyword: {keyword!r}")
    if project:
        print(f"   Project filter: {project}")
    if smart:
        print("   Mode: --smart (force Stage 2)")
    print("═" * 60)

    content = INDEX_FILE.read_text(encoding="utf-8")
    rows = _parse_index_rows(content)

    if not rows:
        print("⚠️  INDEX_MATRIX is empty or has invalid format")
        sys.exit(1)

    hits = _filter_rows(rows, keyword, project)
    print(f"\n⚡ Stage 1 (Grep): {len(hits)} hit(s)")

    need_stage2 = smart or len(hits) < 2 or len(hits) > top

    if not need_stage2:
        print(_render_table(hits, top))
        print("═" * 60)
        return

    if smart:
        reason = "--smart flag (force)"
    elif len(hits) < 2:
        reason = f"grep < 2 hits ({len(hits)} found, keyword may be too vague)"
    else:
        reason = f"grep > top={top} ({len(hits)} found, needs reranking)"
    print(f"🧠 Stage 2 trigger: {reason}")

    rerank_raw = call_gemini_query(keyword, content).strip()
    if not rerank_raw:
        print("\n(Stage 2: Gemini returned no relevant results)")
        if hits:
            print("\n💡 Fallback Stage 1:")
            print(_render_table(hits, top))
        print("═" * 60)
        return

    reranked = _parse_gemini_rerank(rerank_raw)
    if project:
        reranked = [r for r in reranked if project.lower() in r.project.lower()]

    if reranked:
        print(f"\n💡 Stage 2 reranked: {len(reranked)} result(s)")
        print(_render_table(reranked, top))
    else:
        print("\n💡 Stage 2 raw (parser could not extract rows):")
        print(rerank_raw[:500])

    print("═" * 60)
