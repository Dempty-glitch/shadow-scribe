# ADR-001: Watchdog Architecture

| Field | Value |
|-------|-------|
| **Date** | 14/04/2026 |
| **Project** | shadow-scribe |
| **Status** | 🟢 ACCEPTED |
| **Related Session** | [→](../../sessions/2026-04/14_04_26.md) |

## Context

The IDE Agent (Anti/Antigravity) operates in a closed loop — it does not save chat transcripts to disk. A watchdog system is needed to monitor and preserve session history without interfering with the main coding workflow.

---

## 📍 Decision (The Chosen Path)

> **Chosen: Option 4 — File System as Message Broker**

**Description:** Agent only dumps `session_brief.md` + gathers artifacts. A Python script + Gemini Flash reads the data and writes the full session log. The File System serves as the communication channel between the two agents.

**Rationale:**
- Zero coupling — Agent and Watchdog are unaware of each other's existence
- Gemini Flash 1M context, extremely cheap (~$0.001/session) for heavy lifting
- Durable — vault exists independently; even if Agent is reinstalled, vault remains intact

**Accepted trade-off:** Watchdog lacks "How" data (no chat transcript) — compensated by requiring `session_brief.md` to be more detailed (10-15 lines instead of 3)

---

## 🚫 Rejected Paths

### ❌ Option 1 — Agent writes full Session Log itself
- **Rejected at:** Theory stage
- **Reason:** Burns expensive Claude Opus tokens (~$0.38/session vs $0.001). Agent wastes its precious context window writing logs instead of coding.

### ❌ Option 2 — claude-mem plugin (hooks + SQLite + Bun worker)
- **Rejected at:** Theory stage
- **Reason:** Only works with Claude Code CLI. Antigravity has no compatible hook system. Requires additional Claude API calls per observation. Needs Bun runtime installation.

### ❌ Option 3 — MCP Server (Agent calls Watchdog in real-time)
- **Rejected at:** Theory stage (not tested)
- **Reason:** Requires bidirectional real-time communication between Agent and Watchdog. Overkill for post-session review needs. User doesn't need real-time feedback in V1.

---

## 🔮 Future Paths (Untested)

### ⏳ Option 5 — Real-time Audit (Phase 2 roadmap)
- **Theory:** Watchdog runs as daemon, audits `git diff` vs `implementation_plan.md` every 15 minutes, pings Telegram if deviation detected
- **When to try:** Once Phase 1+2+3 are stable and user wants real-time guardrails
- **Predicted risk:** High false positive rate if Gemini Flash lacks sufficient context

### ⏳ Option 6 — Antigravity Native Integration
- **Theory:** If Antigravity later exposes a hook API (like Claude Code), could adopt claude-mem-like pattern
- **When to try:** When platform supports it
- **Predicted risk:** Depends on platform roadmap, outside our control

---

## 📊 Comparison Matrix

| Criteria | Opt 1: Self-write ❌ | Opt 2: claude-mem ❌ | Opt 3: MCP real-time ❌ | **Opt 4: File System ✅** | Opt 5: Real-time ⏳ |
|----------|----------------------|---------------------|------------------------|--------------------------|---------------------|
| Token cost | High ($0.38) | High (Claude API) | Medium | **Very low ($0.001)** | Medium |
| Complexity | Low | High | High | **Low** | High |
| Agent context impact | Large | 0 | Small | **Very small** | 0 |
| Durable | ✅ | ✅ | ✅ | **✅** | ✅ |
| Extra deps | None | Bun, ChromaDB | None | **Python (pre-installed)** | Telegram bot |
| Tested? | ❌ | ❌ | ❌ | **✅ Built in Phase 1+2** | ❌ |
