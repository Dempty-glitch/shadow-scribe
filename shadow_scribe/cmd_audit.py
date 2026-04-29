"""shadow_scribe.cmd_audit — `watchdog audit` command (READ-ONLY)."""

import subprocess
import sys
from pathlib import Path
from typing import Optional

from shadow_scribe.config import VAULT_DIR
from shadow_scribe.gemini import call_gemini_audit, call_gemini_audit_resolve

from shadow_scribe.security import _filter_diff


def _detect_project(cwd: Path) -> str:
    """Map workspace folder name → project (kebab-case, per GUIDE rules).

    TODO: Future ADR should handle multi-workspace aliases such as
    `my-app-v2` → `my-app`.
    """
    return cwd.name.lower().replace(" ", "-").replace("_", "-")


def _gather_plan_candidates(cwd: Path, project: str) -> list[Path]:
    """Collect all plausible plan candidates from cwd, brain dir, vault.

    Returns deduplicated list, no ordering preference. Caller decides
    resolution strategy (single → use it; multiple → LLM resolve).
    """
    candidates: list[Path] = []

    p = cwd / "implementation_plan.md"
    if p.exists():
        candidates.append(p)

    brain_dir = Path.home() / ".gemini" / "antigravity" / "brain"
    if brain_dir.exists():
        for conv_dir in sorted(brain_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            c = conv_dir / "implementation_plan.md"
            if c.exists():
                candidates.append(c)
                break

    vault_plans = VAULT_DIR / "projects" / project / "plans"
    if vault_plans.exists():
        candidates.extend(sorted(vault_plans.rglob("*.md")))

    seen = set()
    out = []
    for c in candidates:
        rp = c.resolve()
        if rp not in seen:
            seen.add(rp)
            out.append(c)
    return out


def _resolve_plan_via_llm(diff: str, candidates: list[Path]) -> Optional[Path]:
    """Ask Gemini which plan matches the diff. Return None if no clear match.

    Truncates diff to 3000 chars, each plan to 400 chars, to keep prompt
    bounded. LLM is instructed to return only a filename or "none".
    """
    digests = []
    for i, p in enumerate(candidates, 1):
        head = p.read_text(encoding="utf-8")[:400]
        digests.append(f"[{i}] {p.name}\n{head}\n")

    prompt = (
        "You are matching a git diff to its implementation plan.\n\n"
        f"GIT DIFF (truncated):\n{diff[:3000]}\n\n"
        "PLAN CANDIDATES (filename + first 400 chars):\n"
        + "\n".join(digests)
        + "\nReturn STRICTLY one line:\n"
        "- The exact filename of the matching plan, OR\n"
        "- The literal string 'none' if no plan clearly matches.\n"
        "Be strict: if diff doesn't clearly implement a candidate plan, "
        "return 'none'. Do not force a pick."
    )
    pick_lines = call_gemini_audit_resolve(prompt).strip().splitlines()
    pick = pick_lines[0].strip() if pick_lines else ""
    if pick.lower() == "none" or not pick:
        return None
    for c in candidates:
        if c.name == pick:
            return c
    return None


def _resolve_plan_path(cwd: Path, diff: str, plan_path_arg: str = "") -> Optional[Path]:
    """Resolve audit plan path via explicit arg, single candidate, or Stage 0 LLM."""
    plan_path = None
    project = _detect_project(cwd)

    if plan_path_arg:
        p = Path(plan_path_arg)
        if p.exists():
            plan_path = p
        else:
            print(f"⚠️  --plan '{plan_path_arg}' does not exist. Falling back to auto-resolve...")

    if not plan_path:
        candidates = _gather_plan_candidates(cwd, project)
        if len(candidates) == 0:
            pass
        elif len(candidates) == 1:
            plan_path = candidates[0]
            print(f"✅ Single plan candidate: {plan_path.name}")
        else:
            print(f"🤔 {len(candidates)} plan candidates — Stage 0 resolving via LLM...")
            plan_path = _resolve_plan_via_llm(diff, candidates)
            if plan_path:
                print(f"✅ LLM resolved → {plan_path.name}")
            else:
                print("❌ Stage 0: LLM could not match diff to any plan.")
                print(f"   Candidates seen: {[c.name for c in candidates]}")
                print("   Pass --plan <path> explicitly, or run audit without plan (Soft Audit).")
                sys.exit(1)

    return plan_path


def cmd_audit(plan_path_arg: str = "") -> None:
    """Audit git diff vs implementation plan. READ-ONLY — does not write files."""
    cwd = Path.cwd()
    print("\n" + "═" * 60)
    print("🔍 SHADOW SCRIBE — Quick Audit")
    print(f"   CWD: {cwd}")
    print("═" * 60)

    # 1. Get git diff from CWD
    result = subprocess.run(
        ["git", "diff"],
        capture_output=True, text=True, cwd=str(cwd)
    )
    if result.returncode != 0:
        print(f"❌ Cannot run git diff at {cwd}")
        print(f"   {result.stderr.strip()}")
        sys.exit(1)

    diff = result.stdout.strip()
    if not diff:
        result2 = subprocess.run(
            ["git", "diff", "HEAD~1"],
            capture_output=True, text=True, cwd=str(cwd)
        )
        if result2.returncode == 0 and result2.stdout.strip():
            diff = result2.stdout.strip()
            print("⚠️  No staged/unstaged changes. Using diff with HEAD~1.")
        else:
            diff = "(No changes detected)"

    diff = _filter_diff(diff)
    print(f"✅ Git diff: {len(diff)} chars from [{cwd.name}]")

    # 2. Resolve plan via Stage 0
    plan = ""
    plan_path = _resolve_plan_path(cwd, diff, plan_path_arg)

    if plan_path:
        plan = plan_path.read_text(encoding="utf-8")
        print(f"✅ Implementation Plan: ...{str(plan_path)[-50:]} ({len(plan)} chars)")
        print("🔍 Activated [Hard Audit]")
    else:
        print("⚠️  No Plan found. Auditing git diff only (Soft Audit).")

    # 3. Call Gemini
    answer = call_gemini_audit(diff, plan)

    # 4. Print results — READ-ONLY
    print("\n" + "═" * 60)
    print("📊 Audit Result:")
    print("-" * 40)
    print(answer.strip())
    print("═" * 60)
    print("🚨 READ-ONLY — No files written, Index untouched.\n")
