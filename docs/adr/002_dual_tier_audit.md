# ADR-002: Dual-Tier Audit Architecture

| Field | Value |
|-------|-------|
| **Date** | 14/04/2026 |
| **Project** | shadow-scribe |
| **Status** | 🟢 ACCEPTED |
| **Related Session** | [→](../../sessions/2026-04/14_04_26.md) |

## Context

After `watchdog scribe` was working successfully (Phase 3.1), a need emerged for "mid-session error checking" without triggering the full file-writing pipeline. The core question:

> *"How can we check for goal drift while actively coding, without corrupting the index or creating partial logs?"*

Constraints:
- `scribe` is a **Destructive** command (writes files + deletes temp data) — cannot be used for "quick checks"
- Need a **Read-only, idempotent** command — safe to run any number of times
- Git diff must be taken from the **project directory** (CWD), not from the Vault

---

## 📍 Decision (The Chosen Path)

> **Chosen: Option 3 — Full separation of concerns: `scribe` (Destructive) + `audit` (Read-only)**

**Rationale:**
- Follows **Single Responsibility Principle (SRP)** — each command does exactly one thing
- `audit` is **fully idempotent** — call it 10 times, same result, no side effects
- Dedicated prompt for `audit` (shorter, temperature 0.1) → faster, less hallucination than `scribe`
- Auto-scans `implementation_plan.md` by `mtime` → automatically activates Hard Audit when a Plan exists

**Accepted trade-offs:**
- Must maintain 2 subcommands and 2 separate system prompts in one script
- User needs to remember: `audit` (mid-session) vs `scribe` (end-of-day)

---

## 🚫 Rejected Paths

### ❌ Option 1 — "Silent Assassin": Keep `scribe`, hide terminal output

- **Rejected at:** Theory stage (immediately upon analysis)
- **Reason:** Violates SRP — still a Destructive command despite "hiding" output. One accidental mid-session invocation → creates partial log + deletes brief + inserts stale row into Index. More dangerous than doing nothing.
- **Evidence:** Use case analysis: "Finished a module, not ready to stop, just want to check plan alignment" → `scribe` would require `@dump` first → creates one-way file → not reversible.

### ❌ Option 2 — Add `--check` flag to `scribe` (e.g., `scribe --check`)

- **Rejected at:** Theory stage
- **Reason:** Same subcommand with branching logic → confusing UX. User can't tell if `scribe --check` writes files. "Reducing command count" ≠ "Separating concerns".

---

## 🔮 Future Paths (Untested)

### ⏳ Option 4 — `audit` via Telegram bot

- **Theory:** User sends `/audit` from phone while coding; bot runs `git diff` on remote repo and returns result
- **When to try:** Phase 4 (Telegram integration)
- **Predicted risk:** Needs SSH/API into local machine or CI/CD hook — significantly more complex

### ⏳ Option 5 — `audit` runs automatically on `git commit`

- **Theory:** Git pre-commit hook → runs audit → blocks commit if 🔴 GOAL DRIFT
- **When to try:** Once workflow is stable
- **Predicted risk:** Calling Gemini API on every commit → slow + costly with frequent commits

---

## 📊 Comparison Matrix

| Criteria | Opt 1 ❌ Silent Assassin | Opt 2 ❌ `--check` flag | **Opt 3 ✅ Separate cmds** | Opt 4 ⏳ Telegram | Opt 5 ⏳ Git hook |
|----------|--------------------------|--------------------------|-------------------------|--------------------|-------------------|
| Read-only? | ❌ (still writes) | ⚠️ (depends on flag) | **✅ fully** | ✅ | ✅ |
| Idempotent? | ❌ | ⚠️ | **✅** | ✅ | ✅ |
| Requires @dump? | ✅ (dependent) | ✅ (dependent) | **❌ independent** | ❌ | ❌ |
| Clear UX? | ❌ confusing | ❌ confusing | **✅ explicit** | ✅ | ✅ |
| Tested? | ❌ | ❌ | **✅** | ❌ | ❌ |

---

## 🐛 Bug Discovered During Implementation

**Bug: UUID sort instead of mtime sort**

When auto-scanning `implementation_plan.md` in `.gemini/antigravity/brain/`, the code used `sorted(dirs, reverse=True)` to sort UUIDs alphabetically. UUIDs have no chronological order → selected the wrong Plan from an old conversation (Airwallex).

**Fix:** `sorted(dirs, key=lambda p: p.stat().st_mtime, reverse=True)`

**Real-world test:** First audit returned `🔴 GOAL DRIFT — related to Airwallex`. After fix → `✅ On-track`.
