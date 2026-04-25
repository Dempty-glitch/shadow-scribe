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
