# ADR-008: Agent-Native Philosophy — Drop PyPI & Custom Skills

| Field | Value |
|-------|-------|
| **Date** | 26/04/2026 |
| **Project** | shadow-scribe |
| **Status** | 🟢 ACCEPTED |
| **Related Session** | [→](../../sessions/2026-04/26_04_26_3.md) |

## Context

During onboarding review (v1.3.1 → v1.3.2), two distribution features were evaluated:
1. **PyPI package** (`pip install shadow-scribe`) — standard Python distribution.
2. **Custom Skills** (agent-specific command plugins) — extending the `watchdog` CLI with user-defined skills.

The question: Should Shadow Scribe invest in these distribution mechanisms to reach more users?

---

## 📍 Decision (The Chosen Path)

> **Chosen: Neither. Stay Agent-Native (git clone + GUIDE.md is the entire distribution).**

### Rationale

**Who is the user?** Not a human developer running `pip install`. The user is an **AI Agent** (Cursor, Windsurf, Claude Code, Antigravity) that:
- Reads a git repo natively (no install step needed)
- Understands `GUIDE.md` as its operations manual
- Executes `python watchdog_scribe.py` directly

**PyPI adds zero value for this user.** An AI Agent does not:
- Browse PyPI to discover tools
- Run `pip install` in its workflow
- Need semver-resolved dependency management

**Custom Skills add maintenance debt.** An AI Agent does not:
- Need a plugin registry — it reads `GUIDE.md` and adapts
- Need formal skill definitions — natural language instructions are more flexible
- Benefit from rigid CLI extensions — it already has full shell access

### The Distribution Model

```
Human shares repo link → Agent clones → Agent reads GUIDE.md → Agent operates
```

That's it. No package manager. No skill framework. No registry. The repo IS the product.

---

## 🚫 Rejected Paths

### ❌ PyPI Distribution
- **Rejected at:** Design review (v1.3.2 onboarding audit)
- **Reason:** Target user (AI Agent) never runs `pip install`. Adds packaging ceremony (setup.py, MANIFEST.in, CI release pipeline) with zero ROI. If a human wants to use it, `git clone` + `setup.sh` works.
- **Revisit when:** Shadow Scribe gains Python library consumers (other tools importing `shadow_scribe` as a dependency). Currently: zero evidence of this need.

### ❌ Custom Skills Framework
- **Rejected at:** Design review (v1.3.2 onboarding audit)
- **Reason:** Skills are rigid contracts. AI Agents work better with natural language instructions (`GUIDE.md`) than formal plugin interfaces. Adding a skill registry creates a second source of truth that can drift from GUIDE.md.
- **Revisit when:** Shadow Scribe supports 3+ distinct agent types with incompatible instruction formats.

---

## 📊 Comparison Matrix

| Criteria | PyPI ❌ | Skills ❌ | **Agent-Native ✅** |
|----------|--------|----------|---------------------|
| Setup friction | `pip install` (easy for humans, irrelevant for agents) | Skill discovery + config | **`git clone` + read GUIDE.md** |
| Maintenance cost | CI release pipeline, versioning | Plugin API surface, backward compat | **Zero — repo is self-contained** |
| Agent compatibility | Irrelevant (agents don't pip install) | Rigid (formal contracts) | **Native (agents read markdown)** |
| Human onboarding | Familiar | Unfamiliar | **Familiar (git clone)** |
| Token cost | 0 | Skill loading overhead | **0** |
