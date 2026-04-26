# 🗺️ Shadow Scribe — ROADMAP

> [English](ROADMAP.md) | [Tiếng Việt](ROADMAP.vi.md)

> This document tracks **completed phases** and **future plans** for the system.  
> ADR Index: [`docs/adr/ADR_INDEX.md`](docs/adr/ADR_INDEX.md)

---

## ✅ Completed

### Phase 1 — `@dump` Protocol *(14/04/2026)*
**Goal:** Establish the "Agent does the absolute minimum" mechanism.

- IDE Agent writes `session_brief.md` (~15 lines) into `raw_logs/`
- Gathers temp artifacts → `~/Documents/agent_vault/artifacts/YYYY-MM/`
- Captures `git diff` → `raw_logs/git_diff.txt`
- **Core principle:** Gemini Flash does the heavy lifting; Agent preserves its context window for code

**Related ADR:** [ADR-001 — Watchdog Architecture](docs/adr/001_watchdog_architecture.md)

---

### Phase 2 — `watchdog scribe` *(14/04/2026)*
**Goal:** Automate Full Session Log creation from brief + git diff.

- Gemini Flash reads `session_brief.md` + `git_diff.txt` → synthesizes Full Session Log
- Writes file to `sessions/YYYY-MM/DD_MM_YY.md`
- Inserts 1 row into `00_INDEX_MATRIX.md` (preserves table format)
- Cleans up `raw_logs/` after completion
- `--mock` flag for dry-run (no file writes)

---

### Phase 3.1 — `watchdog audit` *(14/04/2026)*
**Goal:** Enable "mid-session error checking" without triggering the write pipeline.

- Read-only, idempotent — safe to run unlimited times
- **Hard Audit:** Has `implementation_plan.md` → cross-references git diff vs plan → detects Goal Drift
- **Soft Audit:** No plan → reviews git diff only
- Auto-scans plan by `mtime` (fixed UUID sort bug → prevents loading stale plans)
- Gets `git diff` from CWD (project directory), not vault

**Bug fixed:** UUID sort → mtime sort  
**Related ADR:** [ADR-002 — Dual-Tier Audit](docs/adr/002_dual_tier_audit.md)

---

### Phase 3.2 — `watchdog digest` *(14/04/2026)*
**Goal:** Aggregate multiple sessions into a single digest filtered by project.

- Scans all `sessions/YYYY-MM/*.md` in the vault
- Filter by `--project` (parses `**Project:**` from session header)
- Filter by `--last N` days (parses date from filename `DD_MM_YY.md`)
- Auto-truncates if exceeding 900K chars (fits Gemini 1M context)
- Dual output: terminal print + file write to `digests/{project}_{date}.md`
- Does not overwrite same-day files (auto-appends counter)

---

### Phase 3.4 — Security Hardening *(24/04/2026)*
**Goal:** Patch 6 security and reliability vulnerabilities, elevating from "working prototype" to "production-ready".

- `_redact_secrets()` — Regex masks API keys/tokens/PEM before sending to Gemini API
- `_sanitize_tags()` — Escapes XML-like tags in user content (prevents prompt injection)
- `_atomic_write_index()` — `fcntl.flock` + `tempfile` atomic rename for `00_INDEX_MATRIX.md`
- `_http_post_with_retry()` — 120s timeout + exponential backoff retry (3 attempts)
- Trash timestamp precision: seconds → microseconds (`%f`)
- `_filter_diff()` — Removes lockfiles, `.DS_Store` from diff payload

**Reference:** Audit Report *(vault-only: `agent_vault/artifacts/2026-04/shadow_scribe_audit_24_04_26.md`)*

---

### Phase 3.5 — Package Refactor, CI/CD Pipeline & JSON Parser *(25/04/2026)*
**Goal:** Pay down tech debt — split monolith into standard PyPI package, set up CI matrix, bulletproof the parser.

- Split `watchdog_scribe.py` into 8 modules under `shadow_scribe/`
- Added GitHub Actions CI matrix: Python 3.9 + 3.12 (Ruff, Mypy, Pytest)
- Updated 14 unit tests for security, gemini parser, path utils
- Enforced `response_mime_type: "application/json"` + 3-layer parser fallback

**Related ADR:** [ADR-005 — Refactor Package CI JSON](docs/adr/005_refactor_package_ci_json.md)

---

### Phase 6 — Lightweight Agentic RAG (`watchdog query`) *(26/04/2026)*
**Goal:** Solve the cold-start problem — agent queries the vault for specific context instead of requiring manual prompting.

- `watchdog query <keyword>` with 4 flags: `keyword`, `--project`, `--top`, `--smart`
- **Parent-Child Retrieval:** child=INDEX_MATRIX row, parent=session log, grandparent=ADR
- **2-stage retrieval:** Stage 1 sparse grep (cheap-fast) → Stage 2 Gemini LLM rerank (smart-fallback) triggered when `<2 hits`, `>top hits`, or `--smart`
- Output: ASCII table (Date | Project | TL;DR | Link) — does NOT dump file contents (progressive disclosure)
- Zero new dependencies — reuses `gemini.py`, `security.py`, `io_utils.py`
- 22 unit tests covering parser/filter/render/Stage 2 trigger logic

**Related ADRs:**
- [ADR-006 — Lightweight Agentic RAG (Architecture)](docs/adr/006_phase6_lightweight_agentic_rag.md)
- [ADR-007 — Parent-Child + Sparse-LLM Hybrid Reranking (Implementation)](docs/adr/007_phase6_parent_child_hybrid_reranking.md)

---

## 🔜 Planned

### Phase 4 — Telegram Integration *(Pending — awaiting stability)*
**Goal:** Run audit & digest remotely via Telegram bot.

**Planned scope:**
- `/audit` from phone → bot SSHs into machine → runs `watchdog audit` → returns result
- `/digest shadow-scribe` → aggregates and replies directly on Telegram
- Auto-notification if audit detects 🔴 GOAL DRIFT

**Issues to resolve first:**
- Bot needs to reach local machine (SSH tunnel? ngrok? webhook?)
- Security: must not expose API key via Telegram

**Reference:** [ADR-002, Option 4 — Telegram bot](docs/adr/002_dual_tier_audit.md)

---

### Phase 5 — Thinking Discipline *(DROPPED)*
**Status:** ❌ Dropped — belongs in the **skill layer** (agent-side), not in Shadow Scribe (independent auditor). IDE agents (Claude Code, Antigravity) will evolve their own thinking protocols natively.

---

## 📊 Status Overview

| Phase | Description | Status | Version |
|-------|-------------|--------|---------|
| 1 | `@dump` Protocol | ✅ Done | 1.0.0 |
| 2 | `watchdog scribe` | ✅ Done | 1.0.0 |
| 3.1 | `watchdog audit` (Hard + Soft) | ✅ Done | 1.0.1 |
| 3.2 | `watchdog digest` (project-filtered) | ✅ Done | 1.1.0 |
| 3.4 | Security Hardening (Redact, Escape, Atomic, Retry) | ✅ Done | 1.2.1 |
| 3.5 | Package Refactor, CI/CD, JSON Parser | ✅ Done | 1.2.2 |
| 6 | Lightweight Agentic RAG (`watchdog query`) | ✅ Done | 1.3.0 |
| 4 | Telegram Integration | ⏸ Pending | — |
| 5 | ~~Internal Monologue~~ | ❌ Dropped (skill layer, out of scope) | — |
