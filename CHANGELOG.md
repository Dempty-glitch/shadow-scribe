# Changelog

All notable changes to Shadow Scribe are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.3.2] — 2026-04-26

### Fixed
- `GEMINI_MODEL` env var was silently ignored — function always returned `gemini-2.5-flash` regardless of ENV. Now uses allowlist: `{gemini-2.5-flash, gemini-2.5-pro}`, rejects unknown values.
- `VAULT_DIR` was not configurable despite README claim — added `SHADOW_SCRIBE_VAULT_DIR` env override (shell-level only, cannot be set via `.env` due to chicken-and-egg).
- `pytest tests/` failed 4 tests due to live Gemini API calls without key — added `@requires_gemini` skip marker. Result: `51 passed, 4 skipped` (was `42 passed, 4 failed`).
- `gemini.py` API key error message told users to `export GEMINI_API_KEY` — corrected to point to `~/Documents/agent_vault/.env`.
- CI workflow cherry-picked specific test files, masking failures — now runs `pytest tests/ -v`.

### Added
- `_resolve_vault_dir()` function in `config.py` — reads `SHADOW_SCRIBE_VAULT_DIR` from shell env.
- `_ALLOWED_MODELS` allowlist constant in `config.py`.
- `setup.sh` respects `SHADOW_SCRIBE_VAULT_DIR` env var.
- 9 new unit tests: 4 for `_resolve_vault_dir`, 5 for `get_gemini_model` allowlist.

### Changed
- Version bump: `1.3.1` → `1.3.2`
- README config table: `VAULT_DIR` → `SHADOW_SCRIBE_VAULT_DIR`, `GEMINI_MODEL` documents allowlist.

---

## [1.3.1] — 2026-04-26

### Added
- **i18n — ENV-based bilingual output** (`SHADOW_SCRIBE_LANG=vi|en`)
  - Dual prompt templates for all 4 modes: `scribe`, `audit`, `digest`, `query`
  - `get_lang()` in `config.py` with silent fallback to `vi` + warning log
  - `setup.sh` interactive language prompt writes `SHADOW_SCRIBE_LANG` to `.env`
  - 5 new unit tests for config + prompt injection logic
- CI badge in `README.md` and `README.vi.md`

### Fixed
- `DIGEST_PROMPT_VI` typo: `Rủi cấu tích lũy` → `Rủi ro tích lũy`
- `README.vi.md` `GEMINI_MODEL` row missing `+ query`
- Ruff W293: trailing whitespace on blank lines in `config.py` and `gemini.py`

### Changed
- `call_gemini_audit()` signature: removed `audit_prompt` param (prompt selection now owned internally)
- Version bump: `1.3.0` → `1.3.1`

---

## [1.3.0] — 2026-04-26

### Added
- **Phase 6 — Lightweight Agentic RAG** (`watchdog query`)
  - `watchdog query <keyword>` with 4 flags: `--project`, `--top`, `--smart`
  - Parent-Child Retrieval: INDEX_MATRIX row → session log → ADR
  - 2-stage retrieval: Stage 1 sparse grep → Stage 2 Gemini LLM rerank (triggered on `<2 hits`, `>top hits`, or `--smart`)
  - ASCII table output (Date | Project | TL;DR | Link) — progressive disclosure, no raw dump
  - `cmd_query.py`, `QUERY_PROMPT`, `call_gemini_query()`, security tags for INDEX/QUERY
  - 22 unit tests covering parser / filter / render / Stage 2 trigger logic
- English documentation: `README.md`, `ROADMAP.md`, `GUIDE.md`, all ADRs
- ADR-006 (Lightweight Agentic RAG Architecture) and ADR-007 (Parent-Child + Sparse-LLM Hybrid Reranking)

### Fixed
- Stage 2 Gemini response: handle missing `parts` key gracefully
- CI: `test_query.py` added to unit test step

---

## [1.2.2] — 2026-04-25

### Added
- **Phase 3.5 — Package Refactor, CI/CD Pipeline & JSON Parser**
  - Split `watchdog_scribe.py` monolith into 8 modules under `shadow_scribe/`  
    (`config`, `prompts`, `security`, `io_utils`, `gemini`, `cmd_scribe`, `cmd_audit`, `cmd_digest`)
  - GitHub Actions CI matrix: Python 3.9 + 3.12 (Ruff lint, Mypy type check, Pytest)
  - 3-layer JSON parser fallback: `response_mime_type: application/json` → fence extract → separator split → raw
  - 14 unit tests in `test_helpers.py`
- ADR-005 (Refactor Package CI JSON)

---

## [1.2.1] — 2026-04-24

### Added
- **Phase 3.4 — Security Hardening**
  - `_redact_secrets()` — regex masks API keys, tokens, PEM before sending to Gemini
  - `_sanitize_tags()` — XML-escapes user content (prevents prompt injection)
  - `_atomic_write_index()` — `fcntl.flock` + `tempfile` atomic rename for `00_INDEX_MATRIX.md`
  - `_http_post_with_retry()` — 120s timeout + exponential backoff (3 attempts, codes 429/503)
  - `_filter_diff()` — strips lockfiles, `.DS_Store`, binary noise from diff payload
  - Trash timestamp: seconds → microseconds precision
- P10 few-shot examples in `AUDIT_PROMPT` + P13 regression test suite (`test_audit_quality.py`)
- ADR-004 (Security Hardening)

---

## [1.2.0] — 2026-04-23

### Added
- **Phase 3.3 — Bulletproof Scribe**
  - Directory-based routing: `raw_logs/{project-name}/` (was flat `raw_logs/`)
  - Soft-Delete: `raw_logs/` moved to `trash/{timestamp}/` instead of hard delete
  - Auto-Cleanup: `trash/` entries older than 30 days purged on every run
  - Zero-dependency `.env` loader (no `python-dotenv`) — reads `~/Documents/agent_vault/.env`
  - `--mock` dry-run flag for `watchdog scribe`
  - 🩸 Blood Lessons section in session log format
- `setup.sh` — one-shot vault setup, alias injection, `00_INDEX_MATRIX.md` bootstrap
- `GUIDE.md` — operations manual for AI agents
- ADR-003 (Bulletproof Scribe)

---

## [1.1.0] — 2026-04-14

### Added
- **Phase 3.2 — `watchdog digest`**
  - Aggregates N session logs into a single digest via Gemini Flash
  - `--project` filter (parses `**Project:**` from session header)
  - `--last N` days filter (parses date from `DD_MM_YY.md` filename)
  - Auto-truncates at 900K chars to fit Gemini 1M context
  - Dual output: terminal print + `digests/{project}_{date}.md`
  - No overwrite on same-day runs (auto-appends `_1`, `_2`...)
- ADR-002 (Dual-Tier Audit) — documents Phase 3.1 + 3.2 decisions

---

## [1.0.1] — 2026-04-14

### Added
- **Phase 3.1 — `watchdog audit`** (Dual-Tier Audit)
  - Hard Audit: auto-finds `implementation_plan.md` by `mtime`, cross-references git diff vs plan → detects Goal Drift
  - Soft Audit: git diff review only (no plan)
  - Read-only, idempotent — safe to run unlimited times
  - Gets `git diff` from CWD (project dir), not vault

### Fixed
- Plan auto-scan: UUID sort → `mtime` sort (prevents loading stale plans)

---

## [1.0.0] — 2026-04-14

### Added
- **Phase 1 — `@dump` Protocol**
  - IDE Agent writes `session_brief.md` (~15 lines) into `raw_logs/`
  - Captures `git diff` → `raw_logs/git_diff.txt`
  - Gathers temp artifacts → `agent_vault/artifacts/YYYY-MM/`
- **Phase 2 — `watchdog scribe`**
  - Gemini Flash reads `session_brief.md` + `git_diff.txt` → synthesizes Full Session Log
  - Writes `sessions/YYYY-MM/DD_MM_YY.md`
  - Inserts 1-line index row into `00_INDEX_MATRIX.md` (table-safe)
  - Cleans up `raw_logs/` after completion
- ADR-001 (Watchdog Architecture)
- Vault structure: `sessions/`, `raw_logs/`, `artifacts/`, `projects/`, `digests/`, `trash/`
