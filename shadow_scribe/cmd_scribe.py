"""shadow_scribe.cmd_scribe — `watchdog scribe` command."""

import re
import shutil
from datetime import datetime
from pathlib import Path

from shadow_scribe.config import (
    INDEX_FILE,
    RAW_LOGS_DIR,
    SESSIONS_DIR,
    TRASH_DIR,
)
from shadow_scribe.gemini import call_gemini, parse_output
from shadow_scribe.io_utils import _atomic_write_index, read_file
from shadow_scribe.security import _filter_diff


def cmd_scribe(mock: bool) -> None:
    """Compile session brief + git diff → session log + index row."""
    print("\n" + "═" * 60)
    print("🛡️  SHADOW SCRIBE — Session Compiler")
    print("═" * 60)

    project_dir = None

    if mock:
        print("🧪 MODE: DRY-RUN (mock data, không ghi file)\n")
        brief_path = RAW_LOGS_DIR / "session_brief_mock.md"
        diff_path = RAW_LOGS_DIR / "git_diff_mock.txt"
    else:
        # ── Phase 3.3: Directory-based Routing ──────────────────────────────
        # Ưu tiên: scan raw_logs/ tìm subdirectory chứa session_brief.md
        # Fallback: đọc flat file (backward compat với v1.1.0)
        project_subdirs = sorted(
            [d for d in RAW_LOGS_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")],
            key=lambda d: d.stat().st_mtime,
            reverse=True,
        ) if RAW_LOGS_DIR.exists() else []

        if project_subdirs:
            for d in project_subdirs:
                if (d / "session_brief.md").exists():
                    project_dir = d
                    break
            if not project_dir:
                project_dir = project_subdirs[0]  # Fallback: thư mục mới nhất

        if project_dir:
            print(f"📁 Project directory: raw_logs/{project_dir.name}")
            brief_path = project_dir / "session_brief.md"
            diff_path = project_dir / "git_diff.txt"
        else:
            # Backward compat: flat structure (v1.1.0)
            print("⚠️  Không tìm thấy project subdirectory. Fallback: flat raw_logs/ (v1.1.0 compat)")
            brief_path = RAW_LOGS_DIR / "session_brief.md"
            diff_path = RAW_LOGS_DIR / "git_diff.txt"

    # 1. Đọc input
    brief = read_file(brief_path, "Session Brief", required=True)
    diff = read_file(diff_path, "Git Diff", required=False)
    diff = _filter_diff(diff)

    # 1.5. Trích xuất Plan Path và Load Plan (Tầng 2 Audit)
    plan_content = ""
    plan_match = re.search(r'Plan Path:\s*(.+)', brief)
    if plan_match:
        plan_path_str = plan_match.group(1).strip()
        if (
            plan_path_str
            and "absolute_path" not in plan_path_str
            and "_{" not in plan_path_str
            and plan_path_str not in ("(none)", "—")
        ):
            plan_path = Path(plan_path_str)
            if plan_path.exists() and plan_path.is_file():
                plan_content = read_file(plan_path, "Implementation Plan", required=False)
            else:
                print(f"⚠️  Plan Path được khai báo là '{plan_path_str}' nhưng file không tồn tại. Bỏ qua Plan.")

    print()

    # 2. Gọi Gemini
    raw_output = call_gemini(brief, diff, plan_content)
    print(f"✅ Gemini trả về {len(raw_output)} chars\n")

    # 3. Parse output
    session_log, index_row = parse_output(raw_output)

    # 4. In kết quả ra terminal
    print("─" * 60)
    print("📄 PHẦN 1: Full Session Log")
    print("─" * 60)
    print(session_log)
    print()
    print("─" * 60)
    print("📋 PHẦN 2: Index Row (1 dòng để chèn vào INDEX_MATRIX)")
    print("─" * 60)
    print(index_row)
    print()

    if mock:
        print("═" * 60)
        print("🧪 DRY-RUN hoàn tất — không có file nào được ghi.")
        print("Nếu output trên đẹp → chạy lại KHÔNG có --mock để lưu thật.")
        print("═" * 60)
    else:
        # Lấy ngày từ brief
        date_match = re.search(r'Date:\s*(\d{4})-(\d{2})-(\d{2})', brief)
        if date_match:
            yyyy, mm, dd = date_match.groups()
        else:
            now = datetime.now()
            yyyy, mm, dd = now.strftime("%Y"), now.strftime("%m"), now.strftime("%d")

        session_folder = SESSIONS_DIR / f"{yyyy}-{mm}"
        session_folder.mkdir(parents=True, exist_ok=True)
        session_file = session_folder / f"{dd}_{mm}_{yyyy[2:]}.md"

        counter = 1
        while session_file.exists():
            session_file = session_folder / f"{dd}_{mm}_{yyyy[2:]}_{counter}.md"
            counter += 1

        session_file.write_text(session_log, encoding="utf-8")

        if INDEX_FILE.exists():
            _atomic_write_index(INDEX_FILE, index_row)

        # ── Phase 3.3: Soft-Delete → Trash (không xóa vĩnh viễn) ────────────
        trash_slot = TRASH_DIR / datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
        trash_slot.mkdir(parents=True, exist_ok=True)
        if project_dir and project_dir.exists():
            shutil.move(str(project_dir), str(trash_slot / project_dir.name))
            print(f"🗑️  raw_logs/{project_dir.name}/ → trash/{trash_slot.name}/")
        else:
            flat_slot = trash_slot / "_flat"
            flat_slot.mkdir(parents=True, exist_ok=True)
            if brief_path.exists():
                shutil.move(str(brief_path), str(flat_slot / brief_path.name))
            if diff_path.exists():
                shutil.move(str(diff_path), str(flat_slot / diff_path.name))
            print(f"🗑️  raw_logs/ (flat) → trash/{trash_slot.name}/_flat/")

        # ── Auto-cleanup: Dọn rác cũ hơn 30 ngày ────────────────────────────
        retention_days = 30
        now_ts = datetime.now().timestamp()
        deleted_count = 0
        if TRASH_DIR.exists():
            for slot in TRASH_DIR.iterdir():
                if slot.is_dir() and not slot.name.startswith("."):
                    if (now_ts - slot.stat().st_mtime) > (retention_days * 86400):
                        shutil.rmtree(str(slot), ignore_errors=True)
                        deleted_count += 1

        print("\n" + "═" * 60)
        print(f"✅ Session Log: {session_file}")

        cleanup_msg = f" (đã dọn {deleted_count} folder rác > 30 ngày)" if deleted_count > 0 else ""
        print(f"✅ Index đã cập nhật | 🗑️ raw_logs → trash/{cleanup_msg}")

        risks_match = re.search(r'## ⚠️ Risks.*?(?=\n## |\Z)', session_log, re.DOTALL)
        if risks_match:
            risks_text = risks_match.group(0).strip()
            has_real_risk = any(c in risks_text for c in ['🔴', '🟡'])
            if has_real_risk:
                print("\n🚨 RISK PHÁT HIỆN:")
                print("-" * 40)
                print(risks_text)
            else:
                print("🔍 Audit Pass: Không phát hiện Risk 🔴/🟡")
        print("═" * 60)

    print()
