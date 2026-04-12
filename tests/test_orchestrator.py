from unittest.mock import MagicMock, patch
import subprocess

import pytest

from autodev_cli.developer_orchestrator import AutoDevOrchestrator


@pytest.fixture(autouse=True)
def isolate_data_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))


def _run_git(repo_path, *args):
    return subprocess.run(
        ["git", *args],
        cwd=repo_path,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_git_repo(repo_path):
    _run_git(repo_path, "init")
    _run_git(repo_path, "config", "user.email", "autodev@example.com")
    _run_git(repo_path, "config", "user.name", "Autodev")
    _run_git(repo_path, "branch", "-M", "main")


def _write_file(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_orchestrator_runs_plan_develop_test_validate(tmp_path):
    (tmp_path / "README.md").write_text("# Project README\n", encoding="utf-8")
    (tmp_path / "GEMINI.md").write_text("# Gemini guide\n", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("# Agents guide\n", encoding="utf-8")

    orchestrator = AutoDevOrchestrator(str(tmp_path))
    orchestrator.detector.detect = MagicMock(
        return_value={
            "is_git": True,
            "project_type": "python",
            "test_runner": "pytest",
            "detected_files": [],
        }
    )
    orchestrator.git.create_branch = MagicMock()
    orchestrator.git.commit_changes = MagicMock()
    orchestrator.git.push_branch = MagicMock()
    orchestrator.git.get_current_branch = MagicMock(return_value=None)
    orchestrator.ai.run_prompt = MagicMock(
        side_effect=[
            "plan",
            "develop",
            "docs",
            "test",
            "# Validation report\nDone",
        ]
    )

    with patch("autodev_cli.developer_orchestrator.open_html_report", return_value=True):
        orchestrator.run("Añade un endpoint para exportar reportes")

    assert orchestrator.ai.run_prompt.call_count == 5
    call_kwargs = [call.kwargs for call in orchestrator.ai.run_prompt.call_args_list]
    assert call_kwargs[0]["resume"] is False
    assert call_kwargs[1]["resume"] is True
    assert call_kwargs[2]["resume"] is True
    assert call_kwargs[3]["resume"] is True
    assert call_kwargs[4]["resume"] is True

    orchestrator.git.create_branch.assert_called_once()
    branch_name = orchestrator.git.create_branch.call_args.args[0]
    assert branch_name.startswith("autodev/")

    orchestrator.git.commit_changes.assert_not_called()
    orchestrator.git.push_branch.assert_not_called()
    assert [doc["name"] for doc in orchestrator.reference_docs] == [
        "README.md",
        "GEMINI.md",
        "AGENTS.md",
    ]
    assert (orchestrator.storage.session_dir(orchestrator.session_id) / "reference_docs/README.md").exists()

    report_path = orchestrator.results_dir + "/final_report.md"
    with open(report_path, "r", encoding="utf-8") as handle:
        report = handle.read()
        assert "Validation report" in report
        assert "Session ID:" in report
        assert "Branch:" in report

    session_root = orchestrator.storage.base_dir / "sessions" / orchestrator.session_id
    assert (session_root / "summary.md").exists()
    assert (session_root / "summary.html").exists()


def test_orchestrator_recovers_running_session_on_branch(tmp_path):
    (tmp_path / "README.md").write_text("# Project README\n", encoding="utf-8")
    (tmp_path / "GEMINI.md").write_text("# Gemini guide\n", encoding="utf-8")

    orchestrator = AutoDevOrchestrator(str(tmp_path), agent="gemini")
    orchestrator.detector.detect = MagicMock(
        return_value={
            "is_git": True,
            "project_type": "python",
            "test_runner": "pytest",
            "detected_files": [],
        }
    )
    orchestrator.git.get_current_branch = MagicMock(return_value="autodev/existing")
    orchestrator.git.create_branch = MagicMock()
    orchestrator.git.commit_changes = MagicMock()
    orchestrator.git.push_branch = MagicMock()
    orchestrator.git.get_head_sha = MagicMock(return_value="head-sha")

    session_id = "session-existing"
    session_dir = orchestrator.storage.session_dir(session_id)
    orchestrator.history.create_session(
        session_id,
        str(tmp_path),
        "gemini",
        "Añade un endpoint para exportar reportes",
        str(session_dir),
        branch_name="autodev/existing",
        status="running",
        log_path=str(session_dir / "execution.log"),
        summary_md_path=str(session_dir / "summary.md"),
        summary_html_path=str(session_dir / "summary.html"),
        agent_session_id="gemini-session-123",
        head_sha="head-sha",
    )
    orchestrator.history.save_step(
        session_id,
        "Planning phase",
        "plan prompt",
        "plan response",
        step_order=1,
        input_path=str(session_dir / "inputs/01_planning_phase.md"),
        output_path=str(session_dir / "outputs/01_planning_phase.md"),
    )
    reference_docs_dir = session_dir / "reference_docs"
    reference_docs_dir.mkdir(parents=True, exist_ok=True)
    (reference_docs_dir / "README.md").write_text("# Project README\n", encoding="utf-8")
    (reference_docs_dir / "GEMINI.md").write_text("# Gemini guide\n", encoding="utf-8")

    orchestrator.ai.run_prompt = MagicMock(
        side_effect=[
            "docs",
            "develop",
            "test",
            "# Validation report\nDone",
        ]
    )

    with patch("autodev_cli.developer_orchestrator.open_html_report", return_value=True):
        orchestrator.run("Añade un endpoint para exportar reportes")

    orchestrator.git.create_branch.assert_not_called()
    assert orchestrator.ai.run_prompt.call_count == 4
    assert orchestrator.ai.session_id == "gemini-session-123"
    assert orchestrator.history.get_session_steps(session_id)[0]["step_label"] == "Planning phase"
    assert orchestrator.history.get_session(session_id)["status"] == "completed"
    orchestrator.git.commit_changes.assert_not_called()
    orchestrator.git.push_branch.assert_not_called()
    assert [doc["name"] for doc in orchestrator.reference_docs] == ["README.md", "GEMINI.md"]
    assert "Project README" in orchestrator.reference_docs_context


def test_orchestrator_new_session_without_reference_docs_uses_fallback_context(tmp_path):
    orchestrator = AutoDevOrchestrator(str(tmp_path))
    orchestrator.detector.detect = MagicMock(
        return_value={
            "is_git": True,
            "project_type": "python",
            "test_runner": "pytest",
            "detected_files": [],
        }
    )
    orchestrator.git.create_branch = MagicMock()
    orchestrator.git.commit_changes = MagicMock()
    orchestrator.git.push_branch = MagicMock()
    orchestrator.git.get_current_branch = MagicMock(return_value=None)
    orchestrator.ai.run_prompt = MagicMock(
        side_effect=[
            "plan",
            "develop",
            "docs",
            "test",
            "# Validation report\nDone",
        ]
    )

    with patch("autodev_cli.developer_orchestrator.open_html_report", return_value=True):
        orchestrator.run("Añade un endpoint para exportar reportes")

    first_prompt = orchestrator.ai.run_prompt.call_args_list[0].args[0]
    assert "Documentacion de referencia cargada: ninguna." in first_prompt


def test_orchestrator_runs_unit_test_flow(tmp_path):
    orchestrator = AutoDevOrchestrator(str(tmp_path))
    orchestrator.detector.detect = MagicMock(
        return_value={
            "is_git": True,
            "project_type": "python",
            "test_runner": "pytest",
            "detected_files": [],
        }
    )
    orchestrator.git.get_current_branch = MagicMock(return_value="feature/cov-review")
    orchestrator.git.get_branch_origin = MagicMock(return_value="origin/main")
    orchestrator.git.get_merge_base = MagicMock(return_value="merge-base-sha")
    orchestrator.git.get_diff_stat = MagicMock(return_value=" file.py | 12 +++++++-----")
    orchestrator.git.get_diff_name_status = MagicMock(return_value="M\tfile.py")
    orchestrator.git.get_changed_files = MagicMock(return_value=["file.py"])
    orchestrator.git.get_commit_summary = MagicMock(return_value="abc123 Add branch change")
    orchestrator.git.get_diff_patch = MagicMock(return_value="diff --git a/file.py b/file.py")
    orchestrator.git.create_branch = MagicMock()
    orchestrator.git.commit_changes = MagicMock()
    orchestrator.git.push_branch = MagicMock()
    orchestrator.ai.run_prompt = MagicMock(
        side_effect=[
            "diff analysis",
            "coverage gaps",
            "gap remediation",
            "# Validation report\nClosed",
        ]
    )

    with patch("autodev_cli.developer_orchestrator.open_html_report", return_value=True):
        orchestrator.run_unit_test(instructions="revisar auth")

    assert orchestrator.ai.run_prompt.call_count == 4
    call_kwargs = [call.kwargs for call in orchestrator.ai.run_prompt.call_args_list]
    assert call_kwargs[0]["resume"] is False
    assert call_kwargs[1]["resume"] is True
    assert call_kwargs[2]["resume"] is True
    assert call_kwargs[3]["resume"] is True

    orchestrator.git.create_branch.assert_not_called()
    orchestrator.git.get_branch_origin.assert_called_once_with("feature/cov-review")
    orchestrator.git.commit_changes.assert_not_called()
    orchestrator.git.push_branch.assert_not_called()
    assert orchestrator.history.get_session(orchestrator.session_id)["workflow"] == "unit-test"
    assert orchestrator.history.get_session(orchestrator.session_id)["base_branch"] == "origin/main"
    assert orchestrator.history.get_session(orchestrator.session_id)["merge_base_sha"] == "merge-base-sha"


def test_orchestrator_runs_explain_flow(tmp_path):
    (tmp_path / "README.md").write_text("# Project README\n", encoding="utf-8")
    (tmp_path / "ARCHITECTURE.md").write_text("# Architecture\n", encoding="utf-8")
    (tmp_path / "tests").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tests" / "test_cli.py").write_text("import unittest\n", encoding="utf-8")

    orchestrator = AutoDevOrchestrator(str(tmp_path))
    orchestrator.detector.detect = MagicMock(
        return_value={
            "is_git": True,
            "project_type": "python",
            "test_runner": "unittest",
            "detected_files": [],
        }
    )
    orchestrator.git.get_current_branch = MagicMock(return_value="main")
    orchestrator.git.get_head_sha = MagicMock(return_value="head-sha")
    orchestrator.git.create_branch = MagicMock()
    orchestrator.git.commit_changes = MagicMock()
    orchestrator.git.push_branch = MagicMock()
    orchestrator.ai.run_prompt = MagicMock(
        side_effect=[
            "Resumen generado por IA",
            "Stack generado por IA",
            "Arquitectura generada por IA",
            "Diseno generado por IA",
            "Funcionalidad generada por IA",
            "Tests generados por IA",
            "Riesgos y conclusiones generados por IA",
        ]
    )

    with patch("autodev_cli.developer_orchestrator.open_html_report", return_value=True):
        orchestrator.run_explain()

    assert orchestrator.ai.run_prompt.call_count == 7
    call_kwargs = [call.kwargs for call in orchestrator.ai.run_prompt.call_args_list]
    assert call_kwargs[0]["resume"] is False
    assert all(call["resume"] is True for call in call_kwargs[1:])

    orchestrator.git.create_branch.assert_not_called()
    orchestrator.git.commit_changes.assert_not_called()
    orchestrator.git.push_branch.assert_not_called()
    assert orchestrator.history.get_session(orchestrator.session_id)["workflow"] == "explain"
    assert orchestrator.history.get_session(orchestrator.session_id)["agent"] == "codex"

    session_root = orchestrator.storage.base_dir / "sessions" / orchestrator.session_id
    assert (session_root / "summary.md").exists()
    assert (session_root / "summary.html").exists()
    assert (session_root / "outputs" / "01_resumen_ejecutivo.md").exists()
    assert (session_root / "outputs" / "07_riesgos_y_conclusiones.md").exists()

    with open(orchestrator.results_dir + "/final_report.md", "r", encoding="utf-8") as handle:
        report = handle.read()
        assert "## Stack" in report
        assert "## Arquitectura" in report
        assert "## Tests" in report
        assert "Riesgos y conclusiones generados por IA" in report


def test_orchestrator_unit_test_includes_pending_changes(tmp_path):
    orchestrator = AutoDevOrchestrator(str(tmp_path))
    orchestrator.detector.detect = MagicMock(
        return_value={
            "is_git": True,
            "project_type": "python",
            "test_runner": "pytest",
            "detected_files": [],
        }
    )
    orchestrator.git.get_current_branch = MagicMock(return_value="feature/cov-review")
    orchestrator.git.get_branch_origin = MagicMock(return_value="origin/main")
    orchestrator.git.get_merge_base = MagicMock(return_value="merge-base-sha")
    orchestrator.git.get_diff_stat = MagicMock(return_value=" file.py | 12 +++++++-----")
    orchestrator.git.get_diff_name_status = MagicMock(return_value="M\tfile.py")
    orchestrator.git.get_changed_files = MagicMock(return_value=["file.py"])
    orchestrator.git.get_commit_summary = MagicMock(return_value="abc123 Add branch change")
    orchestrator.git.get_diff_patch = MagicMock(return_value="diff --git a/file.py b/file.py")
    orchestrator.git.get_status_porcelain = MagicMock(return_value=[" M file.py", "?? docs/new.md"])
    orchestrator.git.get_staged_changed_files = MagicMock(return_value=["file.py"])
    orchestrator.git.get_unstaged_changed_files = MagicMock(return_value=["file.py"])
    orchestrator.git.get_untracked_files = MagicMock(return_value=["docs/new.md"])
    orchestrator.git.get_staged_diff_stat = MagicMock(return_value=" file.py | 1 +")
    orchestrator.git.get_unstaged_diff_stat = MagicMock(return_value=" file.py | 2 ++")
    orchestrator.git.get_staged_diff_name_status = MagicMock(return_value="M\tfile.py")
    orchestrator.git.get_unstaged_diff_name_status = MagicMock(return_value="M\tfile.py")
    orchestrator.git.get_staged_diff_patch = MagicMock(return_value="diff --git a/file.py b/file.py")
    orchestrator.git.get_unstaged_diff_patch = MagicMock(return_value="diff --git a/file.py b/file.py")
    orchestrator.git.create_branch = MagicMock()
    orchestrator.git.commit_changes = MagicMock()
    orchestrator.git.push_branch = MagicMock()
    orchestrator.ai.run_prompt = MagicMock(
        side_effect=[
            "diff analysis",
            "coverage gaps",
            "gap remediation",
            "# Validation report\nClosed",
        ]
    )

    with patch("autodev_cli.developer_orchestrator.open_html_report", return_value=True):
        orchestrator.run_unit_test(instructions="revisar auth")

    first_prompt = orchestrator.ai.run_prompt.call_args_list[0].args[0]
    assert "Cambios pendientes en working tree" in first_prompt
    assert "?? docs/new.md" in first_prompt

    with open(orchestrator.results_dir + "/final_report.md", "r", encoding="utf-8") as handle:
        report = handle.read()
        assert "## Diff de la rama" in report
        assert "```diff" in report
        assert "## Cambios pendientes" in report
        assert "docs/new.md" in report


def test_orchestrator_unit_test_with_real_git_worktree_pending_changes(tmp_path):
    _init_git_repo(tmp_path)
    _write_file(tmp_path / "file.py", "print('base')\n")
    _run_git(tmp_path, "add", "file.py")
    _run_git(tmp_path, "commit", "-m", "feat: base file")
    _run_git(tmp_path, "checkout", "-b", "feature/cov-review")

    _write_file(tmp_path / "file.py", "print('staged')\n")
    _run_git(tmp_path, "add", "file.py")
    _write_file(tmp_path / "file.py", "print('unstaged')\n")
    _write_file(tmp_path / "docs/new.md", "# new docs\n")

    orchestrator = AutoDevOrchestrator(str(tmp_path))
    orchestrator.ai.run_prompt = MagicMock(
        side_effect=[
            "diff analysis",
            "coverage gaps",
            "gap remediation",
            "# Validation report\nClosed",
        ]
    )

    with patch("autodev_cli.developer_orchestrator.open_html_report", return_value=True):
        orchestrator.run_unit_test(base_branch="main")

    first_prompt = orchestrator.ai.run_prompt.call_args_list[0].args[0]
    assert "Cambios pendientes en working tree:" in first_prompt
    assert "Archivos staged:" in first_prompt
    assert "Archivos unstaged:" in first_prompt
    assert "Archivos no trackeados:" in first_prompt
    assert "docs/new.md" in first_prompt

    with open(orchestrator.results_dir + "/final_report.md", "r", encoding="utf-8") as handle:
        report = handle.read()
        assert "## Cambios pendientes" in report
        assert "Staged diff" in report
        assert "Unstaged diff" in report
        assert "Untracked" in report


def test_orchestrator_marks_failed_session_in_development_flow(tmp_path):
    orchestrator = AutoDevOrchestrator(str(tmp_path))
    orchestrator.detector.detect = MagicMock(
        return_value={
            "is_git": True,
            "project_type": "python",
            "test_runner": "pytest",
            "detected_files": [],
        }
    )
    orchestrator.git.create_branch = MagicMock()
    orchestrator.git.commit_changes = MagicMock()
    orchestrator.git.push_branch = MagicMock()
    orchestrator.git.get_current_branch = MagicMock(return_value=None)
    orchestrator.ai.run_prompt = MagicMock(side_effect=["plan", RuntimeError("boom")])

    with patch("autodev_cli.developer_orchestrator.open_html_report", return_value=True), \
        pytest.raises(RuntimeError):
        orchestrator.run("Añade un endpoint para exportar reportes")

    session = orchestrator.history.get_session(orchestrator.session_id)
    assert session["status"] == "failed"
    orchestrator.git.commit_changes.assert_not_called()
    orchestrator.git.push_branch.assert_not_called()


def test_orchestrator_marks_failed_session_in_unit_test_flow(tmp_path):
    orchestrator = AutoDevOrchestrator(str(tmp_path))
    orchestrator.detector.detect = MagicMock(
        return_value={
            "is_git": True,
            "project_type": "python",
            "test_runner": "pytest",
            "detected_files": [],
        }
    )
    orchestrator.git.get_current_branch = MagicMock(return_value="feature/cov-review")
    orchestrator.git.get_branch_origin = MagicMock(return_value="origin/main")
    orchestrator.git.get_merge_base = MagicMock(return_value="merge-base-sha")
    orchestrator.git.get_diff_stat = MagicMock(return_value=" file.py | 12 +++++++-----")
    orchestrator.git.get_diff_name_status = MagicMock(return_value="M\tfile.py")
    orchestrator.git.get_changed_files = MagicMock(return_value=["file.py"])
    orchestrator.git.get_commit_summary = MagicMock(return_value="abc123 Add branch change")
    orchestrator.git.get_diff_patch = MagicMock(return_value="diff --git a/file.py b/file.py")
    orchestrator.git.create_branch = MagicMock()
    orchestrator.git.commit_changes = MagicMock()
    orchestrator.git.push_branch = MagicMock()
    orchestrator.ai.run_prompt = MagicMock(side_effect=["diff analysis", RuntimeError("boom")])

    with patch("autodev_cli.developer_orchestrator.open_html_report", return_value=True), \
        pytest.raises(RuntimeError):
        orchestrator.run_unit_test(instructions="revisar auth")

    session = orchestrator.history.get_session(orchestrator.session_id)
    assert session["status"] == "failed"
    orchestrator.git.commit_changes.assert_not_called()
    orchestrator.git.push_branch.assert_not_called()


def test_orchestrator_pushes_when_requested(tmp_path):
    orchestrator = AutoDevOrchestrator(str(tmp_path))
    orchestrator.detector.detect = MagicMock(
        return_value={
            "is_git": True,
            "project_type": "python",
            "test_runner": "pytest",
            "detected_files": [],
        }
    )
    orchestrator.git.create_branch = MagicMock()
    orchestrator.git.commit_changes = MagicMock()
    orchestrator.git.push_branch = MagicMock()
    orchestrator.git.get_current_branch = MagicMock(return_value=None)
    orchestrator.ai.run_prompt = MagicMock(
        side_effect=[
            "plan",
            "develop",
            "docs",
            "test",
            "# Validation report\nDone",
        ]
    )

    with patch("autodev_cli.developer_orchestrator.open_html_report", return_value=True):
        orchestrator.run("Añade un endpoint para exportar reportes", push=True)

    orchestrator.git.commit_changes.assert_called_once()
    assert orchestrator.git.commit_changes.call_args.args[0].startswith("autodev:")
    orchestrator.git.push_branch.assert_called_once_with(orchestrator.branch_name)

def test_orchestrator_non_git_repo(tmp_path):
    orchestrator = AutoDevOrchestrator(str(tmp_path))
    orchestrator.detector.detect = MagicMock(
        return_value={
            "is_git": False,
            "project_type": "python",
            "test_runner": "pytest",
        }
    )
    orchestrator.ai.run_prompt = MagicMock()
    
    orchestrator.run("test")
    
    orchestrator.ai.run_prompt.assert_not_called()

def test_orchestrator_no_instructions(tmp_path):
    orchestrator = AutoDevOrchestrator(str(tmp_path))
    orchestrator.ai.run_prompt = MagicMock()
    
    orchestrator.run("")
    
    orchestrator.ai.run_prompt.assert_not_called()

def test_orchestrator_agent_selection_gemini(tmp_path):
    from autodev_cli.gemini_client import GeminiClient
    orchestrator = AutoDevOrchestrator(str(tmp_path), agent="gemini")
    assert isinstance(orchestrator.ai, GeminiClient)

def test_orchestrator_agent_selection_codex(tmp_path):
    from autodev_cli.codex_client import CodexClient
    orchestrator = AutoDevOrchestrator(str(tmp_path), agent="codex")
    assert isinstance(orchestrator.ai, CodexClient)
