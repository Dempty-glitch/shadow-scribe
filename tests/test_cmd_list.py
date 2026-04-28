"""Tests for watchdog list — deterministic catalog filter (no LLM).
Spec: vault/projects/shadow-scribe/plans/watchdog_list_spec.md
"""
import pytest
from shadow_scribe.cmd_list import cmd_list, _filter_list_rows


# ─── Fixtures ────────────────────────────────────────────────────────────────

_VALID_ROW_A = "| 01/04 | shadow-scribe | shadow scribe | Fix parser B1 B2 | [→](sessions/2026-04/01_04_26.md) | — | #bugfix #parser |"
_VALID_ROW_B = "| 15/04 | z-zero | ai-card | Build MCP server | [→](sessions/2026-04/15_04_26.md) | plan.md | #adr #build |"
_VALID_ROW_C = "| 28/04 | shadow-scribe | shadow scribe | ADR-010 catalog design | [→](sessions/2026-04/28_04_26.md) | adr010.md | #adr #architecture |"
_HEADER = "| Ngày | Project | Workspace | TL;DR | Session | Artifacts | Tags |"
_SEP = "|------|---------|-----------|-------|---------|-----------|------|"

SAMPLE_MATRIX = "\n".join([_HEADER, _SEP, _VALID_ROW_A, _VALID_ROW_B, _VALID_ROW_C])
EMPTY_MATRIX = "\n".join([_HEADER, _SEP])


# ─── _filter_list_rows unit tests ────────────────────────────────────────────

def test_filter_no_flags_returns_all():
    """No flags → all rows returned."""
    from shadow_scribe.cmd_query import _parse_index_rows
    rows = _parse_index_rows(SAMPLE_MATRIX)
    result = _filter_list_rows(rows, project=None, since=None, tag=None)
    assert len(result) == 3


def test_filter_project_substring():
    """--project shadow → only shadow-scribe rows."""
    from shadow_scribe.cmd_query import _parse_index_rows
    rows = _parse_index_rows(SAMPLE_MATRIX)
    result = _filter_list_rows(rows, project="shadow", since=None, tag=None)
    assert len(result) == 2
    assert all("shadow" in r.project.lower() for r in result)


def test_filter_project_case_insensitive():
    """--project SHADOW → same as --project shadow."""
    from shadow_scribe.cmd_query import _parse_index_rows
    rows = _parse_index_rows(SAMPLE_MATRIX)
    result = _filter_list_rows(rows, project="SHADOW", since=None, tag=None)
    assert len(result) == 2


def test_filter_tag_substring():
    """--tag adr → rows with #adr tag."""
    from shadow_scribe.cmd_query import _parse_index_rows
    rows = _parse_index_rows(SAMPLE_MATRIX)
    result = _filter_list_rows(rows, project=None, since=None, tag="adr")
    assert len(result) == 2
    assert all("adr" in r.tags.lower() for r in result)


def test_filter_and_logic():
    """--project shadow --tag adr → AND, not OR."""
    from shadow_scribe.cmd_query import _parse_index_rows
    rows = _parse_index_rows(SAMPLE_MATRIX)
    result = _filter_list_rows(rows, project="shadow", since=None, tag="adr")
    assert len(result) == 1  # only row C matches both
    assert "shadow" in result[0].project.lower()
    assert "adr" in result[0].tags.lower()


def test_filter_since_future():
    """--since 2099-01-01 → empty (no sessions that far)."""
    from shadow_scribe.cmd_query import _parse_index_rows
    rows = _parse_index_rows(SAMPLE_MATRIX)
    result = _filter_list_rows(rows, project=None, since="2099-01-01", tag=None)
    assert result == []


def test_filter_since_past_returns_all():
    """--since 2020-01-01 → all rows (all dates are after)."""
    from shadow_scribe.cmd_query import _parse_index_rows
    rows = _parse_index_rows(SAMPLE_MATRIX)
    result = _filter_list_rows(rows, project=None, since="2020-01-01", tag=None)
    assert len(result) == 3


def test_filter_since_excludes_unparseable_date():
    """Row with unparseable date (e.g. '1') must be excluded when --since active.

    Regression: previously such rows leaked through via silent except pass.
    """
    from shadow_scribe.cmd_query import _parse_index_rows
    bad_row = "| 1 | z-zero | ai-card | Wallet EOA notes | [Wallet EOA](artifacts/x.md) | — | #note |"
    matrix = "\n".join([_HEADER, _SEP, bad_row])
    rows = _parse_index_rows(matrix)
    result = _filter_list_rows(rows, project=None, since="2026-01-01", tag=None)
    assert result == []  # unparseable date → excluded when since filter active


def test_filter_since_reads_year_from_session_link():
    """Year must be parsed from session_link path, not hardcoded.

    Regression: year-bomb — hardcoded '2026' breaks --since in 2027+.
    A row from sessions/2027-03/... must be included by --since 2027-01-01.
    """
    from shadow_scribe.cmd_query import _parse_index_rows
    future_row = "| 15/03 | shadow-scribe | shadow scribe | Some 2027 work | [→](sessions/2027-03/15_03_27.md) | — | #build |"
    matrix = "\n".join([_HEADER, _SEP, future_row])
    rows = _parse_index_rows(matrix)
    # With hardcoded 2026: row_iso = "2026-03-15" < "2027-01-01" → wrongly excluded
    result = _filter_list_rows(rows, project=None, since="2027-01-01", tag=None)
    assert len(result) == 1  # must be INCLUDED (row is from 2027-03)


def test_filter_no_match():
    """--project foo → empty."""
    from shadow_scribe.cmd_query import _parse_index_rows
    rows = _parse_index_rows(SAMPLE_MATRIX)
    result = _filter_list_rows(rows, project="foo", since=None, tag=None)
    assert result == []


# ─── cmd_list integration tests ──────────────────────────────────────────────

def test_cmd_list_empty_matrix(tmp_path, capsys, monkeypatch):
    """Empty MATRIX (header + sep only) → '(no results)'."""
    import shadow_scribe.config as cfg
    index_file = tmp_path / "00_INDEX_MATRIX.md"
    index_file.write_text(EMPTY_MATRIX, encoding="utf-8")
    monkeypatch.setattr(cfg, "INDEX_FILE", index_file)

    cmd_list(project=None, since=None, tag=None, top=20)
    out = capsys.readouterr().out
    assert "(no results found)" in out


def test_cmd_list_renders_table(tmp_path, capsys, monkeypatch):
    """cmd_list with no flags renders table with all rows."""
    import shadow_scribe.config as cfg
    index_file = tmp_path / "00_INDEX_MATRIX.md"
    index_file.write_text(SAMPLE_MATRIX, encoding="utf-8")
    monkeypatch.setattr(cfg, "INDEX_FILE", index_file)

    cmd_list(project=None, since=None, tag=None, top=20)
    out = capsys.readouterr().out
    assert "shadow-scribe" in out
    assert "z-zero" in out


def test_cmd_list_project_filter(tmp_path, capsys, monkeypatch):
    """cmd_list --project z-zero → only z-zero row."""
    import shadow_scribe.config as cfg
    index_file = tmp_path / "00_INDEX_MATRIX.md"
    index_file.write_text(SAMPLE_MATRIX, encoding="utf-8")
    monkeypatch.setattr(cfg, "INDEX_FILE", index_file)

    cmd_list(project="z-zero", since=None, tag=None, top=20)
    out = capsys.readouterr().out
    assert "z-zero" in out
    assert "shadow-scribe" not in out


def test_cmd_list_top_cap(tmp_path, capsys, monkeypatch):
    """--top 1 → only 1 row in output."""
    import shadow_scribe.config as cfg
    index_file = tmp_path / "00_INDEX_MATRIX.md"
    index_file.write_text(SAMPLE_MATRIX, encoding="utf-8")
    monkeypatch.setattr(cfg, "INDEX_FILE", index_file)

    cmd_list(project=None, since=None, tag=None, top=1)
    out = capsys.readouterr().out
    # Only 1 data row between separators
    data_rows = [l for l in out.splitlines() if l.startswith("|") and "---" not in l and "Date" not in l and "Ngày" not in l]
    assert len(data_rows) == 1


def test_cmd_list_missing_index(tmp_path, monkeypatch):
    """Missing INDEX_FILE → sys.exit(1)."""
    import shadow_scribe.config as cfg
    monkeypatch.setattr(cfg, "INDEX_FILE", tmp_path / "nonexistent.md")
    with pytest.raises(SystemExit) as exc:
        cmd_list(project=None, since=None, tag=None, top=20)
    assert exc.value.code == 1
