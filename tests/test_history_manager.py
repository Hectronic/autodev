import sqlite3
from pathlib import Path

import pytest

from autodev_cli.history_manager import HistoryManager


@pytest.fixture(autouse=True)
def isolate_data_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))


def test_history_manager_persists_sessions_and_branch_lookup(tmp_path):
    manager = HistoryManager()
    session_id = "session-001"
    results_dir = str(manager.storage.session_dir(session_id))

    manager.create_session(
        session_id,
        str(tmp_path),
        "codex",
        "Añade un endpoint para exportar reportes",
        results_dir,
        branch_name="autodev/001",
        workflow="development",
        base_branch="origin/main",
        merge_base_sha="abc999",
        status="running",
        log_path=f"{results_dir}/execution.log",
        summary_md_path=f"{results_dir}/summary.md",
        summary_html_path=f"{results_dir}/summary.html",
        agent_session_id="agent-session-abc",
        head_sha="abc123",
    )
    manager.save_step(
        session_id,
        "Planning phase",
        "prompt",
        "response",
        step_order=1,
        input_path=f"{results_dir}/inputs/01_planning_phase.md",
        output_path=f"{results_dir}/outputs/01_planning_phase.md",
    )

    session = manager.get_session(session_id)
    assert session["branch_name"] == "autodev/001"
    assert session["workflow"] == "development"
    assert session["base_branch"] == "origin/main"
    assert session["merge_base_sha"] == "abc999"
    assert session["status"] == "running"
    assert session["agent_session_id"] == "agent-session-abc"

    lookup = manager.get_running_session_for_branch(str(tmp_path), "autodev/001", "codex", "development")
    assert lookup["id"] == session_id

    steps = manager.get_session_steps(session_id)
    assert steps[0]["step_order"] == 1
    assert steps[0]["input_path"].endswith("planning_phase.md")

    manager.close_session(session_id)
    assert manager.get_running_session_for_branch(str(tmp_path), "autodev/001", "codex") is None


def test_history_manager_migrates_legacy_history_db(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    home_dir = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home_dir)

    legacy_db_path = home_dir / ".autodev" / "history.db"
    legacy_db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(legacy_db_path) as conn:
        conn.execute(
            """
            CREATE TABLE execution_sessions (
                id TEXT PRIMARY KEY,
                project_path TEXT,
                agent TEXT,
                instructions TEXT,
                timestamp DATETIME,
                results_dir TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO execution_sessions (id, project_path, agent, instructions, timestamp, results_dir) VALUES (?, ?, ?, ?, ?, ?)",
            (
                "legacy-001",
                str(tmp_path),
                "codex",
                "Legacy instructions",
                "2026-04-09T12:00:00",
                "/tmp/legacy-results",
            ),
        )
        conn.commit()

    manager = HistoryManager()

    session = manager.get_session("legacy-001")
    assert session is not None
    assert session["agent"] == "codex"
    assert session["instructions"] == "Legacy instructions"
    assert session["branch_name"] is None
    assert manager.db_path.exists()
    assert manager.db_path == tmp_path / "xdg" / "autodev" / "history.db"
