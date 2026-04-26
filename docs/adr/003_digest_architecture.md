# ADR-003: Digest Architecture — Subcommand vs Flag vs Separate Script

| Field | Value |
|-------|-------|
| **Date** | 14/04/2026 |
| **Project** | shadow-scribe |
| **Status** | 🟢 ACCEPTED |
| **Related Session** | [→](../../sessions/2026-04/14_04_26_2.md) |

## Context

After `audit` (Phase 3.1) stabilized, a need emerged to "review the entire work history by project" — not just 1 session but N sessions. The core question:

> *"How can we aggregate multiple session logs into a single concise digest, without needing to know how many sessions exist or read them manually?"*

Constraints:
- Sessions from different projects are mixed in the same `sessions/YYYY-MM/` — need filtering
- A project may only be active for a few weeks, then go silent — need time-based filtering
- Gemini Flash has 1M context but it's not infinite — need safe truncation
- Output must be viewable immediately (terminal) AND saved for later (file)

---

## 📍 Decision (The Chosen Path)

> **Chosen: Option 3 — Independent subcommand `watchdog digest` with project filter**

**Rationale:**
- Follows SRP — each subcommand does exactly one thing, no confusion with `scribe`/`audit`
- `--project NAME` filters by `**Project:**` header in session logs — no per-project folder needed
- `--last N` filters by filename date `DD_MM_YY.md` — no separate metadata file needed
- Dual output (terminal + file) serves 2 use cases: quick view vs archive
- Auto-truncates at 900K chars to fit Gemini 1M context — no silent crashes

**Accepted trade-offs:**
- Must maintain an additional subcommand and a separate system prompt (`DIGEST_PROMPT`)
- `--project` filter depends on session log header format being correct — if Agent writes wrong format, sessions get missed

---

## 🚫 Rejected Paths

### ❌ Option 1 — `--digest` flag on `scribe` (e.g., `watchdog scribe --digest`)

- **Rejected at:** Theory stage (immediately upon analysis)
- **Reason:** Violates SRP — `scribe` is Destructive, attaching `digest` (Read-only) to the same subcommand creates UX confusion. User can't tell if `scribe --digest` writes files. Same pattern already rejected in ADR-002.

### ❌ Option 2 — Separate script `digest_scribe.py`

- **Rejected at:** Theory stage
- **Reason:** Duplicates code (Gemini HTTP call, config constants, helper functions). Makes workspace unnecessarily complex. Model changes would require editing 2 files. `watchdog_scribe.py` is already the single entry point — maintain the pattern.

---

## 🔮 Future Paths (Untested)

### ⏳ Option 4 — Digest via Telegram bot
- **Theory:** `/digest shadow-scribe 7` from phone → bot runs `watchdog digest` → replies with result
- **When to try:** Phase 4 (Telegram integration)
- **Predicted risk:** Needs to reach local machine from Telegram — SSH tunnel or webhook adds complexity

### ⏳ Option 5 — Weekly cron auto-report
- **Theory:** `0 9 * * 1 watchdog digest --project shadow-scribe --last 7` runs every Monday
- **When to try:** After Telegram is stable
- **Predicted risk:** Requires machine to be always on + API key set in cron environment

---

## 📊 Comparison Matrix

| Criteria | Opt 1 ❌ `--digest` flag | Opt 2 ❌ Separate script | **Opt 3 ✅ Subcommand** | Opt 4 ⏳ Telegram | Opt 5 ⏳ Cron |
|----------|--------------------------|----------------------|-------------------------|--------------------|----------------|
| SRP? | ❌ mixed | ✅ | **✅** | ✅ | ✅ |
| DRY (no dup code)? | ✅ | ❌ | **✅** | ✅ | ✅ |
| Clear UX? | ❌ | ✅ | **✅** | ✅ | Auto |
| Project filter? | ❌ | optional | **✅ `--project`** | ✅ | ✅ |
| Time filter? | ❌ | optional | **✅ `--last N`** | ✅ | ✅ (hardcoded) |
| Dual output? | optional | optional | **✅** | ❌ Telegram only | ❌ file only |
| Tested? | ❌ | ❌ | **✅ Built + syntax OK** | ❌ | ❌ |
