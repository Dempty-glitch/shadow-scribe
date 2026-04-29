# 🐛 Known Issues — Shadow Scribe

> Operational bugs discovered through real-world agent onboarding tests.
> Each entry includes root cause, fix, and commit hash.

---

| ID | Bug | Severity | Status | Fixed in |
|----|-----|----------|--------|----------|
| KI-001 | Same-day session collision: INDEX_MATRIX path mismatch | 🔴 Critical | ✅ FIXED | `1d5617c` |
| KI-002 | Agent onboard: no git cross-check for stale INDEX | 🟡 Medium | ✅ FIXED | `1d5617c` |
| KI-003 | Vault/repo GUIDE.md drift (manual copy on setup, no resync) | 🟡 Medium | ✅ FIXED | `0ef9051` |
| KI-004 | Agent action-impulse: writes code on read-only intent | 🟡 Medium | ✅ FIXED | `494974f` |
| KI-005 | `watchdog audit` auto-pick filename mismatch with Plan-First Discipline | 🟡 Medium | ✅ FIXED | `867609f` |
| KI-006 | Autosync incomplete: `adr/` folder drifts between repo and vault | 🟡 Medium | 🟠 OPEN | — |

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

---

## KI-005 — Audit auto-pick filename mismatch with Plan-First Discipline

**Discovered:** 2026-04-29 (post Stage 2 top-K dump+audit test)

**Symptom:** Codex dumped plan `stage2_topk_spec.md` to `vault/projects/shadow-scribe/plans/`
per Plan-First Discipline (GUIDE), then ran `watchdog audit`. Audit reported
🔴 GOAL DRIFT — false positive. Diff was Stage 2 top-K (commit `7c38fbc`),
but audit auto-loaded an OLDER `implementation_plan.md` from a previous task.

**Root cause:** Two conventions don't align.
- GUIDE Plan-First Discipline: "dump plan to vault before coding" — any filename.
- `cmd_audit.py` auto-pick: globs for `implementation_plan.md` specifically, by mtime.

Result: plan dumped under different name (e.g., `stage2_topk_spec.md`) is invisible
to audit auto-pick. Audit falls back to whatever stale `implementation_plan.md` exists.

**Workaround (today):** pass `--plan <explicit-path>` to audit when plan filename
isn't `implementation_plan.md`.

**Fix options (deferred):**
- **A.** Standardize convention: all plans named `implementation_plan.md`, scoped by
  subfolder (`plans/{task}/implementation_plan.md`). Strict but unambiguous.
- **B.** Broaden audit auto-pick: glob `plans/**/*.md` by mtime. Simpler, but risks
  picking wrong plan when multiple tasks dumped in parallel.

**Decision pending:** likely bundled with ADR-011 (`watchdog doctor` / lint-vault).
Doctor may surface this drift class systematically.

**Tests:** None yet. Awaiting fix direction.

---

## KI-006 — Autosync incomplete: `adr/` folder drifts between repo and vault

**Discovered:** 2026-04-30 (codex flagged ADR-013 dual-path ambiguity during KI-005 spec review)

**Symptom:** Spec for KI-005 told codex to write ADR-013 only to vault path
(`vault/projects/shadow-scribe/adr/`). Codex correctly questioned: repo also
has `docs/adr/` mirror with ADR-001..010. Writing to vault only would leave
ADR-013 out of git history; writing to both is duplicated effort with no
sync guarantee.

Investigation: `watchdog_scribe._sync_docs()` only syncs 3 files:
`["GUIDE.md", "README.md", "KNOWN_ISSUES.md"]`. The `adr/` folder is NOT
covered. ADRs sync manually today (every prior ADR was written twice or
copied by hand).

**Root cause:** Same class as KI-003 (GUIDE drift), but KI-003 fix only
patched named files, not folders. ADRs drifted unnoticed because they're
write-once: rare edits → drift accumulates slowly → invisible until next
ADR creation forces the question.

**Fix options:**
- **A.** Extend `_SYNC_DOC_FILES` mechanism to support folder sync.
  E.g., add `_SYNC_DIRS = [("docs/adr", "projects/shadow-scribe/adr")]`
  and helper `sync_dir_if_differ(src_dir, dst_dir)` that mirrors all `.md`
  files within.
- **B.** Project-aware sync: scan `docs/adr/` → for each project mentioned
  in vault, sync to corresponding `projects/{name}/adr/`. Future-proof
  for multi-project repos.

**Workaround (today):** Manual `cp docs/adr/*.md vault/projects/{name}/adr/`
after creating an ADR. KI-005 PR uses this workaround per revised spec
instruction to codex.

**Decision pending:** A is simpler, ship first. B can come when 2nd project
joins the repo (currently only `shadow-scribe`, single-project assumption is
fine).

**Related:** ADR-011 doctor should LINT this — flag any ADR file present in
repo but missing or stale in vault.

**Tests:** None yet. When fix lands, mirror the 4 sync tests from KI-003.
