import pytest
from unittest.mock import patch, MagicMock
from autodev_cli.git_manager import GitManager

@pytest.fixture
def git_manager(tmp_path):
    return GitManager(str(tmp_path))

def test_git_is_repo_validation(git_manager):
    with patch("subprocess.run") as mock_run:
        # Success case
        mock_run.return_value = MagicMock(returncode=0)
        assert git_manager.is_git_repo() is True
        
        # Failure case
        mock_run.return_value = MagicMock(returncode=128) # Typical git error code for non-repos
        assert git_manager.is_git_repo() is False

def test_git_commit_changes(git_manager):
    with patch("subprocess.run") as mock_run:
        git_manager.commit_changes("test message")
        # Check if add and commit were called
        assert mock_run.call_count == 2
        
        # Check add call
        args1, _ = mock_run.call_args_list[0]
        assert "add" in args1[0]
        
        # Check commit call
        args2, _ = mock_run.call_args_list[1]
        assert "commit" in args2[0]
        assert "test message" in args2[0]
