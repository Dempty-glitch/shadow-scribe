"""Tests for Track B: _validate_index_row (B1) and _split_md_row (B2)."""
import pytest


_VALID_ROW = "| 28/04 | shadow-scribe | shadow scribe | Fix A3 Gemini guard | [→](sessions/2026-04/28_04_26.md) | plan.md | #bugfix |"

# ─── _validate_index_row tests (Track B — B1) ────────────────────────────────

def test_validate_index_row_valid():
    from shadow_scribe.gemini import _validate_index_row
    assert _validate_index_row(_VALID_ROW) is True

def test_validate_index_row_not_a_pipe_row():
    """Non-table line → False (not master row)."""
    from shadow_scribe.gemini import _validate_index_row
    assert _validate_index_row("## Heading") is False
    assert _validate_index_row("") is False
    assert _validate_index_row("just text") is False

def test_validate_index_row_separator():
    """Separator line |---|--- → False."""
    from shadow_scribe.gemini import _validate_index_row
    assert _validate_index_row("|------|---------|-----------|-------|---------|-----------|------|") is False

def test_validate_index_row_header_row():
    """Header row with 'Ngày'/'Date' → False (header, not data)."""
    from shadow_scribe.gemini import _validate_index_row
    assert _validate_index_row("| Ngày | Project | Workspace | TL;DR | Session | Artifacts | Tags |") is False
    assert _validate_index_row("| Date | Project | Workspace | TL;DR | Session | Artifacts | Tags |") is False

def test_validate_index_row_adr_5col():
    """ADR sub-table row (5-col) → False (not master row — lenient)."""
    from shadow_scribe.gemini import _validate_index_row
    assert _validate_index_row("| 001 | shadow-scribe | Watchdog Architecture | 🟢 ACCEPTED | [→](adr/001.md) |") is False

def test_validate_index_row_too_few_cols():
    """1-col placeholder '| index |' → False."""
    from shadow_scribe.gemini import _validate_index_row
    assert _validate_index_row("| index |") is False

def test_validate_index_row_too_many_cols():
    """8-col row (literal pipe in content) → False."""
    from shadow_scribe.gemini import _validate_index_row
    bad = "| 1 | —    | z-zero | — | Wallet EOA notes | — | [link](x.md) | #crypto #wallet |"
    assert _validate_index_row(bad) is False

def test_parse_output_invalid_row_exits():
    """parse_output with 1-col index_row → sys.exit (invariant violated)."""
    import json
    from shadow_scribe.gemini import parse_output
    raw = json.dumps({"session_log": "# Log", "index_row": "| index |"})
    with pytest.raises(SystemExit):
        parse_output(raw)

def test_parse_output_empty_row_exits():
    """parse_output with empty index_row → sys.exit (invariant violated)."""
    import json
    from shadow_scribe.gemini import parse_output
    raw = json.dumps({"session_log": "# Log", "index_row": ""})
    with pytest.raises(SystemExit):
        parse_output(raw)


# ─── _split_md_row tests (Track B — B2) ──────────────────────────────────────

def test_split_md_row_normal():
    """Normal 7-col row → 7 cells."""
    from shadow_scribe.io_utils import _split_md_row
    cells = _split_md_row(_VALID_ROW)
    assert len(cells) == 7
    assert cells[0] == "28/04"
    assert cells[1] == "shadow-scribe"

def test_split_md_row_escaped_pipe():
    r"""Cell with \| → pipe char preserved in that cell's content."""
    from shadow_scribe.io_utils import _split_md_row
    # 7 apparent pipes in content means 8 cells after split, but \| merges → 7 final cells
    row = r"| A \| B | C | D | E | F | G | H |"
    cells = _split_md_row(row)
    assert len(cells) == 7
    assert cells[0] == "A | B"
    assert cells[1] == "C"

def test_split_md_row_strips_whitespace():
    """Cells with extra spaces → stripped."""
    from shadow_scribe.io_utils import _split_md_row
    row = "|  hello  |  world  | a | b | c | d | e |"
    cells = _split_md_row(row)
    assert cells[0] == "hello"
    assert cells[1] == "world"

def test_split_md_row_null_byte_raises():
    """Input with null byte → AssertionError (defensive guard)."""
    from shadow_scribe.io_utils import _split_md_row
    with pytest.raises(AssertionError):
        _split_md_row("| col\x00with_null | b | c | d | e | f | g |")

def test_split_md_row_empty_cells():
    """Cells with '—' (dash placeholder) → preserved as-is."""
    from shadow_scribe.io_utils import _split_md_row
    row = "| 28/04 | z-zero | ai-card | — | — | — | #tag |"
    cells = _split_md_row(row)
    assert len(cells) == 7
    assert cells[3] == "—"

def test_split_md_row_no_surrounding_pipes():
    """Row without surrounding pipes → still splits correctly."""
    from shadow_scribe.io_utils import _split_md_row
    row = "a | b | c"
    cells = _split_md_row(row)
    assert "a" in cells
    assert "b" in cells
