"""Tests for watchdog doctor deterministic vault lint."""

import pytest

import shadow_scribe.cmd_doctor as doctor


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _index_row(session_path):
    return (
        "| 30/04 | shadow-scribe | ws | TL;DR | "
        f"[→]({session_path}) | — | #tag |"
    )


def _complete_session_log():
    return "\n".join([
        "# Session Log",
        "## 📊 Matrix Tổng Quan",
        "## ⏱️ Timeline",
        "## 🔧 Code Changes (từ git diff)",
        "## 💡 Quyết định quan trọng",
        "## 🩸 Blood Lessons (Lỗi đã gặp & Bài học)",
        "## ⚠️ Risks & Bài học",
        "## ✅ Status",
        "## 🔄 Next Session",
        "## 📎 Artifacts & ADR",
    ])


def test_check_index_rows_exist_all_present(tmp_path):
    vault = tmp_path / "vault"
    session_path = "sessions/2026-04/30_04_26.md"
    _write(vault / "00_INDEX_MATRIX.md", "\n".join([
        "| Ngày | Project | Workspace | TL;DR | Session | Artifacts | Tags |",
        "|------|---------|-----------|-------|---------|-----------|------|",
        _index_row(session_path),
        _index_row("sessions/2026-04/29_04_26.md"),
    ]))
    _write(vault / session_path, "# log")
    _write(vault / "sessions/2026-04/29_04_26.md", "# log")

    assert doctor._check_index_rows_exist(vault) == []


def test_check_index_rows_missing_file(tmp_path):
    vault = tmp_path / "vault"
    _write(vault / "00_INDEX_MATRIX.md", _index_row("sessions/2026-04/missing.md"))

    findings = doctor._check_index_rows_exist(vault)

    assert len(findings) == 1
    assert findings[0].check_id == "A"
    assert findings[0].severity == "ERROR"


def test_check_adr_index_match_clean(tmp_path):
    repo = tmp_path / "repo"
    for adr_id in ("001", "002", "011"):
        _write(repo / "docs" / "adr" / f"{adr_id}_example.md", "# ADR")
    _write(repo / "docs" / "adr" / "ADR_INDEX.md", "\n".join([
        "| 001 | One | 2026 | ✅ | [→](001_example.md) |",
        "| 002 | Two | 2026 | ✅ | [→](002_example.md) |",
        "| 011 | Doctor | 2026 | ✅ | [→](011_example.md) |",
    ]))

    assert doctor._check_adr_index_match(repo) == []


def test_check_adr_index_orphan_file(tmp_path):
    repo = tmp_path / "repo"
    _write(repo / "docs" / "adr" / "011_watchdog_doctor_lint.md", "# ADR")
    _write(repo / "docs" / "adr" / "ADR_INDEX.md", "| ID | Issue | Date | Status | File |")

    findings = doctor._check_adr_index_match(repo)

    assert len(findings) == 1
    assert "ADR file 011 exists" in findings[0].message


def test_check_adr_index_orphan_row(tmp_path):
    repo = tmp_path / "repo"
    _write(repo / "docs" / "adr" / "001_example.md", "# ADR")
    _write(repo / "docs" / "adr" / "ADR_INDEX.md", "\n".join([
        "| 001 | One | 2026 | ✅ | [→](001_example.md) |",
        "| 099 | Missing | 2026 | ✅ | [→](099_missing.md) |",
    ]))

    findings = doctor._check_adr_index_match(repo)

    assert len(findings) == 1
    assert findings[0].check_id == "B"
    assert "ADR_INDEX row 099" in findings[0].message


def test_check_adr_sync_clean(tmp_path):
    repo = tmp_path / "repo"
    vault = tmp_path / "vault"
    _write(repo / "docs" / "adr" / "011.md", "# same")
    _write(vault / "projects" / "shadow-scribe" / "adr" / "011.md", "# same")

    assert doctor._check_adr_sync(repo, vault, "shadow-scribe") == []


def test_check_adr_sync_drift(tmp_path):
    repo = tmp_path / "repo"
    vault = tmp_path / "vault"
    _write(repo / "docs" / "adr" / "011.md", "# repo")
    _write(vault / "projects" / "shadow-scribe" / "adr" / "011.md", "# vault")

    findings = doctor._check_adr_sync(repo, vault, "shadow-scribe")

    assert len(findings) == 1
    assert findings[0].check_id == "C"
    assert "ADR drift" in findings[0].message


def test_check_adr_sync_missing_in_vault(tmp_path):
    repo = tmp_path / "repo"
    vault = tmp_path / "vault"
    _write(repo / "docs" / "adr" / "011.md", "# repo")
    (vault / "projects" / "shadow-scribe" / "adr").mkdir(parents=True)

    findings = doctor._check_adr_sync(repo, vault, "shadow-scribe")

    assert len(findings) == 1
    assert "ADR not mirrored to vault" in findings[0].message


def test_check_session_sections_complete(tmp_path):
    vault = tmp_path / "vault"
    _write(vault / "sessions" / "2026-04" / "30_04_26.md", _complete_session_log())

    assert doctor._check_session_sections(vault) == []


def test_check_session_sections_missing(tmp_path):
    vault = tmp_path / "vault"
    text = _complete_session_log().replace("## 🔧 Code Changes (từ git diff)\n", "")
    _write(vault / "sessions" / "2026-04" / "30_04_26.md", text)

    findings = doctor._check_session_sections(vault)

    assert len(findings) == 1
    assert findings[0].check_id == "D"
    assert "## 🔧 Code Changes (từ git diff)" in findings[0].message


def test_cmd_doctor_e2e_clean_exit_zero(capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(doctor, "VAULT_DIR", tmp_path / "vault")
    monkeypatch.setattr(doctor, "_check_index_rows_exist", lambda vault_dir: [])
    monkeypatch.setattr(doctor, "_check_adr_index_match", lambda repo_dir: [])
    monkeypatch.setattr(doctor, "_check_adr_sync", lambda repo_dir, vault_dir, project: [])
    monkeypatch.setattr(doctor, "_check_session_sections", lambda vault_dir: [])

    doctor.cmd_doctor()

    assert "All checks passed" in capsys.readouterr().out


def test_cmd_doctor_e2e_error_exits_one(capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(doctor, "VAULT_DIR", tmp_path / "vault")
    monkeypatch.setattr(
        doctor,
        "_check_index_rows_exist",
        lambda vault_dir: [doctor.Finding("A", "ERROR", "missing", "row")],
    )
    monkeypatch.setattr(doctor, "_check_adr_index_match", lambda repo_dir: [])
    monkeypatch.setattr(doctor, "_check_adr_sync", lambda repo_dir, vault_dir, project: [])
    monkeypatch.setattr(doctor, "_check_session_sections", lambda vault_dir: [])

    with pytest.raises(SystemExit) as exc:
        doctor.cmd_doctor()

    assert exc.value.code == 1
    assert "1 ERROR" in capsys.readouterr().out
