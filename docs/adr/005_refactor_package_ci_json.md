# ADR-005: Refactor Monolith → Package + CI + JSON Parser (v1.2.2)

| Field | Value |
|-------|-------|
| **Date** | 25/04/2026 |
| **Project** | shadow-scribe |
| **Status** | 🟢 ACCEPTED |
| **Related Session** | [→](../../sessions/2026-04/25_04_26.md) |
| **Related Plan** | [v1.2.2_refactor.md](../plans/v1.2.2_refactor.md) |

> **Next status flip:** ACCEPTED on user sign-off → IMPLEMENTED when v1.2.2 merged to main.

---

## Context

Shadow Scribe v1.2.1 successfully shipped Phase 3.4 Security Hardening. However, an independent audit (Claude Sonnet) rated **6/10 Code Quality** and **5/10 Testing** — the two lowest scores across 10 criteria. Root causes:

- `watchdog_scribe.py` had ballooned to **901 lines** — 3 commands + 2 prompts + 6 helpers + config + main in 1 file
- **0 unit tests** for security helpers (`_redact_secrets`, `_sanitize_tags`, `_atomic_write_index`)
- **0 CI/CD** — `test_audit_quality.py` only ran manually when remembered
- **Brittle parser** — split by string `===INDEX===`; Gemini off by 1 char = unrecoverable crash

Continuing to add features (Phase 4 Telegram, Phase 6 RAG) on this monolith would double the tech debt and make the codebase untouchable.

**Actual trigger:** Claude Sonnet rated 6/10 Code Quality, 5/10 Testing → wanted B+ → A- before opening Phase 4.

---

## 📍 Decision (The Chosen Path)

> **Chosen: 3 simultaneous tasks in 1 version bump (v1.2.2 PATCH)**

### 1. Split monolith → `shadow_scribe/` package (8 modules)

```
shadow_scribe/
├── config.py      — paths, env loader
├── prompts.py     — 3 prompt strings
├── security.py    — redact, sanitize, filter_diff
├── io_utils.py    — atomic_write, read_file, parse_session_date
├── gemini.py      — http retry, call_gemini, parse_output
├── cmd_scribe.py  — cmd_scribe()
├── cmd_audit.py   — cmd_audit()
└── cmd_digest.py  — cmd_digest()
```

`watchdog_scribe.py` becomes a thin entry point ≤ 50 lines.

**Rationale:** True test isolation requires each module to be independently importable. Testing `security.py` must not pull in HTTP client, must not need Gemini mocks.

### 2. CI: GitHub Actions matrix 3.9 + 3.12, ruff, mypy non-strict

```yaml
matrix: python-version: ['3.9', '3.12']
steps: ruff check → mypy --ignore-missing-imports → pytest → test_audit_quality.py --mock
```

**Rationale:** Oldest supported (3.9) + newest (3.12) catches compatibility drift without excess. `mypy non-strict` is a gate-keeper for the future — won't catch much now with 0 type hints, but establishes a baseline to tighten in v1.2.3+.

### 3. 3-layer JSON parser replacing `===INDEX===`

```
Layer 1: json.loads(raw)                    — response_mime_type enforced
Layer 2: strip code fence → json.loads()    — Gemini sometimes still wraps
Layer 3: split("===INDEX===")              — fallback backward compat
```

Uses `response_mime_type: "application/json"` in API call to force Gemini to return pure JSON.

**Rationale:** String separator is a single point of failure. 3-layer never crashes — worst case returns `("", "")` and logs a warning.

---

## 🚫 Rejected Paths

### ❌ Package name `watchdog/`
- **Reason:** `watchdog` is a popular PyPI package (~13M downloads/month, file-system events). Import collision if user installs it in the same env.
- **Fix:** `shadow_scribe/`

### ❌ Split into only 2-3 large files
- **Reason:** `security.py` and `gemini.py` are completely different concerns. Merging into `helpers.py` means tests still need HTTP mocks when testing regex — that's not true test isolation.

### ❌ mypy `--strict`
- **Reason:** Project currently has 0 type hints → `--strict` generates hundreds of errors immediately → CI permanently red → nobody fixes → CI gets ignored. Non-strict is a pragmatic compromise.

### ❌ Bump to v1.3.0
- **Reason:** SemVer: MINOR when there's a new user-visible feature. Refactor + CI + parser are internal changes = PATCH. v1.3.0 should be reserved for Phase 4 Telegram.

### ❌ JSON parser without fallback
- **Reason:** Gemini sometimes wraps JSON in code fences despite being told not to. No fallback = production crash. 3-layer is belt-and-suspenders.

### ❌ Wildcard import `from shadow_scribe.config import *`
- **Reason:** Namespace pollution + import side-effects + permanent lint warnings. Use explicit symbol imports.

---

## ⚠️ Accepted Trade-offs

| Trade-off | Severity | Justification |
|-----------|----------|---------------|
| mypy catches nothing yet (0 type hints) | 🟢 LOW | Gate-keeper, not an immediate bug catcher. Type hints ship incrementally in v1.2.3+ |
| 14-16h of work, no new features | 🟡 MED | Debt repayment — investing in foundation before Phase 4/6 |
| 10 granular commits — skipping verify risks silent regression | 🟡 MED | Mitigated by rule: verify each step before committing the next |
| `response_mime_type` requires Gemini 1.5-flash+ | 🟢 LOW | Project uses `gemini-2.5-flash` → OK. Layer 2/3 still catches on older models |
| Import paths change in `setup.sh` | 🟢 LOW | Only alias in `setup.sh` — no external consumers |

---

## 📊 Success Metrics

> Baseline from Claude Sonnet audit 25/04/2026. Re-measure after v1.2.2 ships.

| Criteria | Before (v1.2.1) | Target (v1.2.2) |
|----------|-----------------|-----------------|
| Code Quality | 5.5/10 | 8.0/10 |
| Testing/CI | 5.0/10 | 7.5/10 |
| Architecture | 6.5/10 | 8.0/10 |
| Maintainability | 6.0/10 | 7.5/10 |
| **Weighted total** | **6.9/10 (B+)** | **≥8.0/10 (A-)** |
| Test coverage critical paths | 0% | ≥75% |
| Max lines/file | 901 | ≤250 |
| CI green | ❌ | ✅ (3.9 + 3.12) |

---

## 🔄 Rollback Plan

- **Tag before starting:** `git tag v1.2.1-stable` at last v1.2.1 commit
- **Per-step rollback:** Each step is 1 commit → `git revert <commit>` anytime
- **Full rollback:** `git checkout v1.2.1-stable` + update alias in `setup.sh`
- **No long-running branches:** `main` is source of truth, no `refactor/v1.2.2` branch

---

## 🔮 Consequences

### Positive
- **True test isolation** — `security.py` tests don't need HTTP mocks
- **Green CI** — regressions caught automatically, no manual memory required
- **Foundation for Phase 4/6** — Telegram bot can `import shadow_scribe.cmd_audit` directly
- **PyPI-ready** — `shadow_scribe/` package structure enables future publishing
- **Safer parser** — 3-layer fallback is resilient. (Additional decision: If all 3 layers fail (garbage output), script will `sys.exit(1)` instead of returning `("", "")` per the original plan, to prevent silent data corruption.)

### Negative / Risks
- **14-16h with no new features** — the cost of cleaning up debt before Phase 4

---

## 📊 Comparison Matrix

| Criteria | Monolith 1 file ❌ | 2-3 large files ❌ | **8 modules ✅** |
|----------|-------------------|-------------------|-----------------|
| Test isolation | ❌ | 🟡 | **✅** |
| Import collision risk | N/A | N/A | **✅ (`shadow_scribe/`)** |
| Granular rollback | ❌ | 🟡 | **✅ (1 commit/module)** |
| Lines/file | 901 | ~300-400 | **≤250** |
| Foundation Phase 4/6 | ❌ | 🟡 | **✅** |
