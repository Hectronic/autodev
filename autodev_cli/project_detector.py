import os
import subprocess

class ProjectDetector:
    def __init__(self, project_path):
        self.project_path = os.path.abspath(project_path)
        self.project_info = {
            "is_git": False,
            "project_type": "unknown",
            "test_runner": "unknown",
            "detected_files": []
        }

    def detect(self):
        self.project_info["is_git"] = self._check_git()
        self.project_info["project_type"] = self._detect_project_type()
        self.project_info["test_runner"] = self._detect_test_runner()
        
        # Defaults if not found
        if self.project_info["project_type"] == "unknown":
            self.project_info["project_type"] = "generic"
        if self.project_info["test_runner"] == "unknown":
            self.project_info["test_runner"] = self._get_default_test_runner(self.project_info["project_type"])
            
        return self.project_info

    def _check_git(self):
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=self.project_path,
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def _detect_project_type(self):
        files = os.listdir(self.project_path)
        self.project_info["detected_files"] = files
        
        if "package.json" in files:
            return "nodejs"
        if "requirements.txt" in files or "setup.py" in files or "pyproject.toml" in files:
            return "python"
        if "go.mod" in files:
            return "go"
        if "Cargo.toml" in files:
            return "rust"
        if "pom.xml" in files or "build.gradle" in files:
            return "java"
        if "composer.json" in files:
            return "php"
        
        return "unknown"

    def _detect_test_runner(self):
        ptype = self.project_info["project_type"]
        files = self.project_info["detected_files"]
        
        if ptype == "python":
            # Check for pytest markers
            if any(f in files for f in ["pytest.ini", "tox.ini", "conftest.py"]):
                return "pytest"
            
            # Check subdirectories for conftest.py
            for root, dirs, filenames in os.walk(self.project_path):
                if "conftest.py" in filenames:
                    return "pytest"
                if root != self.project_path: # only go one level deep for speed
                    break
            
            # Check pyproject.toml for pytest config
            if "pyproject.toml" in files:
                try:
                    with open(os.path.join(self.project_path, "pyproject.toml"), "r") as f:
                        if "[tool.pytest.ini_options]" in f.read():
                            return "pytest"
                except:
                    pass
                    
            return "unittest"
        
        if ptype == "nodejs":
            if "jest.config.js" in files or "jest.config.ts" in files:
                return "jest"
            if "vitest.config.ts" in files or "vitest.config.js" in files:
                return "vitest"
            
            # Check package.json
            if "package.json" in files:
                try:
                    with open(os.path.join(self.project_path, "package.json"), "r") as f:
                        content = f.read()
                        if '"jest"' in content: return "jest"
                        if '"mocha"' in content: return "mocha"
                        if '"vitest"' in content: return "vitest"
                        if '"cypress"' in content: return "cypress"
                except:
                    pass
            return "npm test"
            
        if ptype == "go":
            return "go test"
            
        if ptype == "rust":
            return "cargo test"
            
        if ptype == "java":
            if "pom.xml" in files:
                return "mvn test"
            return "gradle test"
            
        return "unknown"

    def _get_default_test_runner(self, project_type):
        defaults = {
            "python": "pytest",
            "nodejs": "jest",
            "go": "go test",
            "rust": "cargo test",
            "java": "mvn test",
            "php": "phpunit",
            "generic": "echo 'No test runner detected'"
        }
        return defaults.get(project_type, "echo 'No test runner detected'")
