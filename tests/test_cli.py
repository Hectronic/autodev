import pytest
from click.testing import CliRunner
from autodev_cli.cli import cli
from unittest.mock import MagicMock, patch

@pytest.fixture
def runner():
    return CliRunner()

def test_cli_help(runner):
    result = runner.invoke(cli, ["-h"])
    assert result.exit_code == 0
    assert "autodev" in result.output
    assert "-dev" in result.output
    assert "-ut" in result.output
    assert "-e" in result.output
    assert "--explain" in result.output
    assert "push" in result.output
    assert "history" in result.output

def test_cli_dev_command(runner):
    with patch("autodev_cli.cli.AutoDevOrchestrator") as mock_orchestrator:
        mock_instance = mock_orchestrator.return_value
        mock_instance.run = MagicMock()

        result = runner.invoke(
            cli,
            ["-dev", "Crear un endpoint para exportar reportes", "--agent", "codex"],
        )

        assert result.exit_code == 0
        mock_orchestrator.assert_called_once()
        args, kwargs = mock_orchestrator.call_args
        assert kwargs["agent"] == "codex"
        mock_instance.run.assert_called_once_with(
            instructions="Crear un endpoint para exportar reportes",
            push=False,
        )


def test_cli_dev_command_with_push(runner):
    with patch("autodev_cli.cli.AutoDevOrchestrator") as mock_orchestrator:
        mock_instance = mock_orchestrator.return_value
        mock_instance.run = MagicMock()

        result = runner.invoke(
            cli,
            ["-dev", "Crear un endpoint para exportar reportes", "--agent", "codex", "--push"],
        )

        assert result.exit_code == 0
        mock_instance.run.assert_called_once_with(
            instructions="Crear un endpoint para exportar reportes",
            push=True,
        )


def test_cli_unit_test_command(runner):
    with patch("autodev_cli.cli.AutoDevOrchestrator") as mock_orchestrator:
        mock_instance = mock_orchestrator.return_value
        mock_instance.run_unit_test = MagicMock()

        result = runner.invoke(
            cli,
            ["-ut", "--base-branch", "origin/main", "--agent", "codex"],
        )

        assert result.exit_code == 0
        mock_orchestrator.assert_called_once()
        args, kwargs = mock_orchestrator.call_args
        assert kwargs["agent"] == "codex"
        mock_instance.run_unit_test.assert_called_once_with(
            base_branch="origin/main",
            push=False,
        )


def test_cli_unit_test_command_with_push(runner):
    with patch("autodev_cli.cli.AutoDevOrchestrator") as mock_orchestrator:
        mock_instance = mock_orchestrator.return_value
        mock_instance.run_unit_test = MagicMock()

        result = runner.invoke(
            cli,
            ["-ut", "--base-branch", "origin/main", "--agent", "codex", "--push"],
        )

        assert result.exit_code == 0
        mock_instance.run_unit_test.assert_called_once_with(
            base_branch="origin/main",
            push=True,
        )


def test_cli_explain_command(runner):
    with patch("autodev_cli.cli.AutoDevOrchestrator") as mock_orchestrator:
        mock_instance = mock_orchestrator.return_value
        mock_instance.run_explain = MagicMock()

        result = runner.invoke(
            cli,
            ["-e", "--agent", "codex"],
        )

        assert result.exit_code == 0
        mock_orchestrator.assert_called_once()
        args, kwargs = mock_orchestrator.call_args
        assert kwargs["agent"] == "codex"
        mock_instance.run_explain.assert_called_once_with()

def test_cli_invalid_agent(runner):
    result = runner.invoke(cli, ["-dev", "probar", "-a", "invalid"])
    assert result.exit_code != 0
    assert "is not one of 'gemini', 'codex'" in result.output


def test_cli_push_command(runner):
    with patch("autodev_cli.cli.GitManager") as mock_git_manager:
        mock_instance = mock_git_manager.return_value
        mock_instance.is_git_repo.return_value = True
        mock_instance.get_current_branch.return_value = "feature/topic"
        mock_instance.commit_and_push_generated_changes.return_value = "feat: update cli"

        result = runner.invoke(cli, ["push"])

        assert result.exit_code == 0
        mock_git_manager.assert_called_once()
        mock_instance.commit_and_push_generated_changes.assert_called_once_with()
        assert "feat: update cli" in result.output


def test_cli_push_command_invalid_repo(runner):
    with patch("autodev_cli.cli.GitManager") as mock_git_manager:
        mock_instance = mock_git_manager.return_value
        mock_instance.is_git_repo.return_value = False

        result = runner.invoke(cli, ["push"])

        assert result.exit_code == 0
        assert "no es un repositorio Git válido" in result.output
        mock_instance.get_current_branch.assert_not_called()
        mock_instance.commit_and_push_generated_changes.assert_not_called()


def test_cli_push_command_without_branch(runner):
    with patch("autodev_cli.cli.GitManager") as mock_git_manager:
        mock_instance = mock_git_manager.return_value
        mock_instance.is_git_repo.return_value = True
        mock_instance.get_current_branch.return_value = None

        result = runner.invoke(cli, ["push"])

        assert result.exit_code == 0
        assert "No se pudo determinar la rama actual" in result.output
        mock_instance.commit_and_push_generated_changes.assert_not_called()
