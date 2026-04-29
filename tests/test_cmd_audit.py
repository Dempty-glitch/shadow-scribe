"""Tests for watchdog audit Stage 0 plan resolution."""

import pytest

import shadow_scribe.cmd_audit as audit


def _set_home(monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


def _set_vault(monkeypatch, tmp_path):
    vault = tmp_path / "vault"
    monkeypatch.setattr(audit, "VAULT_DIR", vault)
    return vault


def test_gather_no_candidates(tmp_path, monkeypatch):
    """No cwd plan, no brain plan, no vault plans → []."""
    _set_home(monkeypatch, tmp_path)
    _set_vault(monkeypatch, tmp_path)
    cwd = tmp_path / "shadow scribe"
    cwd.mkdir()

    assert audit._gather_plan_candidates(cwd, "shadow-scribe") == []


def test_gather_vault_only(tmp_path, monkeypatch):
    """Vault plans/ supports any .md filename."""
    _set_home(monkeypatch, tmp_path)
    vault = _set_vault(monkeypatch, tmp_path)
    cwd = tmp_path / "shadow scribe"
    cwd.mkdir()
    plans_dir = vault / "projects" / "shadow-scribe" / "plans"
    plans_dir.mkdir(parents=True)
    plan = plans_dir / "stage2_topk_spec.md"
    plan.write_text("# Stage 2 plan", encoding="utf-8")

    assert audit._gather_plan_candidates(cwd, "shadow-scribe") == [plan]


def test_gather_dedup(tmp_path, monkeypatch):
    """Same file via cwd and vault symlink is returned once."""
    _set_home(monkeypatch, tmp_path)
    vault = _set_vault(monkeypatch, tmp_path)
    cwd = tmp_path / "shadow scribe"
    cwd.mkdir()
    plan = cwd / "implementation_plan.md"
    plan.write_text("# Plan", encoding="utf-8")
    plans_dir = vault / "projects" / "shadow-scribe" / "plans"
    plans_dir.mkdir(parents=True)
    (plans_dir / "implementation_plan.md").symlink_to(plan)

    assert audit._gather_plan_candidates(cwd, "shadow-scribe") == [plan]


def test_resolve_single_skips_llm(tmp_path, monkeypatch):
    """Single candidate resolves directly without LLM."""
    cwd = tmp_path / "shadow scribe"
    cwd.mkdir()
    plan = cwd / "implementation_plan.md"
    plan.write_text("# Plan", encoding="utf-8")
    called = False

    def fake_resolve(diff, candidates):
        nonlocal called
        called = True
        return candidates[0]

    monkeypatch.setattr(audit, "_gather_plan_candidates", lambda cwd, project: [plan])
    monkeypatch.setattr(audit, "_resolve_plan_via_llm", fake_resolve)

    assert audit._resolve_plan_path(cwd, "diff") == plan
    assert called is False


def test_resolve_multi_picks_match(tmp_path, monkeypatch):
    """LLM filename match resolves to the matching candidate path."""
    first = tmp_path / "old_plan.md"
    second = tmp_path / "stage2_topk_spec.md"
    first.write_text("# Old", encoding="utf-8")
    second.write_text("# Stage 2", encoding="utf-8")
    monkeypatch.setattr(
        audit,
        "call_gemini_audit_resolve",
        lambda prompt: "stage2_topk_spec.md",
    )

    assert audit._resolve_plan_via_llm("diff", [first, second]) == second


def test_resolve_multi_returns_none(tmp_path, monkeypatch):
    """LLM literal none resolves to None."""
    plan = tmp_path / "stage2_topk_spec.md"
    plan.write_text("# Stage 2", encoding="utf-8")
    monkeypatch.setattr(audit, "call_gemini_audit_resolve", lambda prompt: "none")

    assert audit._resolve_plan_via_llm("diff", [plan]) is None


def test_resolve_llm_returns_unknown_name(tmp_path, monkeypatch):
    """Unknown LLM filename resolves to None instead of crashing."""
    plan = tmp_path / "stage2_topk_spec.md"
    plan.write_text("# Stage 2", encoding="utf-8")
    monkeypatch.setattr(audit, "call_gemini_audit_resolve", lambda prompt: "missing.md")

    assert audit._resolve_plan_via_llm("diff", [plan]) is None


def test_audit_e2e_none_exits_with_message(tmp_path, capsys, monkeypatch):
    """Multi-candidate + LLM none prints explicit error and exits 1."""
    cwd = tmp_path / "shadow scribe"
    cwd.mkdir()
    (cwd / ".git").mkdir()
    plan_a = tmp_path / "stage2_topk_spec.md"
    plan_b = tmp_path / "ki005_audit_resolve_plan_spec.md"
    plan_a.write_text("# Stage 2", encoding="utf-8")
    plan_b.write_text("# KI-005", encoding="utf-8")

    class Result:
        returncode = 0
        stdout = "diff --git a/file b/file\n+change"
        stderr = ""

    monkeypatch.chdir(cwd)
    monkeypatch.setattr(audit.subprocess, "run", lambda *args, **kwargs: Result())
    monkeypatch.setattr(audit, "_gather_plan_candidates", lambda cwd, project: [plan_a, plan_b])
    monkeypatch.setattr(audit, "call_gemini_audit_resolve", lambda prompt: "none")

    with pytest.raises(SystemExit) as exc:
        audit.cmd_audit()

    out = capsys.readouterr().out
    assert exc.value.code == 1
    assert "Stage 0: LLM could not match diff to any plan" in out
    assert "Pass --plan <path> explicitly" in out
