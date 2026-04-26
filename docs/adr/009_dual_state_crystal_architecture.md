# ADR-009: Dual-State Crystal Architecture

| Field | Value |
|-------|-------|
| **Date** | 27/04/2026 |
| **Project** | shadow-scribe |
| **Status** | 🟢 ACCEPTED |
| **Related Session** | [→](../../sessions/2026-04/26_04_26_4.md) |

## Context

The current INDEX_MATRIX is a 1D timeline (append-only ledger). It records **what happened** but not **what the project looks like right now**. When an AI Agent asks "What modules does this project have?", RAG must grep through dozens of historical entries and reconstruct the architecture from scattered logs — slow, expensive, and hallucination-prone.

**Core contradiction:** AI needs both a map (spatial) and a diary (temporal), but mixing them in one file creates noise.

---

## 📍 Decision (The Chosen Path)

> **Chosen: Three-Layer Separation — INTENT / CRYSTAL / INDEX**

### The Three Layers

| Layer | Who writes | Change frequency | Role |
|-------|-----------|-----------------|------|
| **INTENT.md** | Human (you) | Very rare (change = pivot) | Will, boundaries, compass |
| **CRYSTAL.md** | Agent (rendered from code) | Per release or on-demand | Current architecture map |
| **INDEX_MATRIX** | Agent (append-only) | Every `@dump` | History, diary, forensic trail |

### Dependency Direction (No Cycles)

```
INTENT.md ──(guides)──► Agent ──(codes)──► Codebase
                                               │
                                       (render via AST/grep)
                                               ▼
                                         CRYSTAL.md ◄──(annotated by)── INDEX
```

**Codebase = truth. Index = intent diary. Crystal = abstract map rendered from codebase, annotated by Index.**

### File Locations

```
~/Documents/agent_vault/
├── 00_INDEX_MATRIX.md              ← History (global)
├── projects/
│   ├── shadow-scribe/
│   │   ├── INTENT.md               ← Human will
│   │   ├── CRYSTAL.md              ← Architecture map
│   │   └── MATURITY_ROADMAP.md     ← Planning
```

Crystal lives in **vault** (not repo) because it is metadata about code, not code itself. It should not pollute git history or trigger PR reviews.

---

## Crystal Structure

### Module Axis (Spatial — follows architect)

Backbone of Crystal. Nodes = modules, Edges = dependencies. Rendered when a new module is born or relationships change. This is the "what does the project look like NOW" view.

### Phase Axis (Temporal overlay — follows roadmap)

Not a separate graph. A **color layer** painted on top of the module graph. Each node carries a status. Phase transition = recolor node, not redraw graph.

**Module decides the shape. Phase decides the state.**

### Four Statuses (Purely Structural, Zero Ambiguity)

| Status | Condition | Detection |
|--------|-----------|-----------|
| `⬜ skeleton` | Listed in INTENT, no file exists in code | `grep INTENT` + `ls` |
| `🟡 building` | File exists, no test file exists | `ls module` + `grep test_module` |
| `🟢 crystallized` | File exists + test file exists | `ls module` + `grep test_module` |
| `⚫ deprecated` | File exists, no other module imports it | `grep "from module" == 0` |

All four checks are deterministic: shell commands only, zero LLM cost, zero guesswork.

---

## Render Rules

### When to create a node?
When a module **actually exists** in code (has folder, has file, can be imported). Crystal follows codebase — it never leads it.

### When to create an edge?
When `import`/`from` statements actually appear. Agent reads AST or greps imports → derives edges automatically.

### When to delete a node?
When module is deleted from codebase. Agent compares old Crystal with current codebase → proposes removal, human approves.

### Key Property: Crystal Always Lags One Beat Behind Codebase
This is a **feature, not a bug**. The delta between Crystal and code reveals:
- "This module is growing beyond plan" (node has unexpected edges)
- "This edge shouldn't exist" (unplanned dependency)

---

## INTENT.md Specification

A short, human-written file that defines project boundaries. Rarely changes (change = project pivot).

```markdown
# INTENT — [Project Name]

## This project IS:
- [Core purpose]
- [Key constraints: zero-dep, Python-only, etc.]

## This project DOES NOT:
- [Anti-goals: not a replacement for X, not real-time, etc.]
- [Boundaries AI must not cross]
```

When an Agent proposes a new module, it checks INTENT first. If the proposal violates a "DOES NOT" boundary → auto-reject without debate.

---

## RAG Impact

No complex intent-based routing needed. Simply **prepend Crystal content to every RAG prompt** as context primer. Gemini's 1M token window can easily absorb a small Crystal file alongside INDEX grep results.

- **Architecture questions** → Crystal answers directly (O(1), near-zero tokens)
- **History/debug questions** → Crystal provides context, INDEX provides timeline

---

## 🚫 Rejected Paths

### ❌ Crystal as Source of Truth (supersedes codebase)
- **Rejected:** Crystal is a derived view. Codebase is always the single source of truth. If they conflict, codebase wins.

### ❌ Crystal inside repo (committed to git)
- **Rejected:** Crystal is metadata, not source code. Committing it creates noise in git history and PR reviews.

### ❌ Intent-based RAG routing (classify query before searching)
- **Rejected at:** Design stage. Adds an extra LLM call (latency + cost + failure point). Simply prepending Crystal to context achieves the same result with zero complexity.

### ❌ Time-based status heuristics ("no commit in 7 days = crystallized")
- **Rejected:** Time thresholds are subjective and vary per project. Purely structural checks (file exists? test exists? imported?) are deterministic and universally applicable.

---

## 📊 Comparison: Before vs After

| Aspect | Before (INDEX only) | After (INTENT + CRYSTAL + INDEX) |
|--------|--------------------|---------------------------------|
| "What modules exist?" | Grep 50+ index rows, reconstruct | Read CRYSTAL directly |
| "Is this module done?" | Guess from commit dates | Check status: has test? → crystallized |
| "Should we add feature X?" | No guardrail | Check INTENT → auto-reject if out of scope |
| "Why did auth break?" | Grep INDEX (slow, noisy) | CRYSTAL context + INDEX history |
| AI hallucination risk | High (no spatial anchor) | Low (Crystal provides structural ground truth) |
