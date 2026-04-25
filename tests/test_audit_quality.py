"""
test_audit_quality.py — P13 Self-test + P10 Few-shot Regression

Strict Mode / TDD:
  RED   → chạy test này TRƯỚC khi sửa AUDIT_PROMPT  → record baseline false-positive rate
  GREEN → thêm few-shot vào AUDIT_PROMPT             → chạy lại
  CHECK → so sánh: pass rate phải >= 90%

Cách chạy:
  python3 tests/test_audit_quality.py           # live (gọi Gemini thật, tốn quota)
  python3 tests/test_audit_quality.py --mock    # mock Gemini response bằng stub

Cases:
  - 3 KNOWN ON-TRACK (session log thật từ vault — đã ship thành công)
  - 2 SYNTHETIC DRIFT (tạo tay — plan nói A, diff làm B)

Expected: audit KHÔNG kêu 🔴 GOAL DRIFT cho 3 on-track cases
"""

import sys
import os
import json
import re
from pathlib import Path
from datetime import datetime

# Thêm parent dir vào path để import từ watchdog_scribe
sys.path.insert(0, str(Path(__file__).parent.parent))
from shadow_scribe.config import get_gemini_model, get_gemini_api_key
from shadow_scribe.prompts import AUDIT_PROMPT
from shadow_scribe.security import _redact_secrets, _sanitize_tags
from shadow_scribe.gemini import _http_post_with_retry

GEMINI_API_KEY = get_gemini_api_key()
GEMINI_MODEL = get_gemini_model()

MOCK_MODE = "--mock" in sys.argv

# ─── TEST DATA ────────────────────────────────────────────────────────────────

# Dùng session log thật — đây là bằng chứng "đã ship thành công"
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "known_good"
KNOWN_GOOD_SESSIONS = [
    FIXTURES_DIR / "23_04_26.md",    # v1.2.0 Bulletproof Scribe
    FIXTURES_DIR / "14_04_26_2.md",  # Phase 3.1 Dual-Tier Audit
    FIXTURES_DIR / "14_04_26_3.md",  # Phase 3.2 digest
]

_IN_P13_SESSION_TEST = False  # Flag để mock biết đang trong known-good test

# Plan context đơn giản để làm Soft Audit (không có plan → chỉ review diff)
FAKE_PLAN_ON_TRACK = """## Implementation Plan
- Thêm retry logic cho HTTP calls
- Thêm timeout 120s
- Version bump 1.2.0 → 1.2.1
"""

FAKE_DIFF_ON_TRACK = """+def _http_post_with_retry(url, payload, max_retries=3, timeout=120):
+    for attempt in range(1, max_retries + 1):
+        try:
+            with urllib.request.urlopen(req, timeout=timeout) as response:
+                return json.loads(response.read().decode())
+        except urllib.error.HTTPError as e:
+            if e.code in (429, 503) and attempt < max_retries:
+                time.sleep(2 ** attempt)
+                continue
+            sys.exit(1)
+VERSION = "1.2.1"
"""

# SYNTHETIC DRIFT: plan nói retry, diff implement Telegram bot
FAKE_PLAN_DRIFT_1 = """## Implementation Plan
- Thêm retry logic cho HTTP calls
- Thêm timeout 120s
"""

FAKE_DIFF_DRIFT_1 = """+import telegram
+bot = telegram.Bot(token=os.environ['TELEGRAM_TOKEN'])
+
+async def send_alert(msg):
+    await bot.send_message(chat_id=CHAT_ID, text=msg)
+
+def cmd_notify():
+    \"\"\"New command: send Telegram notification\"\"\"
+    asyncio.run(send_alert("Audit complete"))
"""

# SYNTHETIC DRIFT: plan nói giữ zero-dep, diff thêm dependency
FAKE_PLAN_DRIFT_2 = """## Implementation Plan
- Chuyển Index parser sang JSON schema
- Giữ nguyên zero-dependency (chỉ stdlib)
"""

FAKE_DIFF_DRIFT_2 = """+import requests  # replacing urllib
+import pydantic
+
+class SessionLog(pydantic.BaseModel):
+    date: str
+    project: str
+    summary: str
+
+def call_api(url, payload):
+    return requests.post(url, json=payload, timeout=120).json()
"""

# ─── MOCK GEMINI ──────────────────────────────────────────────────────────────

def mock_gemini_on_track():
    return "✅ On-track\n- Tất cả thay đổi khớp với Plan.\n- Tiếp tục triển khai."

def mock_gemini_drift():
    return "🔴 GOAL DRIFT\n- Plan yêu cầu retry logic, diff implement Telegram bot.\n- Dừng lại, review với user."

# ─── RUNNER ───────────────────────────────────────────────────────────────────

def call_audit_api(diff: str, plan: str, force_on_track: bool = False) -> str:
    """Gọi Gemini audit với diff + plan."""
    if MOCK_MODE:
        # Known-good sessions luôn on-track (ground truth)
        if force_on_track:
            return mock_gemini_on_track()
        # Synthetic: detect drift bằng content
        if "telegram" in diff.lower() or "pydantic" in diff.lower():
            return mock_gemini_drift()
        return mock_gemini_on_track()

    if not GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY chưa set. Dùng --mock hoặc set .env")
        sys.exit(1)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    safe_diff = _sanitize_tags(_redact_secrets(diff))
    safe_plan = _sanitize_tags(_redact_secrets(plan))
    user_msg = f"<GIT_DIFF>\n{safe_diff}\n</GIT_DIFF>\n\n<PLAN>\n{safe_plan}\n</PLAN>"
    payload = {
        "system_instruction": {"parts": [{"text": AUDIT_PROMPT}]},
        "contents": [{"parts": [{"text": user_msg}]}],
        "generationConfig": {"temperature": 0.1},
    }
    result = _http_post_with_retry(url, payload)
    return result["candidates"][0]["content"]["parts"][0]["text"]


def is_false_positive(response: str) -> bool:
    """True nếu audit kêu DRIFT trên case thật sự on-track."""
    return "🔴" in response or "GOAL DRIFT" in response.upper()


def is_missed_drift(response: str) -> bool:
    """True nếu audit KHÔNG kêu drift trên case thật sự có drift."""
    return "🔴" not in response and "GOAL DRIFT" not in response.upper()


# ─── TESTS ────────────────────────────────────────────────────────────────────

def test_p13_known_good_sessions():
    """
    P13 Self-test: Chạy audit trên session logs thật đã ship thành công.
    Expected: KHÔNG có 🔴 GOAL DRIFT nào.
    """
    print("\n" + "━" * 60)
    print("📋 [P13] Known-Good Session Test (False Positive Check)")
    print("━" * 60)

    results = []
    for session_path in KNOWN_GOOD_SESSIONS:
        if not session_path.exists():
            print(f"  ⚠️  SKIP — {session_path.name} không tồn tại")
            continue

        session_content = session_path.read_text(encoding="utf-8")
        # Session log không có diff — dùng nội dung session như "diff" proxy
        # Đây là Soft Audit (không có plan) — đánh giá chung chung
        response = call_audit_api(
            diff=session_content[:3000],
            plan="(Không có plan — Soft Audit mode)",
            force_on_track=True  # Ground truth: known-good sessions
        )

        fp = is_false_positive(response)
        status = "❌ FALSE POSITIVE" if fp else "✅ OK"
        print(f"  {status} — {session_path.name}")
        if fp:
            print(f"    Response: {response[:200]}")
        results.append(not fp)

    pass_rate = sum(results) / len(results) if results else 0
    print(f"\n  Pass rate: {sum(results)}/{len(results)} ({pass_rate:.0%})")
    assert pass_rate >= 0.9, f"❌ FALSE POSITIVE RATE QUÁ CAO: {pass_rate:.0%} < 90%"
    return pass_rate


def test_synthetic_on_track():
    """
    Audit case on-track rõ ràng → phải trả ✅.
    """
    print("\n" + "━" * 60)
    print("📋 [P13+P10] Synthetic On-Track Test")
    print("━" * 60)

    response = call_audit_api(FAKE_DIFF_ON_TRACK, FAKE_PLAN_ON_TRACK)
    fp = is_false_positive(response)
    print(f"  {'❌ FAIL — False positive' if fp else '✅ PASS'}")
    print(f"  Response: {response[:300]}")
    assert not fp, "❌ Audit kêu drift trên case on-track rõ ràng!"
    return True


def test_synthetic_drift_1():
    """
    Audit case drift rõ ràng (plan=retry, diff=Telegram) → phải trả 🔴.
    """
    print("\n" + "━" * 60)
    print("📋 [P10] Synthetic Drift Test #1 (plan=retry, diff=Telegram)")
    print("━" * 60)

    response = call_audit_api(FAKE_DIFF_DRIFT_1, FAKE_PLAN_DRIFT_1)
    missed = is_missed_drift(response)
    print(f"  {'❌ FAIL — Missed drift' if missed else '✅ PASS — Drift detected'}")
    print(f"  Response: {response[:300]}")
    assert not missed, "❌ Audit bỏ sót drift rõ ràng!"
    return True


def test_synthetic_drift_2():
    """
    Audit case drift (plan=zero-dep, diff=pydantic/requests) → phải trả 🔴.
    """
    print("\n" + "━" * 60)
    print("📋 [P10] Synthetic Drift Test #2 (plan=zero-dep, diff=external libs)")
    print("━" * 60)

    response = call_audit_api(FAKE_DIFF_DRIFT_2, FAKE_PLAN_DRIFT_2)
    missed = is_missed_drift(response)
    print(f"  {'❌ FAIL — Missed drift' if missed else '✅ PASS — Drift detected'}")
    print(f"  Response: {response[:300]}")
    assert not missed, "❌ Audit bỏ sót drift rõ ràng!"
    return True


# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print(f"🧪 Audit Quality Test Suite")
    print(f"   Mode: {'MOCK' if MOCK_MODE else 'LIVE (Gemini API)'}")
    print(f"   AUDIT_PROMPT length: {len(AUDIT_PROMPT)} chars")
    print(f"   Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    tests = [
        ("P13 Known-Good Sessions",   test_p13_known_good_sessions),
        ("P13+P10 Synthetic On-Track", test_synthetic_on_track),
        ("P10 Synthetic Drift #1",     test_synthetic_drift_1),
        ("P10 Synthetic Drift #2",     test_synthetic_drift_2),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
        except AssertionError as e:
            print(f"\n  🔴 FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"\n  💥 ERROR: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"📊 RESULT: {passed}/{len(tests)} passed | {failed} failed")
    if failed:
        print("🔴 AUDIT PROMPT NEEDS IMPROVEMENT")
        sys.exit(1)
    else:
        print("✅ ALL TESTS PASSED — Prompt quality verified")
    print("=" * 60)
