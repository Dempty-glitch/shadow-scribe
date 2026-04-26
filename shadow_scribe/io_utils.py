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
    """Read file and return contents, or exit if required and missing."""
    if not path.exists():
        if required:
            print(f"❌ ERROR: Required file does not exist: {path}")
            sys.exit(1)
        else:
            print(f"⚠️  {label} not found: {path.name} (Skipping)")
            return "(No data available)"
    content = path.read_text(encoding="utf-8")
    print(f"✅ Read {label}: {path.name} ({len(content)} chars)")
    return content


# ─── Atomic index write ───────────────────────────────────────────────────────

def _atomic_write_index(index_path: Path, new_row: str) -> None:
    """Write Index safely: file lock + atomic write."""
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
    """Parse date from filename format DD_MM_YY.md or DD_MM_YY_N.md."""
    m = re.match(r"(\d{2})_(\d{2})_(\d{2})", filename)
    if not m:
        return None
    dd, mm, yy = m.groups()
    try:
        return datetime.strptime(f"{dd}/{mm}/20{yy}", "%d/%m/%Y")
    except ValueError:
        return None


def _parse_project_from_log(content: str) -> str:
    """Extract Project from session log header."""
    m = re.search(r'\*\*Project:\*\*\s*`?([\w\-]+)`?', content)
    if m:
        return m.group(1).strip().lower()
    return ""
