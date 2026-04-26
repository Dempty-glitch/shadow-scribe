"""shadow_scribe.cmd_digest — `watchdog digest` command."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

from shadow_scribe.config import (
    SESSIONS_DIR,
    VAULT_DIR,
    get_gemini_api_key,
    get_gemini_model,
)
from shadow_scribe.gemini import _http_post_with_retry
from shadow_scribe.io_utils import _parse_project_from_log, _parse_session_date
from shadow_scribe.prompts import DIGEST_PROMPT
from shadow_scribe.security import _redact_secrets, _sanitize_tags

DIGEST_SESSIONS_DIR = SESSIONS_DIR
DIGESTS_OUTPUT_DIR = VAULT_DIR / "digests"


def cmd_digest(project_filter: str = "", last_days: int = 0) -> None:
    """Aggregate N session logs into 1 digest per project."""
    print("\n" + "═" * 60)
    print("📊 SHADOW SCRIBE — Digest Engine")
    if project_filter:
        print(f"   Filter: project={project_filter}")
    if last_days:
        print(f"   Filter: last {last_days} days")
    print("═" * 60)

    # 1. Collect all session files
    all_session_files: list[tuple[datetime, Path]] = []
    if not DIGEST_SESSIONS_DIR.exists():
        print(f"❌ Sessions dir not found: {DIGEST_SESSIONS_DIR}")
        sys.exit(1)

    for month_dir in sorted(DIGEST_SESSIONS_DIR.iterdir()):
        if not month_dir.is_dir():
            continue
        for f in sorted(month_dir.iterdir()):
            if f.suffix != ".md":
                continue
            dt = _parse_session_date(f.name)
            if dt is None:
                continue
            all_session_files.append((dt, f))

    all_session_files.sort(key=lambda x: x[0])

    if not all_session_files:
        print("⚠️  No sessions found in vault.")
        sys.exit(0)

    # 2. Filter by --last
    if last_days > 0:
        cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff -= timedelta(days=last_days)
        all_session_files = [(dt, f) for (dt, f) in all_session_files if dt >= cutoff]

    if not all_session_files:
        print(f"⚠️  No sessions found in the last {last_days} days.")
        sys.exit(0)

    # 3. Read content + filter by --project
    matched: list[tuple[datetime, Path, str]] = []
    skipped = 0
    for dt, f in all_session_files:
        try:
            content = f.read_text(encoding="utf-8")
        except Exception:
            skipped += 1
            continue

        if project_filter:
            proj = _parse_project_from_log(content)
            if proj != project_filter.lower():
                skipped += 1
                continue

        matched.append((dt, f, content))

    if not matched:
        filter_info = f"project='{project_filter}'" if project_filter else "all"
        print(f"⚠️  No sessions match filter [{filter_info}].")
        if skipped:
            print(f"   (Skipped {skipped} non-matching sessions)")
        sys.exit(0)

    print(f"✅ Found {len(matched)} matching sessions (skipped {skipped})")

    # 4. Concatenate sessions, truncate if too large
    MAX_CHARS = 900_000  # ~900K chars to fit Gemini 1M context
    parts = []
    total_chars = 0
    truncated_at = None

    for i, (dt, f, content) in enumerate(matched):
        entry = f"---SESSION--- [{dt.strftime('%d/%m/%Y')}] {f.name}\n{content}"
        if total_chars + len(entry) > MAX_CHARS:
            truncated_at = i
            print(f"⚠️  Truncated at session {i+1}/{len(matched)} to fit Gemini 1M context.")
            break
        parts.append(entry)
        total_chars += len(entry)

    combined = "\n\n".join(parts)

    date_range = (
        f"{matched[0][0].strftime('%d/%m/%Y')} → "
        f"{matched[min(len(matched)-1, len(parts)-1)][0].strftime('%d/%m/%Y')}"
    )
    proj_label = project_filter if project_filter else "all-projects"
    print(f"   Date range: {date_range}")
    print(f"   Total chars: {total_chars:,}\n")

    # 5. Call Gemini
    api_key = get_gemini_api_key()
    model = get_gemini_model()

    if not api_key:
        print("❌ GEMINI_API_KEY is not set.")
        sys.exit(1)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    safe_combined = _sanitize_tags(_redact_secrets(combined))
    user_msg = (
        f"Project filter: {proj_label}\n"
        f"Date range: {date_range}\n"
        f"Sessions count: {len(parts)}\n\n"
        f"<SESSION_LOGS>\n{safe_combined}\n</SESSION_LOGS>"
    )

    payload = {
        "system_instruction": {"parts": [{"text": DIGEST_PROMPT}]},
        "contents": [{"parts": [{"text": user_msg}]}],
        "generationConfig": {"temperature": 0.2},
    }

    print("🤖 Aggregating digest...")
    result_json = _http_post_with_retry(url, payload)
    digest_text = result_json["candidates"][0]["content"]["parts"][0]["text"].strip()

    # 6. Print to terminal
    print("\n" + "═" * 60)
    print("📊 DIGEST OUTPUT:")
    print("-" * 40)
    print(digest_text)
    print("═" * 60)

    # 7. Write file
    DIGESTS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    out_file = DIGESTS_OUTPUT_DIR / f"{proj_label}_{today_str}.md"

    counter = 1
    while out_file.exists():
        out_file = DIGESTS_OUTPUT_DIR / f"{proj_label}_{today_str}_{counter}.md"
        counter += 1

    out_file.write_text(digest_text, encoding="utf-8")

    if truncated_at is not None:
        note = f"\n\n---\n> ⚠️ Digest was truncated: only includes {len(parts)}/{len(matched)} initial sessions due to context limit."
        with out_file.open("a", encoding="utf-8") as fh:
            fh.write(note)

    print(f"\n✅ Digest saved: {out_file}")
    print()
