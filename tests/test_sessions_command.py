import unittest
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from autodev_cli.cli import cli


def _session(session_id, timestamp):
    return {
        "id": session_id,
        "timestamp": timestamp,
        "status": "completed",
        "agent": "codex",
        "branch_name": f"autodev/{session_id[-3:]}",
        "project_path": "/tmp/project",
        "instructions": f"Instrucciones para {session_id}",
    }


class SessionsCommandTestCase(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_history_command_lists_last_10_sessions_by_default(self):
        fake_sessions = [
            _session(f"session-{index:02d}", f"2026-04-09T12:{index:02d}:00")
            for index in range(11, 0, -1)
        ]

        with patch("autodev_cli.cli.HistoryManager") as mock_manager:
            mock_instance = mock_manager.return_value
            mock_instance.get_sessions.return_value = fake_sessions[:10]

            result = self.runner.invoke(cli, ["history"])

        self.assertEqual(result.exit_code, 0)
        mock_instance.get_sessions.assert_called_once_with(limit=10)
        self.assertIn("Historial de Ejecuciones (últimas 10)", result.output)
        self.assertIn("session-11", result.output)
        self.assertIn("session-02", result.output)
        self.assertNotIn("session-01", result.output)

    def test_history_command_accepts_custom_limit(self):
        fake_sessions = [
            _session(f"session-{index:02d}", f"2026-04-09T12:{index:02d}:00")
            for index in range(3, 0, -1)
        ]

        with patch("autodev_cli.cli.HistoryManager") as mock_manager:
            mock_instance = mock_manager.return_value
            mock_instance.get_sessions.return_value = fake_sessions

            result = self.runner.invoke(cli, ["history", "--limit", "3"])

        self.assertEqual(result.exit_code, 0)
        mock_instance.get_sessions.assert_called_once_with(limit=3)
        self.assertIn("Historial de Ejecuciones (últimas 3)", result.output)

    def test_history_command_shows_session_detail(self):
        with patch("autodev_cli.cli.HistoryManager") as mock_manager:
            mock_instance = mock_manager.return_value
            mock_instance.get_session.return_value = {
                "branch_name": "autodev/123",
                "status": "completed",
                "results_dir": "/tmp/results",
                "summary_md_path": "/tmp/results/summary.md",
                "summary_html_path": "/tmp/results/summary.html",
            }
            mock_instance.get_session_steps.return_value = [
                {
                    "step_label": "Planning phase",
                    "timestamp": "2026-04-09T12:01:00",
                    "prompt": "prompt",
                    "response": "response",
                }
            ]

            result = self.runner.invoke(cli, ["history", "--session-id", "session-123"])

        self.assertEqual(result.exit_code, 0)
        mock_instance.get_session.assert_called_once_with("session-123")
        mock_instance.get_session_steps.assert_called_once_with("session-123")
        self.assertIn("Detalle de Sesión: session-123", result.output)
        self.assertIn("Planning phase", result.output)


if __name__ == "__main__":
    unittest.main()
