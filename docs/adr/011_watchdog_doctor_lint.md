# ADR-011 — `watchdog doctor`: deterministic vault lint

**Status:** ✅ ACCEPTED
**Date:** 2026-04-30

## Context
Vault state drifts in observed classes such as KI-001 INDEX path mismatch,
KI-006 ADR folder drift, and missing session sections. Each is a rule-based
invariant — no semantic judgment needed.

Today: drift is discovered ad-hoc when an agent trips on it. Cost = lost
session, manual fix, sometimes a new KI entry.

## Decision
Add `watchdog doctor` — read-only, 100% deterministic lint pass over vault
+ repo state. Four checks in v1:

- A: INDEX rows reference session log files that exist on disk.
- B: repo `docs/adr/*.md` and `docs/adr/ADR_INDEX.md` rows match 1-1.
- C: vault `projects/{project}/adr/*.md` mirrors repo `docs/adr/*.md`.
- D: session logs contain the current required scribe sections.

Pattern: gather facts → apply rules → print report. No LLM, no writes.
Exits 1 on any ERROR-severity finding (WARN does not fail).

## Rejected
- **LLM-assisted lint.** Doctor checks are syntactic/structural, not
  semantic. LLM adds latency + cost + non-determinism for zero benefit
  here. Audit needs LLM because diff↔plan is semantic; doctor does not.
- **Auto-fix mode.** v1 = report only. Auto-fix is a separate decision
  (which fixes are safe? which need human review?). Defer to v2 if
  demand exists.
- **CRYSTAL path/symbol checks (E1/E2).** CRYSTAL does not yet have a
  stable path-ref convention; backticks may be symbols, concepts, or file
  names. Doctor v1 lints drift classes already observed in production
  (KI-001, KI-006), not speculative checks.

## Implications
- New CLI subcommand `watchdog doctor` (no args in v1).
- New module `shadow_scribe/cmd_doctor.py`.
- Doctor exits 1 on ERROR — usable in pre-commit / CI later (out of
  scope for this PR; user opt-in only).
- Future ADRs may extend doctor with new check IDs without changing the
  framework.
