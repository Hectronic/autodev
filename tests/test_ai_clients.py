import pytest
from unittest.mock import patch, MagicMock
from autodev_cli.gemini_client import GeminiClient
from autodev_cli.codex_client import CodexClient

@pytest.fixture
def gemini_client(tmp_path):
    log_file = tmp_path / "test.log"
    return GeminiClient(str(tmp_path), str(log_file))

@pytest.fixture
def codex_client(tmp_path):
    log_file = tmp_path / "test.log"
    return CodexClient(str(tmp_path), str(log_file))

def test_gemini_command_generation(gemini_client):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="[abc-123]", stderr="")
        
        # Iteration 1
        gemini_client.run_prompt("test prompt")
        args, kwargs = mock_run.call_args_list[0]
        assert "gemini" in args[0]
        assert "-p" in args[0]
        assert "test prompt" in args[0]
        assert "-r" not in args[0] # Not in first call if session_id is None

def test_gemini_resume_session(gemini_client):
    gemini_client.session_id = "session-123"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        gemini_client.run_prompt("test prompt", resume=True)
        args, _ = mock_run.call_args
        assert "-r" in args[0]
        assert "session-123" in args[0]

def test_codex_command_generation(codex_client):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        
        # Iteration 1
        codex_client.run_prompt("prompt 1")
        args, _ = mock_run.call_args
        assert "codex" in args[0]
        assert "exec" in args[0]
        assert "resume" not in args[0]
        
        # Iteration 2 (resume)
        codex_client.run_prompt("prompt 2", resume=True)
        args, _ = mock_run.call_args
        assert "resume" in args[0]
        assert "--last" in args[0]
        assert "prompt 2" in args[0]

def test_gemini_session_id_extraction(gemini_client):
    with patch("subprocess.run") as mock_run:
        # Simulate gemini --list-sessions output
        mock_run.return_value = MagicMock(
            returncode=0, 
            stdout="Sessions found:\n- [session-abc-123] (2 minutes ago)\n- [old-session-456] (1 hour ago)", 
            stderr=""
        )
        
        session_id = gemini_client._get_latest_session_id()
        assert session_id == "session-abc-123"

def test_gemini_session_id_extraction_empty(gemini_client):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="No sessions found.", stderr="")
        session_id = gemini_client._get_latest_session_id()
        assert session_id == "latest"

def test_gemini_initial_state(gemini_client):
    assert gemini_client.session_id is None

def test_gemini_log_creation(gemini_client, tmp_path):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        gemini_client.run_prompt("test prompt")
        
        log_file = tmp_path / "test.log"
        assert log_file.exists()
        content = log_file.read_text()
        assert "Input Prompt: test prompt" in content
        assert "Output Response:\nok" in content

def test_codex_log_creation(codex_client, tmp_path):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        codex_client.run_prompt("test prompt")
        
        log_file = tmp_path / "test.log"
        assert log_file.exists()
        content = log_file.read_text()
        assert "Input Prompt: test prompt" in content
        assert "--- NEW PROMPT (Codex) ---" in content
