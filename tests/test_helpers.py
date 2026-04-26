import pytest
from datetime import datetime
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
    raw = json.dumps({"session_log": "# Log", "index_row": "| index |"})
    log, row = parse_output(raw)
    assert log == "# Log"
    assert row == "| index |"

def test_parse_output_fence():
    import json
    raw_json = json.dumps({"session_log": "# Log", "index_row": "| index |"})
    raw = f"```json\n{raw_json}\n```"
    log, row = parse_output(raw)
    assert log == "# Log"
    assert row == "| index |"

def test_parse_output_separator():
    raw = "# Session Log\n===INDEX===\n| index |"
    log, row = parse_output(raw)
    assert log == "# Session Log"
    assert row == "| index |"

def test_parse_output_broken():
    # Should exit or raise. Since it calls sys.exit(1), we catch SystemExit
    with pytest.raises(SystemExit):
        parse_output("Garbage data without separator or json")

def test_call_gemini_query_missing_parts(monkeypatch):
    """Regression: Gemini returns response without 'parts' (e.g. SAFETY block) → return '' not crash."""
    import shadow_scribe.gemini as g
    monkeypatch.setattr(g, "get_gemini_api_key", lambda: "fake-key")
    monkeypatch.setattr(g, "_http_post_with_retry", lambda *a, **kw: {"candidates": [{"finishReason": "SAFETY"}]})
    result = g.call_gemini_query("abc123nonexistent", "| 01/01 | proj | tldr | link |")
    assert result == ""

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
