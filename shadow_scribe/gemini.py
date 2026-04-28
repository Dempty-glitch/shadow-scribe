"""shadow_scribe.gemini — HTTP client, Gemini API call, output parser."""

import json
import re
import sys
import time
import urllib.error
import urllib.request
from typing import Optional


from shadow_scribe.config import get_gemini_api_key, get_gemini_model, get_lang
from shadow_scribe.prompts import (
    SYSTEM_PROMPT_VI, SYSTEM_PROMPT_EN,
    HARD_AUDIT_INSTRUCTION_VI, HARD_AUDIT_INSTRUCTION_EN,
    AUDIT_PROMPT_VI, AUDIT_PROMPT_EN,
    QUERY_PROMPT_VI, QUERY_PROMPT_EN
)
from shadow_scribe.security import _redact_secrets, _sanitize_tags


# ─── HTTP with retry ──────────────────────────────────────────────────────────

def _http_post_with_retry(
    url: str, payload: dict, max_retries: int = 3, timeout: int = 120
) -> dict:
    """POST JSON with timeout and retry (exponential backoff)."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

    for attempt in range(1, max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            if e.code in (429, 500, 502, 503) and attempt < max_retries:
                wait = 2 ** attempt
                print(f"⚠️  HTTP {e.code} — retry {attempt}/{max_retries} in {wait}s...")
                time.sleep(wait)
                continue
            print(f"❌ API Error: {e.code} {e.reason}")
            print(error_body)
            sys.exit(1)
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < max_retries:
                wait = 2 ** attempt
                print(f"⚠️  Network error — retry {attempt}/{max_retries} in {wait}s...")
                time.sleep(wait)
                continue
            print(f"❌ Connection failed after {max_retries} attempts: {e}")
            sys.exit(1)

    # Should never reach here, but satisfy type checker
    sys.exit(1)


# ─── Gemini response extractor ────────────────────────────────────────────────

def _extract_text(result: dict, fallback: Optional[str] = None) -> str:
    """Safely extract text from Gemini response.

    If fallback is None (default): exit cleanly on SAFETY/missing parts (fail loud).
    If fallback is set (e.g. ""): return fallback instead of exiting — for graceful
    degradation paths like call_gemini_query (Stage 2 rerank, ADR-006).
    """
    candidates = result.get("candidates", [])
    if not candidates:
        if fallback is not None:
            return fallback
        print("❌ Gemini returned no candidates (likely SAFETY block or quota)")
        print(f"   promptFeedback: {result.get('promptFeedback', {})}")
        sys.exit(1)

    cand = candidates[0]
    finish_reason = cand.get("finishReason", "UNKNOWN")
    parts = cand.get("content", {}).get("parts", [])

    if not parts:
        if fallback is not None:
            return fallback
        print(f"❌ Gemini response has no parts (finishReason={finish_reason})")
        print(f"   safetyRatings: {cand.get('safetyRatings', [])}")
        sys.exit(1)

    return parts[0].get("text", "")


# ─── Index row validator (B1) ────────────────────────────────────────────────

def _validate_index_row(row: str) -> bool:
    """Validate a candidate index_row string from Gemini output.

    Rules (lenient by design — only enforces master row format):
    - Must start and end with '|'
    - Must have exactly 7 cells (split by '|' yields 9 parts: 2 empty edge + 7 cells)
    - First cell must not be a header label ('date', 'ngày')
    - Returns False for empty/non-table strings (caller decides what to do)

    NOT intended to audit the full vault — only validates Gemini output
    before writing to INDEX_MATRIX. Non-7-col rows (ADR sub-tables etc.)
    are not master rows and are correctly rejected here.
    """
    if not row or not row.startswith("|") or not row.endswith("|"):
        return False
    cells = [c.strip() for c in row.split("|")]
    # cells[0] and cells[-1] are empty strings from leading/trailing '|'
    if len(cells) != 9:  # 2 empty edges + 7 content cells
        return False
    # Reject separator lines: |---|---|---|
    if all(re.match(r'^-+$', c) for c in cells[1:-1] if c):
        return False
    first_cell = cells[1].lower()
    if first_cell in ("date", "ngày", "id"):
        return False  # header row, not a data row
    return True


# ─── Output parser (3-layer: JSON → strip fence → separator fallback) ─────────

def parse_output(raw: str) -> tuple[str, str]:
    """Split Gemini output into (session_log, index_row).

    Layer 1: Pure JSON (response_mime_type enforced)
    Layer 2: Strip code fence → JSON
    Layer 3: ===INDEX=== separator (backward compat)
    """
    # Layer 1: Pure JSON
    try:
        data = json.loads(raw)
        log = data.get("session_log", "").strip()
        row = data.get("index_row", "").strip()
        if log:
            if not row:
                print("❌ parse_output: index_row is empty (invariant violated — session log must have index entry)")
                sys.exit(1)
            if not _validate_index_row(row):
                print("❌ parse_output: index_row is not a valid 7-column master row:")
                print(f"   Got: {row!r}")
                sys.exit(1)
            return log, row
    except (json.JSONDecodeError, KeyError, AttributeError):
        pass

    # Layer 2: Strip code fence → JSON
    stripped = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw.strip())
    try:
        data = json.loads(stripped)
        log = data.get("session_log", "").strip()
        row = data.get("index_row", "").strip()
        if log:
            if not row:
                print("❌ parse_output: index_row is empty (invariant violated — session log must have index entry)")
                sys.exit(1)
            if not _validate_index_row(row):
                print("❌ parse_output: index_row is not a valid 7-column master row:")
                print(f"   Got: {row!r}")
                sys.exit(1)
            return log, row
    except (json.JSONDecodeError, KeyError, AttributeError):
        pass

    # Layer 3: Separator fallback (backward compat v1.2.1)
    separator = "===INDEX==="
    if separator not in raw:
        print("❌ Gemini returned invalid format — missing ===INDEX===")
        print("─── RAW OUTPUT ───")
        print(raw)
        sys.exit(1)

    parts = raw.split(separator, 1)
    session_log = parts[0].strip()
    index_row = parts[1].strip()

    # Check Part 2 has exactly 1 table line
    index_lines = [line for line in index_row.splitlines() if line.strip()]
    if len(index_lines) != 1:
        print(f"⚠️  Part 2 has {len(index_lines)} lines instead of 1. Taking first line starting with |")
        index_row = next((line for line in index_lines if line.startswith("|")), index_lines[0])

    # Validate index_row (same invariant as JSON layers)
    if not index_row:
        print("❌ parse_output: index_row is empty (invariant violated — session log must have index entry)")
        sys.exit(1)
    if not _validate_index_row(index_row):
        print("❌ parse_output: index_row is not a valid 7-column master row:")
        print(f"   Got: {index_row!r}")
        sys.exit(1)

    return session_log, index_row


# ─── Gemini API call ──────────────────────────────────────────────────────────

def call_gemini(brief: str, diff: str, plan: str = "") -> str:
    """Call Gemini HTTP API directly (bypasses SDK) to avoid Python namespace errors."""
    api_key = get_gemini_api_key()
    model = get_gemini_model()
    lang = get_lang()

    system_prompt = SYSTEM_PROMPT_EN if lang == "en" else SYSTEM_PROMPT_VI
    hard_audit_instruction = HARD_AUDIT_INSTRUCTION_EN if lang == "en" else HARD_AUDIT_INSTRUCTION_VI

    if not api_key:
        print("❌ GEMINI_API_KEY is not set.")
        print("   Add it to: ~/Documents/agent_vault/.env")
        print("   Format:    GEMINI_API_KEY=your_key_here")
        print("   Get a key: https://aistudio.google.com/")
        sys.exit(1)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    safe_brief = _sanitize_tags(_redact_secrets(brief))
    safe_diff = _sanitize_tags(_redact_secrets(diff))

    user_message = f"<SESSION_BRIEF>\n{safe_brief}\n</SESSION_BRIEF>\n\n<GIT_DIFF>\n{safe_diff}\n</GIT_DIFF>"

    if plan:
        print("🔍 Activated [Hard Audit] - Loading Implementation Plan into verification memory.")
        safe_plan = _sanitize_tags(_redact_secrets(plan))
        user_message += f"\n\n<PLAN>\n{safe_plan}\n</PLAN>"
        user_message += hard_audit_instruction
    else:
        print("🔍 Activated [Soft Audit] - No Plan found.")

    payload = {
        "system_instruction": {
            "parts": [{"text": system_prompt}]
        },
        "contents": [
            {
                "parts": [{"text": user_message}]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "response_mime_type": "application/json",
        }
    }

    print(f"🤖 Calling Gemini via HTTP ({model})...")
    result = _http_post_with_retry(url, payload)
    return _extract_text(result)


def call_gemini_audit(diff: str, plan: str) -> str:
    """Call Gemini with AUDIT_PROMPT (read-only, no file writes)."""
    api_key = get_gemini_api_key()
    model = get_gemini_model()
    lang = get_lang()

    audit_prompt = AUDIT_PROMPT_EN if lang == "en" else AUDIT_PROMPT_VI

    if not api_key:
        print("❌ GEMINI_API_KEY is not set.")
        sys.exit(1)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    safe_diff = _sanitize_tags(_redact_secrets(diff))
    user_msg = f"<GIT_DIFF>\n{safe_diff}\n</GIT_DIFF>"
    if plan:
        safe_plan = _sanitize_tags(_redact_secrets(plan))
        user_msg += f"\n\n<PLAN>\n{safe_plan}\n</PLAN>"

    payload = {
        "system_instruction": {"parts": [{"text": audit_prompt}]},
        "contents": [{"parts": [{"text": user_msg}]}],
        "generationConfig": {"temperature": 0.1},
    }

    print("🤖 Running audit...")
    result = _http_post_with_retry(url, payload)
    return _extract_text(result)


def call_gemini_query(keyword: str, index_content: str) -> str:
    """Stage 2 LLM rerank for `watchdog query` (Phase 6).

    Sends keyword + full INDEX_MATRIX to Gemini, returns top relevant rows.
    Reuses security pipeline (redact + sanitize) from Phase 3.4.
    """
    api_key = get_gemini_api_key()
    model = get_gemini_model()
    lang = get_lang()

    query_prompt = QUERY_PROMPT_EN if lang == "en" else QUERY_PROMPT_VI

    if not api_key:
        print("❌ GEMINI_API_KEY is not set.")
        sys.exit(1)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    safe_keyword = _sanitize_tags(_redact_secrets(keyword))
    safe_index = _sanitize_tags(_redact_secrets(index_content))

    user_msg = (
        f"<QUERY>\n{safe_keyword}\n</QUERY>\n\n"
        f"<INDEX_MATRIX>\n{safe_index}\n</INDEX_MATRIX>"
    )

    payload = {
        "system_instruction": {"parts": [{"text": query_prompt}]},
        "contents": [{"parts": [{"text": user_msg}]}],
        "generationConfig": {"temperature": 0.1},
    }

    print(f"🤖 Stage 2: Gemini semantic rerank ({model})...")
    result = _http_post_with_retry(url, payload)
    return _extract_text(result, fallback="")
