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
    assert "history" in result.output

def test_cli_dev_command(runner):
    with patch("autodev_cli.cli.AutoDevOrchestrator") as mock_orchestrator:
        mock_instance = mock_orchestrator.return_value
        mock_instance.run = MagicMock()

        result = runner.invoke(
            cli,
            ["-dev", "--instructions", "Crear un endpoint para exportar reportes", "--agent", "codex"],
        )

        assert result.exit_code == 0
        mock_orchestrator.assert_called_once()
        args, kwargs = mock_orchestrator.call_args
        assert kwargs["agent"] == "codex"
        mock_instance.run.assert_called_once_with(
            instructions="Crear un endpoint para exportar reportes"
        )


def test_cli_unit_test_command(runner):
    with patch("autodev_cli.cli.AutoDevOrchestrator") as mock_orchestrator:
        mock_instance = mock_orchestrator.return_value
        mock_instance.run_unit_test = MagicMock()

        result = runner.invoke(
            cli,
            ["-ut", "--base-branch", "origin/main", "--instructions", "revisar auth", "--agent", "codex"],
        )

        assert result.exit_code == 0
        mock_orchestrator.assert_called_once()
        args, kwargs = mock_orchestrator.call_args
        assert kwargs["agent"] == "codex"
        mock_instance.run_unit_test.assert_called_once_with(
            base_branch="origin/main",
            instructions="revisar auth",
            no_commit=False,
        )

def test_cli_invalid_agent(runner):
    result = runner.invoke(cli, ["-dev", "--instructions", "probar", "-a", "invalid"])
    assert result.exit_code != 0
    assert "is not one of 'gemini', 'codex'" in result.output
