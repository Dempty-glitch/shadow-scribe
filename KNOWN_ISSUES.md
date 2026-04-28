# 🐛 Known Issues — Shadow Scribe

> Operational bugs discovered through real-world agent onboarding tests.
> Each entry includes root cause, fix, and commit hash.

---

| ID | Bug | Severity | Status | Fixed in |
|----|-----|----------|--------|----------|
| KI-001 | Same-day session collision: INDEX_MATRIX path mismatch | 🔴 Critical | ✅ FIXED | `1d5617c` |
| KI-002 | Agent onboard: no git cross-check for stale INDEX | 🟡 Medium | ✅ FIXED | `1d5617c` |
| KI-003 | Vault/repo GUIDE.md drift (manual copy on setup, no resync) | 🟡 Medium | ✅ FIXED | `0ef9051` |
| KI-004 | Agent action-impulse: writes code on read-only intent | 🟡 Medium | ✅ FIXED | _(this commit)_ |

---

## KI-001 — INDEX_MATRIX path mismatch on same-day scribe

**Discovered:** 2026-04-28 (agent onboarding test)

**Symptom:** When `watchdog scribe` runs twice on the same day:
- File suffix logic (`_1.md`) correctly prevents overwrite on disk
- But `index_row` from Gemini contains hardcoded base path (`DD_MM_YY.md`)
- INDEX_MATRIX gets 2 rows pointing to different content but same path
- Agent onboarding reads INDEX → session log mismatch → reports stale state

**Root cause:** `prompts.py` instructs Gemini to generate path `sessions/{YYYY-MM}/{DD_MM_YY}.md`.
Gemini doesn't know the file was suffixed. `cmd_scribe.py` wrote the suffixed file but
passed the unpatched `index_row` to `_atomic_write_index`.

**Fix:** Added `_fix_index_row_path()` in `cmd_scribe.py` — post-processes `index_row`
to replace Gemini's base path with the actual suffixed filename before writing to INDEX.

**Tests:** 3 new tests in `tests/test_helpers.py`:
- `test_fix_index_row_path_no_collision`
- `test_fix_index_row_path_collision_suffix`
- `test_fix_index_row_path_no_match_in_row`

---

## KI-002 — Agent onboard missing git cross-check

**Discovered:** 2026-04-28 (same onboarding test)

**Symptom:** Agent follows GUIDE.md perfectly (reads INDEX + session log + ADR + INTENT + CRYSTAL)
but still reports "Track B pending" and "63 tests" when Track B was merged (7ec0736) and
test count was 90+. No mechanism to detect stale vault state.

**Root cause:** GUIDE.md "Start of Session" section had no instruction to cross-check
vault data against git history. When INDEX/session logs are stale, agent has no second
source of truth.

**Fix:** Added step to GUIDE.md: `git log --oneline -20` — git is ground truth when
INDEX seems stale or contradictory. Updated both repo `GUIDE.md` and vault `GUIDE.md`.

---

## KI-003 — Vault/repo GUIDE.md drift

**Discovered:** 2026-04-28 (immediately after KI-002 fix attempt)

**Symptom:** `setup.sh` copies repo `GUIDE.md` → vault `GUIDE.md` once, on initial install.
After that, no sync. When repo GUIDE gets fixes (alias note, dedup check, git step),
vault GUIDE stays stale. Agents read vault GUIDE → miss recent fixes → behavior diverges
from intended workflow.

**Root cause:** No automated sync mechanism between dev-edited (repo) and agent-read (vault)
copies of GUIDE.md.

**Fix:** Added `_sync_guide()` to `watchdog_scribe.py` — runs at the start of every
watchdog command, copies repo GUIDE → vault GUIDE if content differs. Repo is canonical.
Pure helper `sync_file_if_differ()` lives in `io_utils.py` (testable, reusable).

**Tests:** 4 new tests in `tests/test_helpers.py`:
- `test_sync_file_if_differ_creates_dest_when_missing`
- `test_sync_file_if_differ_overwrites_when_content_differs`
- `test_sync_file_if_differ_noop_when_match`
- `test_sync_file_if_differ_silent_when_source_missing`

---

## KI-004 — Agent action-impulse on read-only intent

**Discovered:** 2026-04-29 (codex onboarding test)

**Symptom:** User asks codex to "đọc guide" / "làm tiếp cùng tôi" — codex correctly loads context (state detection passes), but then immediately drafts a patch for `cmd_query.py` (Stage 2 top-K) without being asked to implement anything. Patch attempt was rejected, repo stayed clean, but the impulse to act on detected pending work is the failure.

**Root cause:** GUIDE.md "Start of Session" said "provide brief summary, then start coding" — ambiguous. Agent interprets identifying pending work as authorization to act on it. State analysis ≠ action authorization, but GUIDE didn't draw the line.

**Fix:** Added "🛑 Intent Discipline" section to GUIDE.md with explicit verb table. Read-only intents ("đọc", "summarize", "tóm tắt") → load + report + STOP. Action intents ("fix", "build", "sửa", "vá") → write code. When ambiguous, agent must ask.

**Tests:** No code change, prompt-only fix. Verification = re-running codex/anti onboarding test and confirming agent stops after report (manual QA, not automatable in pytest).
