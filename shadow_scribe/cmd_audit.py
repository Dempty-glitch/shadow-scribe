"""shadow_scribe.cmd_audit — `watchdog audit` command (READ-ONLY)."""

import subprocess
import sys
from pathlib import Path

from shadow_scribe.gemini import call_gemini_audit
from shadow_scribe.prompts import AUDIT_PROMPT
from shadow_scribe.security import _filter_diff


def cmd_audit(plan_path_arg: str = "") -> None:
    """Audit git diff vs implementation plan. READ-ONLY — không ghi file."""
    cwd = Path.cwd()
    print("\n" + "═" * 60)
    print("🔍 SHADOW SCRIBE — Quick Audit")
    print(f"   CWD: {cwd}")
    print("═" * 60)

    # 1. Lấy git diff từ CWD
    result = subprocess.run(
        ["git", "diff"],
        capture_output=True, text=True, cwd=str(cwd)
    )
    if result.returncode != 0:
        print(f"❌ Không thể chạy git diff tại {cwd}")
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
            print("⚠️  Không có staged/unstaged changes. Dùng diff với HEAD~1.")
        else:
            diff = "(Không có thay đổi nào)"

    diff = _filter_diff(diff)
    print(f"✅ Git diff: {len(diff)} chars từ [{cwd.name}]")

    # 2. Tìm implementation_plan.md
    plan = ""
    plan_path = None

    if plan_path_arg:
        p = Path(plan_path_arg)
        if p.exists():
            plan_path = p
        else:
            print(f"⚠️  --plan '{plan_path_arg}' không tồn tại. Tự tìm kiếm...")

    if not plan_path:
        brain_dir = Path.home() / ".gemini" / "antigravity" / "brain"
        candidates = [cwd / "implementation_plan.md"]
        if brain_dir.exists():
            for conv_dir in sorted(brain_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
                candidate = conv_dir / "implementation_plan.md"
                if candidate.exists():
                    candidates.insert(0, candidate)
                    break
        for c in candidates:
            if c.exists():
                plan_path = c
                break

    if plan_path:
        plan = plan_path.read_text(encoding="utf-8")
        print(f"✅ Implementation Plan: ...{str(plan_path)[-50:]} ({len(plan)} chars)")
        print("🔍 Kích hoạt [Hard Audit]")
    else:
        print("⚠️  Không tìm thấy Plan. Chỉ audit git diff (Soft Audit).")

    # 3. Gọi Gemini
    answer = call_gemini_audit(diff, plan, AUDIT_PROMPT)

    # 4. In kết quả — READ-ONLY
    print("\n" + "═" * 60)
    print("📊 Kết quả Audit:")
    print("-" * 40)
    print(answer.strip())
    print("═" * 60)
    print("🚨 READ-ONLY — Không ghi file, không chạm Index.\n")
