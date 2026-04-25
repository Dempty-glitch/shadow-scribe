"""shadow_scribe.io_utils — File I/O, atomic index write, session date parsing."""

import fcntl
import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional


# ─── File reading ─────────────────────────────────────────────────────────────

def read_file(path: Path, label: str, required: bool = True) -> str:
    """Đọc file và trả về nội dung, hoặc exit nếu required và không tồn tại."""
    if not path.exists():
        if required:
            print(f"❌ LỖI: File bắt buộc không tồn tại: {path}")
            sys.exit(1)
        else:
            print(f"⚠️  Không tìm thấy {label}: {path.name} (Bỏ qua)")
            return "(Không có dữ liệu)"
    content = path.read_text(encoding="utf-8")
    print(f"✅ Đọc {label}: {path.name} ({len(content)} chars)")
    return content


# ─── Atomic index write ───────────────────────────────────────────────────────

def _atomic_write_index(index_path: Path, new_row: str) -> None:
    """Ghi Index an toàn: file lock + atomic write."""
    lock_path = index_path.parent / ".index.lock"
    with open(lock_path, "w") as lock_fd:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        try:
            lines = index_path.read_text(encoding="utf-8").splitlines() if index_path.exists() else []
            insert_idx = -1
            for i, line in enumerate(lines):
                if line.startswith("|------|---------"):
                    insert_idx = i + 1
                    break
            if insert_idx != -1:
                lines.insert(insert_idx, new_row)
            else:
                lines.append(new_row)

            fd = tempfile.NamedTemporaryFile(
                mode="w", dir=str(index_path.parent),
                suffix=".tmp", delete=False, encoding="utf-8"
            )
            fd.write("\n".join(lines) + "\n")
            fd.close()
            os.replace(fd.name, str(index_path))
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)


# ─── Session date & project parsing (used by cmd_digest) ─────────────────────

def _parse_session_date(filename: str) -> Optional[datetime]:
    """Parse date từ filename dạng DD_MM_YY.md hoặc DD_MM_YY_N.md."""
    m = re.match(r"(\d{2})_(\d{2})_(\d{2})", filename)
    if not m:
        return None
    dd, mm, yy = m.groups()
    try:
        return datetime.strptime(f"{dd}/{mm}/20{yy}", "%d/%m/%Y")
    except ValueError:
        return None


def _parse_project_from_log(content: str) -> str:
    """Trích xuất Project từ header session log."""
    m = re.search(r'\*\*Project:\*\*\s*`?([\w\-]+)`?', content)
    if m:
        return m.group(1).strip().lower()
    return ""
