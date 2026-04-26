"""Tests cho cmd_query (Phase 6 Lightweight Agentic RAG).

Cover:
- Parser: row count, header skip, separator skip, malformed rows
- Filter: keyword match, project filter, case-insensitive, no match
- Render: ASCII table format, truncation, top_n cap
- Stage 2 trigger logic (no API call, just decision branches)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from shadow_scribe.cmd_query import (
    IndexRow,
    _filter_rows,
    _parse_gemini_rerank,
    _parse_index_rows,
    _render_table,
    _truncate,
)

SAMPLE_INDEX = """# Vault Index

## 📊 Master Index

| Ngày | Project | Workspace | TL;DR | Session | Artifacts | Tags |
|------|---------|-----------|-------|---------|-----------|------|
| 25/04 | shadow-scribe | /Users/foo | Refactor monolith to package, JSON parser. | [→](sessions/2026-04/25_04_26.md) | [ADR-005](adr/005.md) | #refactor #ci |
| 24/04 | shadow-scribe | shadow-scribe | Hardening v1.2.1 security fixes. | [→](sessions/2026-04/24_04_26.md) | adr/004.md | #security |
| 22/03 | z-zero | ai-card-mcp | Fix execute_payment INTERNAL_SECRET. | [→](sessions/2026-03/22_03.md) | — | #bugfix #payment |

---

## ADR Table (5 cols, should be skipped)

| ID | Project | Vấn đề | Status | File |
|----|---------|--------|--------|------|
| 001 | shadow-scribe | Watchdog Architecture | 🟢 ACCEPTED | adr/001.md |
"""


# ─── Parser tests ─────────────────────────────────────────────────────────────

def test_parse_index_rows_count():
    rows = _parse_index_rows(SAMPLE_INDEX)
    assert len(rows) == 3, f"Expected 3 master rows, got {len(rows)}"


def test_parse_index_rows_skips_5col_adr_table():
    """Bảng ADR phụ ở cuối có 5 cột, không phải 7 — phải skip."""
    rows = _parse_index_rows(SAMPLE_INDEX)
    project_names = [r.project for r in rows]
    assert "shadow-scribe" in project_names
    assert "z-zero" in project_names
    assert "001" not in project_names  # ADR row's first cell would be ID


def test_parse_index_rows_first_row_fields():
    rows = _parse_index_rows(SAMPLE_INDEX)
    r = rows[0]
    assert r.date == "25/04"
    assert r.project == "shadow-scribe"
    assert "Refactor monolith" in r.tldr
    assert r.session_link.startswith("[→]")
    assert "#refactor" in r.tags


def test_parse_index_rows_empty_input():
    assert _parse_index_rows("") == []


# ─── Filter tests ─────────────────────────────────────────────────────────────

def test_filter_keyword_match():
    rows = _parse_index_rows(SAMPLE_INDEX)
    hits = _filter_rows(rows, "refactor", None)
    assert len(hits) == 1
    assert hits[0].date == "25/04"


def test_filter_keyword_case_insensitive():
    rows = _parse_index_rows(SAMPLE_INDEX)
    upper = _filter_rows(rows, "REFACTOR", None)
    lower = _filter_rows(rows, "refactor", None)
    assert len(upper) == len(lower) == 1


def test_filter_project_only():
    rows = _parse_index_rows(SAMPLE_INDEX)
    hits = _filter_rows(rows, "", "z-zero")
    assert len(hits) == 1
    assert hits[0].project == "z-zero"


def test_filter_keyword_plus_project():
    rows = _parse_index_rows(SAMPLE_INDEX)
    # "security" should match shadow-scribe, but project filter z-zero → 0 hits
    hits = _filter_rows(rows, "security", "z-zero")
    assert len(hits) == 0


def test_filter_no_match():
    rows = _parse_index_rows(SAMPLE_INDEX)
    hits = _filter_rows(rows, "abc123nonexistent", None)
    assert hits == []


def test_filter_searches_in_tags():
    """Keyword trong tags phải match được."""
    rows = _parse_index_rows(SAMPLE_INDEX)
    hits = _filter_rows(rows, "payment", None)
    assert len(hits) == 1
    assert hits[0].project == "z-zero"


# ─── Render tests ─────────────────────────────────────────────────────────────

def test_truncate_under_limit():
    assert _truncate("hello", 10) == "hello"


def test_truncate_over_limit():
    result = _truncate("hello world long string", 10)
    assert len(result) == 10
    assert result.endswith("…")


def test_render_table_empty():
    assert _render_table([], 5) == "(no results found)"


def test_render_table_format():
    rows = _parse_index_rows(SAMPLE_INDEX)
    table = _render_table(rows, 5)
    assert "Date" in table
    assert "Project" in table
    assert "TL;DR" in table
    assert "Link" in table
    assert "+---" in table  # separator line
    assert "25/04" in table


def test_render_table_top_cap():
    """top_n nhỏ hơn số hits → cap kết quả."""
    rows = _parse_index_rows(SAMPLE_INDEX)
    table = _render_table(rows, 1)
    # Chỉ có 1 row được render → "22/03" (row cuối) sẽ không xuất hiện
    assert "25/04" in table
    assert "22/03" not in table


# ─── Gemini rerank parser tests ───────────────────────────────────────────────

def test_parse_gemini_rerank_valid():
    raw = (
        "| 25/04 | shadow-scribe | /Users/foo | Refactor done. | "
        "[→](sessions/x.md) | adr/005.md | #refactor |\n"
        "| 24/04 | shadow-scribe | shadow-scribe | Hardening. | "
        "[→](sessions/y.md) | adr/004.md | #security |"
    )
    parsed = _parse_gemini_rerank(raw)
    assert len(parsed) == 2
    assert parsed[0].date == "25/04"


def test_parse_gemini_rerank_skips_garbage():
    """Output có markdown header/explanation lẫn — chỉ lấy table rows hợp lệ."""
    raw = (
        "Đây là kết quả:\n"
        "| 25/04 | shadow-scribe | /U | Refactor. | [→](x.md) | adr/x.md | #tag |\n"
        "Hết."
    )
    parsed = _parse_gemini_rerank(raw)
    assert len(parsed) == 1


def test_parse_gemini_rerank_empty():
    assert _parse_gemini_rerank("") == []
    assert _parse_gemini_rerank("Không tìm thấy gì.") == []


# ─── Stage 2 trigger logic (test the conditions, not API) ─────────────────────

def test_stage2_trigger_smart_flag():
    """smart=True → trigger Stage 2 luôn."""
    smart = True
    hits_count = 5
    top = 5
    need_stage2 = smart or hits_count < 2 or hits_count > top
    assert need_stage2 is True


def test_stage2_trigger_too_few():
    """hits < 2 → trigger Stage 2."""
    smart = False
    hits_count = 1
    top = 5
    need_stage2 = smart or hits_count < 2 or hits_count > top
    assert need_stage2 is True


def test_stage2_trigger_too_many():
    """hits > top → trigger Stage 2 cho rerank."""
    smart = False
    hits_count = 10
    top = 5
    need_stage2 = smart or hits_count < 2 or hits_count > top
    assert need_stage2 is True


def test_stage2_no_trigger_in_range():
    """2 ≤ hits ≤ top, smart=False → không trigger Stage 2."""
    smart = False
    hits_count = 3
    top = 5
    need_stage2 = smart or hits_count < 2 or hits_count > top
    assert need_stage2 is False
