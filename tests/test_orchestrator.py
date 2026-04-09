from unittest.mock import MagicMock

from autodev_cli.developer_orchestrator import AutoDevOrchestrator


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
    orchestrator.ai.run_prompt = MagicMock(
        side_effect=[
            "plan",
            "develop",
            "test",
            "# Validation report\nDone",
        ]
    )

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
        assert "Validation report" in handle.read()

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
