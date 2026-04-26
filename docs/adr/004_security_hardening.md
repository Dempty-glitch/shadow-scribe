# ADR-004: Security Hardening Strategy — Application-Layer Defense

| Field | Value |
|-------|-------|
| **Date** | 24/04/2026 |
| **Project** | shadow-scribe |
| **Status** | 🟢 ACCEPTED |
| **Related Session** | [→](../../sessions/2026-04/24_04_26_1.md) |
| **Artifacts** | [Audit Report](../../artifacts/2026-04/shadow_scribe_audit_24_04_26.md) |

## Context

Shadow Scribe sends **entire git diffs + session briefs** to the Gemini API for analysis. If those diffs contain API keys, passwords, PEM keys, or PII — all of it gets sent to Google. Meanwhile, `00_INDEX_MATRIX.md` is read-modified-written by multiple potential agents with no race condition protection. HTTP calls have no timeout or retry — 1 network error = crash.

**Core contradiction:** Want to send complete diffs (for accurate Gemini analysis) but must conceal sensitive data (to prevent secret leaks).

---

## 📍 Decision (The Chosen Path)

> **Chosen: Defense-in-Depth at Application Layer**

Protection across 4 layers, all within `watchdog_scribe.py`, zero additional dependencies:

| Layer | Problem | Solution | Function |
|-------|---------|----------|----------|
| 1 — Redaction | Secrets in diff | Regex mask before API call | `_redact_secrets()` |
| 2 — Sanitization | Prompt injection via XML tags | Escape `<TAG>` → `＜TAG＞` | `_sanitize_tags()` |
| 3 — Atomicity | Race condition writing Index | `fcntl.flock` + `tempfile` + `os.replace` | `_atomic_write_index()` |
| 4 — Resilience | HTTP hang/crash | 120s timeout + exponential backoff 3x | `_http_post_with_retry()` |

**Why application-layer:**
- **Zero dependency** — only stdlib (`re`, `fcntl`, `tempfile`, `time`), no extra packages
- **Portable** — runs on any macOS/Linux with Python 3.9+
- **Transparent** — user sees `🔒 Redacted 2 secret(s)` directly in terminal
- **Optimized for single-user** — flock is sufficient for 2-3 parallel agents, no database needed

**Accepted trade-offs:**
- Regex redaction **isn't perfect** — custom secret formats may slip through. Mitigated by: proper `.gitignore` + don't hardcode secrets
- `fcntl.flock` **only works on Unix** — Windows needs `msvcrt.locking()`. Acceptable since user only uses macOS
- Fullwidth character escaping (`＜` replacing `<`) **changes visual appearance** of content — acceptable since content processed by Gemini won't be displayed raw

---

## 🚫 Rejected Paths

### ❌ Option 1 — Rely solely on .gitignore
- **Rejected at:** Analysis stage
- **Reason:** `.gitignore` blocks files from git but doesn't block hardcoded secrets in tracked code. Example: `config.py` with `API_KEY = "AIza..."` — file is legitimately tracked but contains a secret. `.gitignore` doesn't help.

### ❌ Option 2 — Encrypted transport (encrypt diff before sending)
- **Rejected at:** Theory stage
- **Reason:** Gemini needs plaintext to analyze. Encryption → Gemini can't read → pointless. The problem isn't *who* reads (Google), but *what data* gets sent.

### ❌ Option 3 — API proxy/middleware (local server filters before forwarding)
- **Rejected at:** Theory stage
- **Reason:** Violates zero-dependency principle. Adding a proxy = more processes, ports, config. Overkill for a CLI script.

### ❌ Option 4 — SQLite WAL for Index (replacing fcntl.flock)
- **Rejected at:** Analysis stage
- **Reason:** Index is a Markdown file — agents read it directly by eye and grep. Switching to SQLite = agents need tools to read, losing the "Human-readable Relational Database" property. Trade-off not worth it for a <100 line file.

### ❌ Option 5 — Pre-commit git hook (block commits containing secrets)
- **Rejected at:** Deferred (future roadmap)
- **Reason:** Hook blocks at git layer — good but doesn't protect `watchdog audit` (reads unstaged diff). Application-layer redaction protects at the last checkpoint before data leaves the machine.

---

## 📊 Comparison Matrix

| Criteria | .gitignore ❌ | Encrypted ❌ | Proxy ❌ | SQLite ❌ | **App-layer ✅** |
|----------|-------------|------------|---------|---------|-----------------|
| Blocks hardcoded secrets | ❌ | N/A | ✅ | N/A | **✅** |
| Zero dependency | ✅ | ❌ (crypto lib) | ❌ (server) | ❌ (sqlite3) | **✅ (stdlib)** |
| Agent reads Index via grep | ✅ | ✅ | ✅ | ❌ | **✅** |
| Race condition protection | ❌ | ❌ | ❌ | ✅ | **✅ (flock)** |
| HTTP resilience | ❌ | ❌ | ✅ | ❌ | **✅ (retry)** |
| Portable (Mac/Linux) | ✅ | ✅ | 🟡 | ✅ | **✅** |
| Windows compat | ✅ | ✅ | 🟡 | ✅ | **❌ (fcntl)** |

---

## 🔮 Future Paths (Untested)

### ⏳ Pre-commit Hook + Redaction combo
- **When:** If team goes multi-user
- **Idea:** Hook scans staged files using the same `_SECRET_PATTERNS`, blocks commit if found. Combined with app-layer = defense at 2 checkpoints.

### ⏳ Custom secret pattern config
- **When:** If user has unique secret formats (e.g., internal API tokens)
- **Idea:** Allow `~/.watchdog_redact_patterns` containing additional regex. Merged into `_SECRET_PATTERNS` at load time.
