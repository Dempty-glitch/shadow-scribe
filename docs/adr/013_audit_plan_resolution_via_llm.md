# ADR-013 — Audit Plan Resolution via LLM

**Status:** ✅ ACCEPTED
**Date:** 2026-04-30
**Closes:** KI-005

## Context
`watchdog audit` Stage 1 needs an implementation plan to compare git diff
against. The plan-pick logic was filename-rigid (`implementation_plan.md`
only) and ignored the vault `plans/` folder entirely. Result: Plan-First
Discipline (GUIDE) was a zombie — agent dumps to vault, audit never reads
there.

Three options considered:

- **A. Convention-strict.** All plans named `implementation_plan.md`,
  scoped by subfolder. Pro: deterministic. Con: gò agent vibe, migration
  burden, parallel-task race remains.
- **B. Heuristic broaden.** Glob `plans/**/*.md` by mtime, pick newest.
  Pro: zero convention. Con: race tệ hơn A, picks artifacts as plans.
- **C. LLM resolve at junction (CHOSEN).** Glob all candidates, LLM picks
  match. Pro: agent-vibe-friendly, self-diagnoses on no-match (returns
  `none`), no migration. Con: +1 Gemini call when ambiguous (~1s).

## Decision
Add Stage 0 to `cmd_audit`. When >1 plan candidate exists, call Gemini
with diff + candidate digests, ask which plan matches. On `none`, fail
explicit (require `--plan`).

Pattern aligns with ADR-006/007 (cmd_query Stage 1+2): deterministic
gather → LLM judge at junction → deterministic act.

## Rejected
- A: too rigid for vibe coding, doesn't triệt race anyway.
- B: silent wrong-pick is the failure mode we're fixing, not introducing.

## Implications
- Vault `plans/**/*.md` is now first-class input to audit.
- `cmd_audit` gains 1 Gemini call dependency (only when ambiguous).
- New env requirement: GEMINI_API_KEY for audit (was already required for
  Stage 1, no change in practice).
