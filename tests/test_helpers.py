import pytest
from shadow_scribe.security import _redact_secrets, _sanitize_tags, _filter_diff
from shadow_scribe.gemini import parse_output
from shadow_scribe.io_utils import _parse_session_date

# ─── security.py tests ────────────────────────────────────────────────────────

def test_redact_api_key():
    text = "Here is my key: GEMINI_API_KEY=AIzaSyA_bCdEfG1234567890 don't share it."
    redacted = _redact_secrets(text)
    assert "AIza" not in redacted
    assert "*****[REDACTED]*****" in redacted

def test_redact_github_token():
    text = "export GITHUB_TOKEN=ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ123456"
    redacted = _redact_secrets(text)
    assert "ghp_" not in redacted
    assert "*****[REDACTED]*****" in redacted

def test_redact_pem():
    text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----"
    redacted = _redact_secrets(text)
    assert "MIIEow" not in redacted
    assert "*****[REDACTED_PEM]*****" in redacted

def test_redact_clean_text():
    text = "Hello world, this is a normal log file."
    assert _redact_secrets(text) == text

def test_sanitize_tags():
    text = "<SESSION_BRIEF> content </SESSION_BRIEF> and <GIT_DIFF> diff </GIT_DIFF>"
    sanitized = _sanitize_tags(text)
    assert "<SESSION_BRIEF>" not in sanitized
    assert "＜SESSION_BRIEF＞ content ＜/SESSION_BRIEF＞" in sanitized
    assert "＜GIT_DIFF＞ diff ＜/GIT_DIFF＞" in sanitized

def test_sanitize_clean():
    text = "<div>html</div> is fine but not the reserved tags."
    assert _sanitize_tags(text) == text

def test_filter_diff_lockfile():
    diff = """diff --git a/package-lock.json b/package-lock.json
index 1234567..890abcd 100644
--- a/package-lock.json
+++ b/package-lock.json
@@ -1,3 +1,3 @@
 {
-  "version": "1.0.0"
+  "version": "1.0.1"
 }
diff --git a/main.py b/main.py
index 111..222 100644
--- a/main.py
+++ b/main.py
@@ -1 +1 @@
-print('A')
+print('B')
"""
    filtered = _filter_diff(diff)
    assert "package-lock.json" not in filtered
    assert "main.py" in filtered

def test_filter_diff_keeps_py():
    diff = """diff --git a/main.py b/main.py
+++ b/main.py
@@ -1 +1 @@
-A
+B"""
    assert "main.py" in _filter_diff(diff)

# ─── gemini.py tests ──────────────────────────────────────────────────────────

def test_parse_output_json():
    import json
    valid_row = "| 28/04 | shadow-scribe | shadow scribe | Fix A3 Gemini guard | [\u2192](sessions/2026-04/28_04_26.md) | plan.md | #bugfix |"
    raw = json.dumps({"session_log": "# Log", "index_row": valid_row})
    log, row = parse_output(raw)
    assert log == "# Log"
    assert row == valid_row

def test_parse_output_fence():
    import json
    valid_row = "| 28/04 | shadow-scribe | shadow scribe | Fix A3 Gemini guard | [\u2192](sessions/2026-04/28_04_26.md) | plan.md | #bugfix |"
    raw_json = json.dumps({"session_log": "# Log", "index_row": valid_row})
    raw = f"```json\n{raw_json}\n```"
    log, row = parse_output(raw)
    assert log == "# Log"
    assert row == valid_row

def test_parse_output_separator():
    valid_row = "| 28/04 | shadow-scribe | shadow scribe | Fix A3 Gemini guard | [\u2192](sessions/2026-04/28_04_26.md) | plan.md | #bugfix |"
    raw = f"# Session Log\n===INDEX===\n{valid_row}"
    log, row = parse_output(raw)
    assert log == "# Session Log"
    assert row == valid_row

def test_parse_output_broken():
    # Should exit or raise. Since it calls sys.exit(1), we catch SystemExit
    with pytest.raises(SystemExit):
        parse_output("Garbage data without separator or json")

def test_call_gemini_query_missing_parts(monkeypatch):
    """Regression: Gemini SAFETY block on Stage 2 rerank → return '' (graceful, ADR-006 fallback)."""
    import shadow_scribe.gemini as g
    monkeypatch.setattr(g, "get_gemini_api_key", lambda: "fake-key")
    monkeypatch.setattr(g, "_http_post_with_retry", lambda *a, **kw: {"candidates": [{"finishReason": "SAFETY"}]})
    result = g.call_gemini_query("abc123nonexistent", "| 01/01 | proj | tldr | link |")
    assert result == ""

# ─── _extract_text tests (Track A — A3) ───────────────────────────────────────

def test_extract_text_happy():
    """Normal Gemini response → returns text."""
    from shadow_scribe.gemini import _extract_text
    result = {"candidates": [{"content": {"parts": [{"text": "hello world"}]}, "finishReason": "STOP"}]}
    assert _extract_text(result) == "hello world"

def test_extract_text_no_candidates():
    """Empty candidates (quota/safety block at prompt level) → sys.exit."""
    from shadow_scribe.gemini import _extract_text
    with pytest.raises(SystemExit):
        _extract_text({"candidates": []})

def test_extract_text_no_candidates_key():
    """Missing candidates key entirely → sys.exit."""
    from shadow_scribe.gemini import _extract_text
    with pytest.raises(SystemExit):
        _extract_text({"promptFeedback": {"blockReason": "SAFETY"}})

def test_extract_text_no_parts():
    """Candidate exists but no parts (SAFETY finish) → sys.exit."""
    from shadow_scribe.gemini import _extract_text
    with pytest.raises(SystemExit):
        _extract_text({"candidates": [{"finishReason": "SAFETY", "safetyRatings": []}]})

def test_extract_text_empty_text():
    """Parts exist but text is empty string → returns '' (not exit)."""
    from shadow_scribe.gemini import _extract_text
    result = {"candidates": [{"content": {"parts": [{"text": ""}]}, "finishReason": "STOP"}]}
    assert _extract_text(result) == ""

def test_extract_text_fallback_no_candidates():
    """fallback set + no candidates → returns fallback, does NOT exit."""
    from shadow_scribe.gemini import _extract_text
    assert _extract_text({"candidates": []}, fallback="") == ""

def test_extract_text_fallback_no_parts():
    """fallback set + no parts → returns fallback, does NOT exit."""
    from shadow_scribe.gemini import _extract_text
    result = {"candidates": [{"finishReason": "SAFETY", "safetyRatings": []}]}
    assert _extract_text(result, fallback="") == ""

def test_extract_text_fallback_none_still_exits():
    """fallback=None (default) + no candidates → still sys.exit (fail loud)."""
    from shadow_scribe.gemini import _extract_text
    with pytest.raises(SystemExit):
        _extract_text({"candidates": []})

# ─── _positive_int tests (Track A — A2) ───────────────────────────────────────

def test_positive_int_valid():
    """Valid positive int → returns int."""
    from watchdog_scribe import _positive_int
    assert _positive_int("5") == 5
    assert _positive_int("1") == 1
    assert _positive_int("100") == 100

def test_positive_int_zero():
    """Zero → raises ArgumentTypeError."""
    import argparse
    from watchdog_scribe import _positive_int
    with pytest.raises(argparse.ArgumentTypeError):
        _positive_int("0")

def test_positive_int_negative():
    """Negative → raises ArgumentTypeError."""
    import argparse
    from watchdog_scribe import _positive_int
    with pytest.raises(argparse.ArgumentTypeError):
        _positive_int("-1")

def test_positive_int_not_a_number():
    """Non-numeric string → raises ValueError."""
    from watchdog_scribe import _positive_int
    with pytest.raises(ValueError):
        _positive_int("abc")

# ─── io_utils.py tests ────────────────────────────────────────────────────────

def test_parse_session_date():
    dt = _parse_session_date("14_04_26.md")
    assert dt is not None
    assert dt.year == 2026
    assert dt.month == 4
    assert dt.day == 14

def test_parse_session_date_bad():
    assert _parse_session_date("readme.md") is None
    assert _parse_session_date("invalid_format.md") is None

# ─── config.py tests ──────────────────────────────────────────────────────────

def test_get_lang_default_vi(monkeypatch):
    """No env var → default 'vi'."""
    monkeypatch.delenv("SHADOW_SCRIBE_LANG", raising=False)
    from shadow_scribe.config import get_lang
    assert get_lang() == "vi"

def test_get_lang_explicit_en(monkeypatch):
    """ENV=en → returns 'en'."""
    monkeypatch.setenv("SHADOW_SCRIBE_LANG", "en")
    from shadow_scribe.config import get_lang
    assert get_lang() == "en"

def test_get_lang_case_insensitive(monkeypatch):
    """ENV=EN (uppercase) → returns 'en'."""
    monkeypatch.setenv("SHADOW_SCRIBE_LANG", "EN")
    from shadow_scribe.config import get_lang
    assert get_lang() == "en"

def test_get_lang_invalid_falls_back(monkeypatch, capsys):
    """ENV=xyz → 'vi' + warning printed."""
    monkeypatch.setenv("SHADOW_SCRIBE_LANG", "xyz")
    from shadow_scribe.config import get_lang
    assert get_lang() == "vi"
    captured = capsys.readouterr()
    assert "Invalid SHADOW_SCRIBE_LANG" in captured.out

def test_call_gemini_uses_en_prompt_when_lang_en(monkeypatch):
    """Smoke test: ENV=en → EN prompt sent in payload."""
    import shadow_scribe.gemini as g
    monkeypatch.setenv("SHADOW_SCRIBE_LANG", "en")
    monkeypatch.setattr(g, "get_gemini_api_key", lambda: "fake-key")

    captured = {}
    def fake_http(url, payload):
        captured["payload"] = payload
        return {"candidates": [{"content": {"parts": [{"text": '{"session_log":"x","index_row":"y"}'}]}}]}
    monkeypatch.setattr(g, "_http_post_with_retry", fake_http)

    g.call_gemini("brief content", "diff content")
    sent_prompt = captured["payload"]["system_instruction"]["parts"][0]["text"]

    # Assert EN prompt selected
    assert "Mục tiêu" not in sent_prompt, "VN heading leaked into EN prompt"
    # Assert at least one EN keyword present
    assert any(kw in sent_prompt for kw in ["Objective", "Goal", "Decisions"]), "EN prompt missing expected headings"


# ─── _resolve_vault_dir tests ─────────────────────────────────────────────────

def test_resolve_vault_dir_default(monkeypatch):
    """No env var → default ~/Documents/agent_vault."""
    monkeypatch.delenv("SHADOW_SCRIBE_VAULT_DIR", raising=False)
    from shadow_scribe.config import _resolve_vault_dir
    result = _resolve_vault_dir()
    from pathlib import Path
    assert result == Path.home() / "Documents" / "agent_vault"


def test_resolve_vault_dir_override(monkeypatch, tmp_path):
    """ENV set → uses custom path."""
    custom = str(tmp_path / "custom_vault")
    monkeypatch.setenv("SHADOW_SCRIBE_VAULT_DIR", custom)
    from shadow_scribe.config import _resolve_vault_dir
    result = _resolve_vault_dir()
    from pathlib import Path
    assert result == Path(custom).resolve()


def test_resolve_vault_dir_tilde(monkeypatch):
    """ENV with ~ → expands to home dir."""
    monkeypatch.setenv("SHADOW_SCRIBE_VAULT_DIR", "~/my_vault")
    from shadow_scribe.config import _resolve_vault_dir
    result = _resolve_vault_dir()
    from pathlib import Path
    assert result == Path.home() / "my_vault"


def test_resolve_vault_dir_empty_string(monkeypatch):
    """ENV = empty string → treated as unset, uses default."""
    monkeypatch.setenv("SHADOW_SCRIBE_VAULT_DIR", "   ")
    from shadow_scribe.config import _resolve_vault_dir
    result = _resolve_vault_dir()
    from pathlib import Path
    assert result == Path.home() / "Documents" / "agent_vault"


# ─── get_gemini_model allowlist tests ─────────────────────────────────────────

def test_gemini_model_default(monkeypatch):
    """No env var → gemini-2.5-flash."""
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    from shadow_scribe.config import get_gemini_model
    assert get_gemini_model() == "gemini-2.5-flash"


def test_gemini_model_allowed_pro(monkeypatch):
    """ENV=gemini-2.5-pro → accepted (in allowlist)."""
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-pro")
    from shadow_scribe.config import get_gemini_model
    assert get_gemini_model() == "gemini-2.5-pro"


def test_gemini_model_allowed_flash(monkeypatch):
    """ENV=gemini-2.5-flash → accepted (in allowlist)."""
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
    from shadow_scribe.config import get_gemini_model
    assert get_gemini_model() == "gemini-2.5-flash"


def test_gemini_model_rejected_leaked(monkeypatch):
    """ENV=gemini-3.1-pro (leaked from IDE) → rejected, fallback to flash."""
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.1-pro")
    from shadow_scribe.config import get_gemini_model
    assert get_gemini_model() == "gemini-2.5-flash"


def test_gemini_model_rejected_garbage(monkeypatch):
    """ENV=random-garbage → rejected, fallback to flash."""
    monkeypatch.setenv("GEMINI_MODEL", "gpt-4o-mini")
    from shadow_scribe.config import get_gemini_model
    assert get_gemini_model() == "gemini-2.5-flash"


# ─── _fix_index_row_path tests (Bug A — session collision path mismatch) ──────

def test_fix_index_row_path_no_collision():
    """No collision (base == actual) → index_row unchanged."""
    from shadow_scribe.cmd_scribe import _fix_index_row_path
    row = "| 28/04 | shadow-scribe | ws | TL;DR | [→](sessions/2026-04/28_04_26.md) | — | #tag |"
    result = _fix_index_row_path(row, "28_04_26.md", "28_04_26.md", "2026", "04")
    assert result == row


def test_fix_index_row_path_collision_suffix():
    """Collision (suffix _1) → index_row path updated to match actual file."""
    from shadow_scribe.cmd_scribe import _fix_index_row_path
    row = "| 28/04 | shadow-scribe | ws | TL;DR | [→](sessions/2026-04/28_04_26.md) | — | #tag |"
    result = _fix_index_row_path(row, "28_04_26.md", "28_04_26_1.md", "2026", "04")
    assert "28_04_26_1.md" in result
    assert "28_04_26.md)" not in result


def test_fix_index_row_path_no_match_in_row():
    """Edge: index_row doesn't contain expected path pattern → return unchanged, no crash."""
    from shadow_scribe.cmd_scribe import _fix_index_row_path
    row = "| 28/04 | proj | ws | TL;DR | [→](somewhere/else.md) | — | #tag |"
    result = _fix_index_row_path(row, "28_04_26.md", "28_04_26_1.md", "2026", "04")
    assert result == row



# ─── sync_file_if_differ tests (KI-003 GUIDE auto-sync) ───────────────────────

def test_sync_file_if_differ_creates_dest_when_missing(tmp_path):
    """Dest doesn't exist → copy source, return True."""
    from shadow_scribe.io_utils import sync_file_if_differ
    src = tmp_path / "src.md"
    dest = tmp_path / "subdir" / "dest.md"
    src.write_text("hello", encoding="utf-8")
    assert sync_file_if_differ(src, dest) is True
    assert dest.read_text(encoding="utf-8") == "hello"


def test_sync_file_if_differ_overwrites_when_content_differs(tmp_path):
    """Dest exists but differs → overwrite with source, return True."""
    from shadow_scribe.io_utils import sync_file_if_differ
    src = tmp_path / "src.md"
    dest = tmp_path / "dest.md"
    src.write_text("new content", encoding="utf-8")
    dest.write_text("old content", encoding="utf-8")
    assert sync_file_if_differ(src, dest) is True
    assert dest.read_text(encoding="utf-8") == "new content"


def test_sync_file_if_differ_noop_when_match(tmp_path):
    """Dest matches source → no write, return False."""
    from shadow_scribe.io_utils import sync_file_if_differ
    src = tmp_path / "src.md"
    dest = tmp_path / "dest.md"
    src.write_text("same", encoding="utf-8")
    dest.write_text("same", encoding="utf-8")
    assert sync_file_if_differ(src, dest) is False


def test_sync_file_if_differ_silent_when_source_missing(tmp_path):
    """Source missing → no-op, return False, no exception."""
    from shadow_scribe.io_utils import sync_file_if_differ
    src = tmp_path / "missing.md"
    dest = tmp_path / "dest.md"
    assert sync_file_if_differ(src, dest) is False
    assert not dest.exists()


# ─── sync_dir_if_differ tests (KI-006 adr/ auto-sync) ─────────────────────────

def test_sync_dir_creates_dest_when_missing(tmp_path):
    """Dest dir missing → copy all matching files, return count."""
    from shadow_scribe.io_utils import sync_dir_if_differ
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    (src / "001.md").write_text("one", encoding="utf-8")
    (src / "002.md").write_text("two", encoding="utf-8")

    assert sync_dir_if_differ(src, dest) == 2
    assert (dest / "001.md").read_text(encoding="utf-8") == "one"
    assert (dest / "002.md").read_text(encoding="utf-8") == "two"


def test_sync_dir_overwrites_when_content_differs(tmp_path):
    """Only differing files are overwritten and counted."""
    from shadow_scribe.io_utils import sync_dir_if_differ
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    dest.mkdir()
    (src / "001.md").write_text("new", encoding="utf-8")
    (dest / "001.md").write_text("old", encoding="utf-8")

    assert sync_dir_if_differ(src, dest) == 1
    assert (dest / "001.md").read_text(encoding="utf-8") == "new"


def test_sync_dir_noop_when_all_match(tmp_path):
    """All files identical → no writes, return 0."""
    from shadow_scribe.io_utils import sync_dir_if_differ
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    dest.mkdir()
    (src / "001.md").write_text("same", encoding="utf-8")
    (dest / "001.md").write_text("same", encoding="utf-8")

    assert sync_dir_if_differ(src, dest) == 0


def test_sync_dir_silent_when_source_missing(tmp_path):
    """Missing source dir → no-op, return 0, no exception."""
    from shadow_scribe.io_utils import sync_dir_if_differ
    src = tmp_path / "missing"
    dest = tmp_path / "dest"

    assert sync_dir_if_differ(src, dest) == 0
    assert not dest.exists()


def test_sync_dir_additive_only(tmp_path):
    """Extra dst files not present in src are left untouched."""
    from shadow_scribe.io_utils import sync_dir_if_differ
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    dest.mkdir()
    (src / "001.md").write_text("one", encoding="utf-8")
    (dest / "extra.md").write_text("vault draft", encoding="utf-8")

    assert sync_dir_if_differ(src, dest) == 1
    assert (dest / "001.md").read_text(encoding="utf-8") == "one"
    assert (dest / "extra.md").read_text(encoding="utf-8") == "vault draft"
