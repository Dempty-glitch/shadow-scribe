# ADR-010 — Single-Source Catalog with Agent-Native Navigation

| Field | Value |
|-------|-------|
| **ID** | ADR-010 |
| **Date** | 2026-04-28 |
| **Status** | 🟢 ACCEPTED |
| **Supersedes** | — |
| **Related** | ADR-006, ADR-007, ADR-008, ADR-009 |

---

## Context

X review (2026-04-28) suggested splitting INDEX_MATRIX into 3 files:
`00_INDEX_MATRIX.md` (timeline) + `PROJECT_INDEX.md` (per-project) + `CRYSTAL.md` (architecture).

The proposal was motivated by:
- INDEX_MATRIX mixing chronological, project-content, and architecture roles
- Concern that a single large file is slow to query
- Karpathy-style specialization: each artifact has a single purpose

Two alternatives were debated:
- **A (this ADR):** Single-source catalog + agent-native navigation tools
- **B (rejected):** 3 physical files, each with a distinct schema

The core question: when MATRIX grows large, does the agent need 3 files — or does it need better tools?

---

## Decision

**INDEX_MATRIX remains the single source of truth. Derived views are command outputs, not files.**

- `00_INDEX_MATRIX.md` — master log, append-only, single source
- `PROJECT_INDEX` etc. — rendered on demand by `watchdog list`, not stored as separate persistent files
- `CRYSTAL.md` — persistent per-project file, governed by ADR-009 (out of scope here)
- No sync logic, no drift, no dual-source writes

Agent navigation is provided by tools, not by file splitting:

| Scale | Tool strategy |
|-------|--------------|
| < 200 rows | `watchdog query --project` (Stage 1 grep, ~50ms) |
| 200–1000 rows | `watchdog list --project --since --tag` (deterministic pre-filter) |
| 1000–5000 rows | Stage 2 top-K: send Stage 1 hits to Gemini, not full MATRIX |
| > 5000 rows | Index-of-index summary header (CRYSTAL summary block) + hierarchical query |
| > 3000 rows (time) | Year archive: `MATRIX_2025.md`, active = current year only |

---

## Rationale

**DRY — one write, always consistent.** Every `watchdog scribe` writes one row to one file. With 3 files, the same data must be written (or synced) in 3 places. Sync logic = drift surface.

**Agent-first ≠ LLM-everywhere.** ADR-008 principle: serve agents, not humans. But serving agents means deterministic, fast, reliable tools — not more LLM calls. Tool > LLM where deterministic is possible.

**Karpathy doesn't apply 1-1.** His "1 library per domain" applies to semantic segregation of *different* knowledge types. MATRIX rows are all the same type (session entries). Splitting by project is a filter operation, not a schema change — a tool handles it better than a separate file.

**Derived views in files = maintenance burden.** If `PROJECT_INDEX.md` exists as a file, it must be regenerated whenever MATRIX changes, surfaced in git diffs, and kept in sync with MATRIX. A command that renders on demand has none of these costs.

**Scale problems are tool problems, not schema problems.** 5000 rows in MATRIX is a query performance problem — solved by hierarchical retrieval (Stage 1 → top-K Stage 2 → parent fetch), not by splitting the file.

---

## Rejected Alternative: 3-File Split

| Problem | 3-file answer | Single-source answer |
|---------|--------------|---------------------|
| Slow full-MATRIX query | PROJECT_INDEX = per-project file | `watchdog list --project` (filter, ~ms) |
| CRYSTAL drift from MATRIX | CRYSTAL.md = ADR snapshot | ADR-009 already solved this; CRYSTAL ≠ MATRIX |
| Semantic confusion | 3 schemas, 3 roles | 1 schema, roles = command flags |

Rejected because: sync logic, dual-write on scribe, git noise from regenerated files, drift surface.

---

## Consequences

**Benefits:**
- Zero drift: one file = one source
- No sync logic in `watchdog scribe` (already append-only)
- Agent query path: tool filter first, LLM only when needed
- Git history clean (no auto-regenerated files committed)

**Costs / Risks:**
- `watchdog list` must be built (30 LOC, low risk — see Roadmap below)
- Stage 2 top-K rerank must replace full-MATRIX Gemini send (medium, reduces token cost at scale)
- At >5000 rows, index-of-index header must be maintained (future, not now)

**Known limitation:** Pipe character in TL;DR cell (fixed in Track B) — mitigated by `_split_md_row` + prompt instruction (`**KHÔNG dùng ký tự "|" trong cell TL;DR**`). Not a schema problem, a prompt discipline problem.

---

## Roadmap (ordered by priority)

| # | Task | Trigger | Effort |
|---|------|---------|--------|
| 1 | `watchdog list --project --since --tag` | Now (ADR-010 ACCEPTED) | ~30 LOC |
| 2 | Stage 2 top-K: send Stage 1 hits, not full MATRIX | Now (reduces token waste) | ~20 LOC |
| 3 | `watchdog doctor` / lint-vault | ADR-011 ACCEPTED | ~2h |
| 4 | ~~Query loopback `--save-as`~~ | DROPPED 2026-05-01 | — |
| 5 | Index-of-index CRYSTAL summary block | > 1000 rows | Low |
| 6 | Year archive MATRIX_YYYY.md | > 3000 rows | Low |
| 7 | Hierarchical query (index → slice → candidates → target) | > 5000 rows | Medium |

**Note (2026-05-01):** Row 4 dropped. Karpathy model-collapse framing does
not apply at tech-project scale (build-then-ship lifecycle, code as ground
truth, no decision driven by recursive LLM summaries). Shell redirect
(`watchdog query "foo" > file.md`) covers manual save case. `ADR_INDEX`
row 012 remains permanent gap.

B3 transactional scribe covers single-file writes — remains valid, unaffected by this ADR.
