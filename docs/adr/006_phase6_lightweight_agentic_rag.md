# ADR-006: Phase 6 — Lightweight Agentic RAG (Architecture)

| Field | Value |
|-------|-------|
| **Date** | 25/04/2026 |
| **Project** | shadow-scribe |
| **Status** | ✅ IMPLEMENTED |
| **Related Plan** | (see `plans/v1.3.0_phase6.md` when created) |
| **Implementation ADR** | ADR-007 |
| **Author** | Claude Opus 4.7 (independent reviewer agent) |

> **Next status flip:** ACCEPTED on user sign-off → IMPLEMENTED when `watchdog query` ships in v1.3.0.

---

## Context

The vault currently has ~15 sessions (after 2 weeks of use), with a pace of ~270/month based on actual usage (3-4 active projects, ~3 sessions/day/project). The **cold-start problem** is increasingly painful:

- Returning to a project after 2-3 weeks → forget specific decisions (e.g., "why did we choose `fcntl.flock` over `threading.Lock`?")
- `watchdog digest` provides summaries but CANNOT retrieve answers to specific questions — must read the entire digest
- Must open individual ADR/session files manually → wastes time + tokens

**Actual trigger:** User wants `watchdog query "atomic write decision"` → return relevant context in < 1 second.

**Core constraint (inherited from ADR-001):** Zero-dependency. No SQLite, no ChromaDB, no embedding model.

**Important scope note:** The 3-layer storage structure (INDEX_MATRIX → sessions → ADR) was designed in ADR-001/002/003. Phase 6 **does NOT change the structure**, it only adds a query layer that exploits the existing structure.

---

## 📍 Decision (The Chosen Path)

> **Chosen: Lightweight Agentic RAG** — achieve agentic behavior at Naive RAG cost.

### Classification per industry taxonomy (2025-2026)

| RAG Type | Latency | Cost/Query | Phase 6 fit? |
|----------|---------|-----------|--------------|
| Naive RAG | 300ms | $0.005 | ❌ Single-shot, no agent decision |
| Advanced RAG | 1250ms | $0.0175 | ⚠️ Has rerank but no query rewriting/HyDE |
| GraphRAG | 3000ms | $0.085 | ❌ No separate knowledge graph built |
| Full Agentic RAG | 6000ms | $0.055 | ✅ Correct category by behavior |
| **Phase 6 (Lightweight Agentic)** | **~500ms** | **~$0.001** | ✅ **Agentic at Naive cost** |

### Why "Lightweight Agentic"

- **Agentic element:** Agent decides to query Layer 1 → sufficient then stop, insufficient then descend to Layer 2 → needs root cause then descend to Layer 3. Not single-shot.
- **Lightweight element:** No multi-step reasoning loops (like full Agentic 6000ms). Each query = 1-2 round trips, shallow but with agentic decision-making.

### USP (Unique Selling Point)

> **Achieves agentic behavior at Naive RAG cost by leveraging human-curated INDEX.**

Every session brief already has TL;DR + tags written by a human (or agent) — INDEX_MATRIX becomes a "human-curated semantic index". No auto-embedding needed because semantics are already encoded in natural language tags.

---

## 🚫 Rejected Paths

### ❌ Vector RAG (ChromaDB / SQLite + embeddings)
- **Primary reason:** Violates zero-dep principle (inherited from ADR-001). Requires `pip install` + embedding model.
- **Hidden cost:** Re-index on every file edit, black-box debugging, can't display "why this result was found".
- **When to use:** Vault > 10K documents without human curation. Not there yet.

### ❌ Naive RAG (single-shot grep, dump full)
- **Reason:** No agent decision → usually returns too many or too few results. Context overflow when grep matches many files.
- **Specifically:** `grep "atomic" sessions/` returns 20 unranked hits → agent must read all of them.

### ❌ GraphRAG (build separate knowledge graph)
- **Reason:** INDEX_MATRIX is already a pseudo-graph (each row links to session, ADR, artifacts). Building a separate graph = duplicate data + maintenance burden.
- **Cost:** Must re-build graph whenever a new session arrives.

### ❌ Full Agentic RAG (multi-step reasoning loops)
- **Reason:** 6000ms latency is not acceptable for cold-start use case. User wants quick answers, not long dialogs.
- **Cost:** $0.055/query × 10 queries/day = $16/month — overkill for personal use.

### ❌ Self-build embedding pipeline with Gemini
- **Reason:** Gemini has an embedding API but still needs vector storage → requires SQLite/file format → violates zero-dep.

---

## ⚠️ Accepted Trade-offs

| Trade-off | Severity | Justification |
|-----------|----------|---------------|
| Sparse search needs more precise keywords than vector | 🟡 MED | Compensated by Stage 2 LLM rerank (details in ADR-007) when grep < N hits or keyword is vague |
| Depends on INDEX_MATRIX tagging quality | 🟡 MED | Watchdog scribe enforces TL;DR + tags in brief format. Quality improves with discipline. |
| No fuzzy match ("payment" → "billing") | 🟢 LOW | Stage 2 LLM rerank handles this. Test with real data when vault > 50 sessions. |
| Depends on Gemini API (Stage 2) | 🟢 LOW | Already available since Phase 1. No new dependency added. |
| Stage 1 grep linear-scan → slow when vault > 5K sessions | 🟢 LOW | Currently 15 sessions, ~270/month → 5K rows = ~18 months. At that point, add pre-built markdown index (still no Vector DB). |

---

## 📊 Success Metrics

> Measure after v1.3.0 ships, following 2 weeks of real usage.

| Metric | Baseline (v1.2.2) | Target (v1.3.0) |
|--------|-------------------|-----------------|
| Cold-start time (new session, agent has context) | ~5 min (manual prompting) | < 30 sec (`watchdog query`) |
| Avg query latency (Stage 1 only) | N/A | < 100ms |
| Avg query latency (Stage 2 fallback) | N/A | < 1500ms |
| Cost per query (avg) | N/A | < $0.002 |
| Stage 2 fallback rate | N/A | < 30% (if higher → tagging discipline is poor, needs improvement) |
| User-reported "found what I need" | N/A | ≥ 80% sessions |

---

## 🔄 Rollback Plan

- **Non-destructive:** Phase 6 only ADDs subcommand `watchdog query`, does not change `scribe`/`audit`/`digest`
- **Simple rollback:** Remove subcommand → vault structure unaffected (read-only operation)
- **Tag anchor:** `v1.2.2` (already tagged) serves as rollback target if v1.3.0 fails

---

## 🔮 Consequences

### Positive
- **Cold-start solved:** Agent queries on its own instead of user manually feeding context
- **INDEX_MATRIX upgrade:** Becomes a "human-curated semantic index" with value growing per session
- **Cross-project query:** Queries span z-zero, kya-network, shadow-scribe within the same vault — value increases with multi-project usage
- **Validates hypothesis:** "Structured markdown + LLM rerank = sufficient replacement for vector DB at this scale" — pattern exportable later

### Negative / Risks
- **Tagging discipline:** Must be maintained — lazy tagging → query precision drops. Mitigated by scribe prompt enforcement.
- **Stage 2 fallback rate is a KPI to monitor** — if > 50%, Stage 1 isn't working effectively → need to review tagging or add query rewriting

### Long-term implication
- When vault > 5K sessions, Stage 1 grep may slow down → at that point, add pre-built markdown index file (still no Vector DB)
- This pattern could be exported as a standalone tool for Obsidian/Logseq users in the future

---

## 📊 Comparison Matrix

| Criteria | Vector RAG ❌ | Naive RAG ❌ | Full Agentic ❌ | **Lightweight Agentic ✅** |
|----------|---------------|---------------|------------------|---------------------------|
| Zero-dep | ❌ | ✅ | ⚠️ | **✅** |
| Cost/query | $0.0175 | $0.005 | $0.055 | **$0.001** |
| Latency | 1250ms | 300ms | 6000ms | **~500ms** |
| Agent decision | ❌ | ❌ | ✅ | **✅** |
| Debug transparency | ❌ (black box) | ✅ | ⚠️ | **✅** |
| Vault scale fit | 10K+ docs | < 100 docs | any | **100-5K docs** ← we are here |

---

## 📎 Citations & References

### Industry RAG taxonomy (2025-2026)
- Naive / Advanced / Graph / Agentic RAG framework — Starmorph Blog, 2026
- Cost & Latency benchmark numbers — Starmorph Blog, 2026

### Architectural foundation (existing)
- ADR-001: Watchdog Architecture (vault folder structure 3-layer)
- ADR-002: Dual-Tier Audit (separation scribe/audit, Phase 6 adds query tier)
- ADR-003: Digest Architecture (INDEX row format — base for query parser)

### Implementation details
- See ADR-007: specific implementation (Parent-Child Retrieval + Sparse-LLM Hybrid Reranking)
