"""shadow_scribe.cmd_doctor — `watchdog doctor` deterministic vault lint."""

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from shadow_scribe.config import VAULT_DIR
from shadow_scribe.io_utils import _split_md_row

Severity = Literal["ERROR", "WARN"]

_SESSION_PATH_RE = re.compile(r"\((sessions/[^)]+\.md)\)")
_ADR_FILE_RE = re.compile(r"^(\d{3})_.*\.md$")
_ADR_INDEX_ROW_RE = re.compile(r"^\|\s*(\d{3})\s*\|")

_REQUIRED_SECTIONS = [
    "## 📊 Matrix Tổng Quan",
    "## ⏱️ Timeline",
    "## 🔧 Code Changes (từ git diff)",
    "## 💡 Quyết định quan trọng",
    "## 🩸 Blood Lessons (Lỗi đã gặp & Bài học)",
    "## ⚠️ Risks & Bài học",
    "## ✅ Status",
    "## 🔄 Next Session",
    "## 📎 Artifacts & ADR",
]


@dataclass
class Finding:
    check_id: str
    severity: Severity
    message: str
    location: str = ""


def _detect_project(cwd: Path) -> str:
    """Map workspace folder name → project name using GUIDE kebab-case rule."""
    return cwd.name.lower().replace(" ", "-").replace("_", "-")


def _extract_session_path(cell: str) -> str:
    match = _SESSION_PATH_RE.search(cell)
    return match.group(1) if match else ""


def _check_index_rows_exist(vault_dir: Path) -> list[Finding]:
    """For each 00_INDEX_MATRIX.md row, verify referenced session log exists."""
    findings: list[Finding] = []
    index_path = vault_dir / "00_INDEX_MATRIX.md"
    if not index_path.exists():
        return [Finding("A", "ERROR", "00_INDEX_MATRIX.md missing", str(index_path))]

    for line in index_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or stripped.startswith("|------"):
            continue
        cells = _split_md_row(stripped)
        if not cells or cells[0].lower() in ("ngày", "date"):
            continue
        for cell in cells:
            path_str = _extract_session_path(cell)
            if path_str:
                full = vault_dir / path_str
                if not full.exists():
                    findings.append(Finding(
                        "A", "ERROR",
                        f"INDEX row references missing file: {path_str}",
                        stripped[:120],
                    ))
                break
    return findings


def _check_adr_index_match(repo_dir: Path) -> list[Finding]:
    """ADR_INDEX.md rows ↔ docs/adr/*.md files: bijection."""
    findings: list[Finding] = []
    adr_dir = repo_dir / "docs" / "adr"
    index_path = adr_dir / "ADR_INDEX.md"
    if not adr_dir.exists() or not index_path.exists():
        return [Finding("B", "WARN", "docs/adr/ or ADR_INDEX.md missing", str(adr_dir))]

    file_ids: set[str] = set()
    for path in adr_dir.glob("[0-9][0-9][0-9]_*.md"):
        match = _ADR_FILE_RE.match(path.name)
        if match:
            file_ids.add(match.group(1))

    row_ids: set[str] = set()
    for line in index_path.read_text(encoding="utf-8").splitlines():
        match = _ADR_INDEX_ROW_RE.match(line)
        if match:
            row_ids.add(match.group(1))

    for file_id in sorted(file_ids - row_ids):
        findings.append(Finding(
            "B", "WARN",
            f"ADR file {file_id} exists but no row in ADR_INDEX.md",
            file_id,
        ))
    for row_id in sorted(row_ids - file_ids):
        findings.append(Finding(
            "B", "WARN",
            f"ADR_INDEX row {row_id} but no docs/adr/{row_id}_*.md file",
            row_id,
        ))
    return findings


def _check_adr_sync(repo_dir: Path, vault_dir: Path, project: str) -> list[Finding]:
    """Verify vault adr/ mirrors repo docs/adr/."""
    findings: list[Finding] = []
    src = repo_dir / "docs" / "adr"
    dst = vault_dir / "projects" / project / "adr"
    if not src.exists():
        return findings
    if not dst.exists():
        return [Finding("C", "WARN", f"Vault adr/ missing — autosync never ran? {dst}", str(dst))]

    for src_file in sorted(src.glob("*.md")):
        dst_file = dst / src_file.name
        if not dst_file.exists():
            findings.append(Finding(
                "C", "WARN",
                f"ADR not mirrored to vault: {src_file.name}",
                str(src_file),
            ))
        elif src_file.read_text(encoding="utf-8") != dst_file.read_text(encoding="utf-8"):
            findings.append(Finding(
                "C", "WARN",
                f"ADR drift: vault content differs from repo: {src_file.name}",
                str(dst_file),
            ))
    return findings


def _check_session_sections(vault_dir: Path) -> list[Finding]:
    """Each vault-global session log must contain required scribe headings."""
    findings: list[Finding] = []
    sessions_root = vault_dir / "sessions"
    if not sessions_root.exists():
        return findings

    for log in sorted(sessions_root.rglob("*.md")):
        text = log.read_text(encoding="utf-8")
        missing = [heading for heading in _REQUIRED_SECTIONS if heading not in text]
        if missing:
            findings.append(Finding(
                "D", "WARN",
                f"Session log missing sections: {', '.join(missing)}",
                str(log.relative_to(vault_dir)),
            ))
    return findings


def _print_findings(findings: list[Finding]) -> None:
    errors = [f for f in findings if f.severity == "ERROR"]
    warns = [f for f in findings if f.severity == "WARN"]

    if errors:
        print(f"\n🔴 {len(errors)} ERROR(s):")
        for finding in errors:
            print(f"  [{finding.check_id}] {finding.message}")
            if finding.location:
                print(f"        → {finding.location}")
    if warns:
        print(f"\n🟡 {len(warns)} WARN(s):")
        for finding in warns:
            print(f"  [{finding.check_id}] {finding.message}")
            if finding.location:
                print(f"        → {finding.location}")


def cmd_doctor() -> None:
    """Read-only deterministic lint over vault + repo state."""
    cwd = Path.cwd()
    project = _detect_project(cwd)

    print("\n" + "═" * 60)
    print("🩺 SHADOW SCRIBE — Doctor (vault lint)")
    print(f"   Repo: {cwd}")
    print(f"   Vault: {VAULT_DIR}")
    print(f"   Project: {project}")
    print("═" * 60)

    all_findings: list[Finding] = []
    all_findings += _check_index_rows_exist(VAULT_DIR)
    all_findings += _check_adr_index_match(cwd)
    all_findings += _check_adr_sync(cwd, VAULT_DIR, project)
    all_findings += _check_session_sections(VAULT_DIR)

    errors = [f for f in all_findings if f.severity == "ERROR"]
    warns = [f for f in all_findings if f.severity == "WARN"]

    if not all_findings:
        print("✅ All checks passed. Vault is clean.\n")
        return

    _print_findings(all_findings)
    print("\n" + "═" * 60)
    print(f"Summary: {len(errors)} error(s), {len(warns)} warning(s)")
    print("🚨 READ-ONLY — No files written.\n")

    if errors:
        sys.exit(1)
