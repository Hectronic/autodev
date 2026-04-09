import pytest
import os
from unittest.mock import patch, MagicMock
from autodev_cli.project_detector import ProjectDetector

@pytest.fixture
def detector(tmp_path):
    return ProjectDetector(str(tmp_path))

def test_detect_python_project(tmp_path):
    (tmp_path / "requirements.txt").write_text("pytest")
    (tmp_path / "pytest.ini").write_text("[pytest]")
    
    detector = ProjectDetector(str(tmp_path))
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        info = detector.detect()
        
        assert info["project_type"] == "python"
        assert info["test_runner"] == "pytest"
        assert info["is_git"] is True

def test_detect_nodejs_project(tmp_path):
    (tmp_path / "package.json").write_text('{"scripts": {"test": "jest"}}')
    (tmp_path / "jest.config.js").write_text("module.exports = {};")
    
    detector = ProjectDetector(str(tmp_path))
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1) # Not git
        info = detector.detect()
        
        assert info["project_type"] == "nodejs"
        assert info["test_runner"] == "jest"
        assert info["is_git"] is False

def test_detect_go_project(tmp_path):
    (tmp_path / "go.mod").write_text("module test")
    
    detector = ProjectDetector(str(tmp_path))
    info = detector.detect()
    assert info["project_type"] == "go"
    assert info["test_runner"] == "go test"

def test_detect_rust_project(tmp_path):
    (tmp_path / "Cargo.toml").write_text("[package]")
    
    detector = ProjectDetector(str(tmp_path))
    info = detector.detect()
    assert info["project_type"] == "rust"
    assert info["test_runner"] == "cargo test"

def test_detect_unknown_project(tmp_path):
    detector = ProjectDetector(str(tmp_path))
    info = detector.detect()
    assert info["project_type"] == "generic"
    assert info["test_runner"] == "echo 'No test runner detected'"
