# 🐛 Known Issues — Shadow Scribe

> Operational bugs discovered through real-world agent onboarding tests.
> Each entry includes root cause, fix, and commit hash.

---

| ID | Bug | Severity | Status | Fixed in |
|----|-----|----------|--------|----------|
| KI-001 | Same-day session collision: INDEX_MATRIX path mismatch | 🔴 Critical | ✅ FIXED | _(pending commit)_ |
| KI-002 | Agent onboard: no git cross-check for stale INDEX | 🟡 Medium | ✅ FIXED | _(pending commit)_ |

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
