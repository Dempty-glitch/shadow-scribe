"""shadow_scribe.io_utils — File I/O, atomic index write, session date parsing."""

import fcntl
import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional


# ─── GUIDE.md autosync (repo → vault, fixes KI-003 drift) ────────────────────

def sync_file_if_differ(source: Path, dest: Path) -> bool:
    """Copy source → dest if content differs. Returns True if copy happened.

    Pure utility — no prints, no exits. Caller decides UX.
    """
    if not source.exists():
        return False
    src_content = source.read_text(encoding="utf-8")
    if dest.exists() and dest.read_text(encoding="utf-8") == src_content:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(src_content, encoding="utf-8")
    return True


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


# ─── Markdown table row parser (B2) ──────────────────────────────────────────

_NULL_PLACEHOLDER = "\x00"  # Sentinel for escaped pipes during split


def _split_md_row(line: str) -> list[str]:
    r"""Split a Markdown table row into cells, handling escaped pipes (\|).

    Strategy: swap \| → \x00 before split, restore \x00 → | after.
    Defensive: asserts input contains no raw null bytes (would corrupt parsing).

    Returns list of stripped cell strings (excluding leading/trailing empty
    strings from surrounding '|' delimiters).

    Example:
        '| A \| B | C |' → ['A | B', 'C']
    """
    assert _NULL_PLACEHOLDER not in line, (
        f"_split_md_row: input contains null byte (\\x00) which is reserved "
        f"as placeholder. Input: {line!r}"
    )
    # Swap escaped pipes to placeholder, split, restore
    escaped = line.replace("\\|", _NULL_PLACEHOLDER)
    parts = escaped.split("|")
    cells = [p.replace(_NULL_PLACEHOLDER, "|").strip() for p in parts]
    # Drop leading/trailing empty strings from surrounding '|'
    if cells and cells[0] == "":
        cells = cells[1:]
    if cells and cells[-1] == "":
        cells = cells[:-1]
    return cells


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
