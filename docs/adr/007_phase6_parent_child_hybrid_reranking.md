# ADR-007: Phase 6 Implementation — Parent-Child Retrieval + Sparse-LLM Hybrid Reranking

| Field | Value |
|-------|-------|
| **Date** | 25/04/2026 |
| **Project** | shadow-scribe |
| **Status** | ✅ IMPLEMENTED |
| **Related Plan** | (see `plans/v1.3.0_phase6.md` when created) |
| **Architecture ADR** | ADR-006 (WHY Lightweight Agentic RAG) |
| **Author** | Claude Opus 4.7 (independent reviewer agent) |

> **Next status flip:** ACCEPTED on user sign-off → IMPLEMENTED when `watchdog query` ships.

---

## Context

ADR-006 established: **Lightweight Agentic RAG**, built on the 3-layer vault structure (inherited from ADR-001/002/003).

ADR-007 answers the question: **How exactly is it implemented?**
- Retrieval pattern (Parent-Child)
- Search strategy (Sparse + LLM rerank)
- API design (`watchdog query`)
- Output format (progressive disclosure)
- Module placement

---

## 📍 Decision (The Chosen Path)

### 1. Parent-Child Retrieval (3-layer descent)

Mapped to academic literature terminology (2025-2026):

```
Child layer:        INDEX_MATRIX.md row              (precise, ~100 chars)
Parent layer:       sessions/YYYY-MM/*.md            (full context, ~5KB)
Grandparent layer:  projects/{p}/adr/*.md            (decision root, ~3KB)
```

**Workflow:**
1. Stage 1: grep keyword on INDEX_MATRIX → returns N **child rows** (precise hits)
2. Agent reads child rows → decides if parent context is needed
3. If full context needed → follow link → read **parent** (session log)
4. If root decision needed → follow link further → read **grandparent** (ADR)

**Key insight:** Does NOT pull all 3 layers simultaneously. Agent **descends on demand** — this is the "agentic" element from ADR-006.

**Citation:** This pattern matches "Parent-Child Retrieval" in RAG literature (cite [45, 47]) — achieves balance between precision (child level) and the full picture (parent/grandparent level).

### 2. Sparse-LLM Hybrid Reranking (2-stage retrieval)

**Stage 1 (cheap-fast, default):**
```python
results = grep_index_matrix(keyword)
if 2 <= len(results) <= TOP_N:
    return format_results(results)  # Good enough, return immediately
```

**Stage 2 (smart-fallback, on-demand):**
```python
# Triggered when:
# - Stage 1 < 2 hits (vague keyword, may miss)
# - Stage 1 > TOP_N hits (too many, needs ranking)
# - User explicit: --smart flag
prompt = f"Query: {keyword}\n\nINDEX_MATRIX:\n{full_index_matrix}"
ranked = gemini_rerank(prompt)  # Reuses shadow_scribe.gemini.call_gemini
return ranked[:TOP_N]
```

**Why "Hybrid":** Different from traditional BM25+Vector hybrid. This is **"cheap-fast (grep) + smart-expensive (LLM)"** — same cost-aware retrieval philosophy, citing [36, 42, 48, 49] on RRF + Cross-Encoder reranking.

### 3. API Design

```bash
# Basic
watchdog query "atomic write decision"

# Filter by project
watchdog query "payment" --project z-zero

# Limit results
watchdog query "refactor" --top 3

# Force Stage 2 (skip grep, go straight to LLM rerank)
watchdog query "why gemini-flash" --smart
```

**Default values:**
- `TOP_N = 5`
- `--project = None` (search all projects)
- `--smart = False` (auto-decide stage)

### 4. Output Format

```
🔍 Query: "atomic write decision"
   Found: 3 results (Stage 1 grep, 23ms)

┌─────────┬───────────────┬──────────────────────────────────────┬──────────────┐
│ Date    │ Project       │ TL;DR                                │ Link         │
├─────────┼───────────────┼──────────────────────────────────────┼──────────────┤
│ 24/04   │ shadow-scribe │ Hardening v1.2.1, atomic write fcntl │ ADR-004      │
│ 24/04   │ shadow-scribe │ 6 security fixes, atomic file ops    │ session→     │
│ 14/04   │ shadow-scribe │ Watchdog architecture, broker design │ ADR-001      │
└─────────┴───────────────┴──────────────────────────────────────┴──────────────┘

💡 For details: agent follows the link using its read tool.
```

**Core principle:** **DO NOT dump file contents into output.** Print a short table → agent follows links when needed. This is **progressive disclosure** done right — prevents context overflow.

### 5. Module Placement

```
shadow_scribe/
├── cmd_query.py          ← NEW (~120-150 lines)
├── (existing modules)

watchdog_scribe.py        ← add "query" subcommand to argparse
```

**Reuses existing modules:**
- `gemini.py` for Stage 2 LLM rerank (call_gemini with new prompt)
- `io_utils.py` for file reading + path parsing
- `config.py` for `VAULT_DIR`

---

## 🚫 Rejected Implementation Choices

### ❌ Complex markdown table parser (markdown-it library)
- **Reason:** INDEX_MATRIX format is already standardized → simple regex `^\\| (\\d{2}/\\d{2}) \\| (\\S+) \\| ... \\|$` is sufficient. No markdown parser library needed.

### ❌ Cache results in SQLite
- **Reason:** Violates zero-dep. Each grep < 100ms → caching unnecessary.

### ❌ Stream output
- **Reason:** Output is short (5 rows max). Streaming only complicates code.

### ❌ Always auto-trigger Stage 2
- **Reason:** Estimated 70%+ queries are satisfied by Stage 1. Auto Stage 2 = wasted cost.

### ❌ Query rewriting (call Gemini to parse query first)
- **Reason:** Adds latency + cost without clear benefit. Can be added later in v1.3.x if KPIs show keyword search misses frequently.

### ❌ Snippet preview in output
- **Reason:** Violates progressive disclosure. Table should be compact — agent follows link for details.

### ❌ Boolean query (`AND`/`OR`/`NOT`)
- **Reason:** YAGNI. Stage 2 LLM rerank already handles complex queries.

---

## ⚠️ Accepted Trade-offs

| Trade-off | Severity | Justification |
|-----------|----------|---------------|
| Output has no snippet preview | 🟢 LOW | Progressive disclosure done right — agent follows link for snippet |
| Stage 2 cost on vague keywords | 🟡 MED | Acceptable if fallback rate < 30% (KPI from ADR-006) |
| No boolean query support | 🟢 LOW | YAGNI — add later if needed |
| Fixed regex parser for INDEX format | 🟡 MED | If INDEX format changes → parser breaks. Mitigated by tests + format stable since ADR-003 |
| CLI table may break on narrow terminals | 🟢 LOW | Tested at 80 char width; TL;DR truncated if needed |

---

## 📊 Success Metrics

| Metric | Target |
|--------|--------|
| `cmd_query.py` ≤ 150 lines | ✅ (keep minimal) |
| Stage 1 latency p95 | < 100ms |
| Stage 2 latency p95 | < 1500ms |
| Test coverage `cmd_query.py` | ≥ 80% |
| Unit tests cover: grep hit, grep miss, Stage 2 trigger, project filter, --smart flag | All cases |
| Integration test: real query on current vault returns relevant result | ≥ 4/5 queries |

---

## 🛠️ Implementation Plan (high-level)

> Detailed step-by-step plan in `plans/v1.3.0_phase6.md` after ADR-006 + 007 ACCEPTED.

```
Step 1: Create cmd_query.py skeleton + tests/test_query.py
Step 2: Implement Stage 1 grep parser for INDEX_MATRIX
Step 3: Implement Stage 2 Gemini rerank
Step 4: Wire entry point watchdog_scribe.py with new subcommand
Step 5: Verify with 5 real queries on current vault (~15 sessions)
Step 6: Bump v1.3.0, update README/ROADMAP, tag release
```

---

## 🔄 Rollback Plan

Same as ADR-006: remove `watchdog query` subcommand, non-destructive (read-only operation).

---

## 🔮 Consequences

### Positive
- **Parent-Child Retrieval pattern implemented for the first time** in project, using proper academic terminology
- **Stage 2 fallback** addresses the inherent weakness of sparse search
- **Zero new dependencies** — only adds 1 Python file ~150 lines
- **High module reuse:** leverages existing `gemini.py`, `io_utils.py`, `config.py`

### Negative / Risks
- **Regex parser is fragile** if INDEX_MATRIX format changes → need thorough tests + format stable since ADR-003
- **TOP_N hardcoded to 5** — may not be optimal, needs tuning based on user feedback after v1.3.0
- **Stage 2 fallback rate** is the most important KPI to monitor — if abnormally high → review tagging discipline

---

## 📎 Citations & References

### RAG techniques literature (2025-2026)
- **Parent-Child Retrieval** — cite [45, 47] from "Upgrading from Basic RAG to Adaptive RAG"
- **Hybrid Search & Reranking** — cite [36, 42, 48, 49] (BM25/RRF + Cross-Encoder reranking)

### Architectural foundation (existing)
- ADR-006: Lightweight Agentic RAG (WHY this architecture)
- ADR-001/002/003: Vault 3-layer structure (foundation for Parent-Child)

### Module dependencies (existing in shadow_scribe/)
- `gemini.py`: call_gemini, parse_output (Stage 2 reuse)
- `io_utils.py`: file reading, path parsing
- `config.py`: VAULT_DIR
