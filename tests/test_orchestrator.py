from unittest.mock import MagicMock, patch

import pytest

from autodev_cli.developer_orchestrator import AutoDevOrchestrator


@pytest.fixture(autouse=True)
def isolate_data_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))


def test_orchestrator_runs_plan_develop_test_validate(tmp_path):
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
    orchestrator.git.get_current_branch = MagicMock(return_value=None)
    orchestrator.ai.run_prompt = MagicMock(
        side_effect=[
            "plan",
            "develop",
            "test",
            "# Validation report\nDone",
        ]
    )

    with patch("autodev_cli.developer_orchestrator.open_html_report", return_value=True):
        orchestrator.run("Añade un endpoint para exportar reportes")

    assert orchestrator.ai.run_prompt.call_count == 4
    call_kwargs = [call.kwargs for call in orchestrator.ai.run_prompt.call_args_list]
    assert call_kwargs[0]["resume"] is False
    assert call_kwargs[1]["resume"] is True
    assert call_kwargs[2]["resume"] is True
    assert call_kwargs[3]["resume"] is True

    orchestrator.git.create_branch.assert_called_once()
    branch_name = orchestrator.git.create_branch.call_args.args[0]
    assert branch_name.startswith("autodev/")

    orchestrator.git.commit_changes.assert_called_once()
    assert orchestrator.git.commit_changes.call_args.args[0].startswith("autodev:")

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

    orchestrator.ai.run_prompt = MagicMock(
        side_effect=[
            "develop",
            "test",
            "# Validation report\nDone",
        ]
    )

    with patch("autodev_cli.developer_orchestrator.open_html_report", return_value=True):
        orchestrator.run("Añade un endpoint para exportar reportes")

    orchestrator.git.create_branch.assert_not_called()
    assert orchestrator.ai.run_prompt.call_count == 3
    assert orchestrator.ai.session_id == "gemini-session-123"
    assert orchestrator.history.get_session_steps(session_id)[0]["step_label"] == "Planning phase"
    assert orchestrator.history.get_session(session_id)["status"] == "completed"


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
    orchestrator.git.commit_changes.assert_called_once()
    assert orchestrator.history.get_session(orchestrator.session_id)["workflow"] == "unit-test"
    assert orchestrator.history.get_session(orchestrator.session_id)["base_branch"] == "origin/main"
    assert orchestrator.history.get_session(orchestrator.session_id)["merge_base_sha"] == "merge-base-sha"


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
    orchestrator.git.get_current_branch = MagicMock(return_value=None)
    orchestrator.ai.run_prompt = MagicMock(side_effect=["plan", RuntimeError("boom")])

    with patch("autodev_cli.developer_orchestrator.open_html_report", return_value=True), \
        pytest.raises(RuntimeError):
        orchestrator.run("Añade un endpoint para exportar reportes")

    session = orchestrator.history.get_session(orchestrator.session_id)
    assert session["status"] == "failed"
    orchestrator.git.commit_changes.assert_not_called()


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
    orchestrator.ai.run_prompt = MagicMock(side_effect=["diff analysis", RuntimeError("boom")])

    with patch("autodev_cli.developer_orchestrator.open_html_report", return_value=True), \
        pytest.raises(RuntimeError):
        orchestrator.run_unit_test(instructions="revisar auth")

    session = orchestrator.history.get_session(orchestrator.session_id)
    assert session["status"] == "failed"
    orchestrator.git.commit_changes.assert_not_called()

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
