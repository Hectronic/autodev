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


def test_git_push_branch(git_manager):
    with patch("subprocess.run") as mock_run:
        git_manager.push_branch("autodev/123")

        mock_run.assert_called_once_with(
            ["git", "push", "-u", "origin", "autodev/123"],
            cwd=str(git_manager.project_path),
        )


def test_git_generate_commit_message_from_docs_changes(git_manager):
    with patch.object(git_manager, "get_status_porcelain", return_value=[
        " M README.md",
        " M ARCHITECTURE.md",
    ]):
        message = git_manager.generate_commit_message()

    assert message == "docs: update README"


def test_git_generate_commit_message_from_test_changes(git_manager):
    with patch.object(git_manager, "get_status_porcelain", return_value=[
        " M tests/test_cli.py",
        " M tests/test_git_manager.py",
    ]):
        message = git_manager.generate_commit_message()

    assert message == "test: update tests"


def test_git_generate_commit_message_from_config_changes(git_manager):
    with patch.object(git_manager, "get_status_porcelain", return_value=[
        " M pyproject.toml",
    ]):
        message = git_manager.generate_commit_message()

    assert message == "chore: update pyproject"


def test_git_generate_commit_message_from_deleted_files(git_manager):
    with patch.object(git_manager, "get_status_porcelain", return_value=[
        " D autodev_cli/legacy.py",
    ]):
        message = git_manager.generate_commit_message()

    assert message == "fix: update legacy"


def test_git_generate_commit_message_from_renamed_files(git_manager):
    with patch.object(git_manager, "get_status_porcelain", return_value=[
        " R  autodev_cli/old_cli.py -> autodev_cli/new_cli.py",
    ]):
        message = git_manager.generate_commit_message()

    assert message == "refactor: update new cli"


def test_git_generate_commit_message_from_code_changes_uses_single_file_scope(git_manager):
    with patch.object(git_manager, "get_status_porcelain", return_value=[
        " M autodev_cli/cli.py",
    ]):
        message = git_manager.generate_commit_message()

    assert message == "feat: update cli"


def test_git_commit_and_push_generated_changes(git_manager):
    with patch.object(git_manager, "has_changes", return_value=True), \
        patch.object(git_manager, "generate_commit_message", return_value="feat: update cli"), \
        patch.object(git_manager, "get_current_branch", return_value="feature/topic"), \
        patch.object(git_manager, "commit_changes") as mock_commit, \
        patch.object(git_manager, "push_branch") as mock_push:
        message = git_manager.commit_and_push_generated_changes()

    assert message == "feat: update cli"
    mock_commit.assert_called_once_with("feat: update cli")
    mock_push.assert_called_once_with("feature/topic", remote="origin")


def test_git_commit_and_push_generated_changes_without_changes(git_manager):
    with patch.object(git_manager, "has_changes", return_value=False), \
        patch.object(git_manager, "commit_changes") as mock_commit, \
        patch.object(git_manager, "push_branch") as mock_push:
        message = git_manager.commit_and_push_generated_changes()

    assert message is None
    mock_commit.assert_not_called()
    mock_push.assert_not_called()


def test_git_commit_and_push_generated_changes_without_current_branch(git_manager):
    with patch.object(git_manager, "has_changes", return_value=True), \
        patch.object(git_manager, "generate_commit_message", return_value="feat: update cli"), \
        patch.object(git_manager, "get_current_branch", return_value=None), \
        patch.object(git_manager, "commit_changes") as mock_commit, \
        patch.object(git_manager, "push_branch") as mock_push:
        message = git_manager.commit_and_push_generated_changes()

    assert message is None
    mock_commit.assert_not_called()
    mock_push.assert_not_called()


def test_git_get_commit_summary_uses_branch_only_range(git_manager):
    with patch.object(git_manager, "_run_git") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="abc123 Commit one\nxyz789 Commit two\n", stderr="")

        summary = git_manager.get_commit_summary("origin/main", "feature/topic")

    mock_run.assert_called_once_with([
        "log",
        "--oneline",
        "--decorate",
        "--no-merges",
        "origin/main..feature/topic",
    ])
    assert summary == "abc123 Commit one\nxyz789 Commit two"


def test_git_get_branch_origin_falls_back_to_default_remote_branch(git_manager):
    with patch.object(git_manager, "get_branch_upstream", return_value=None), \
        patch.object(git_manager, "get_default_remote_branch", return_value="origin/main"), \
        patch.object(git_manager, "_run_git") as mock_run:
        origin = git_manager.get_branch_origin("feature/topic")

    assert origin == "origin/main"
    mock_run.assert_not_called()


def test_git_get_branch_origin_falls_back_to_local_main(git_manager):
    with patch.object(git_manager, "get_branch_upstream", return_value=None), \
        patch.object(git_manager, "get_default_remote_branch", return_value=None), \
        patch.object(git_manager, "_run_git") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        origin = git_manager.get_branch_origin("feature/topic")

    assert origin == "main"
    mock_run.assert_called_once_with(["show-ref", "--verify", "--quiet", "refs/heads/main"])
