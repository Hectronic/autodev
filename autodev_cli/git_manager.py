import subprocess

class GitManager:
    def __init__(self, project_path):
        self.project_path = project_path

    def is_git_repo(self):
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=self.project_path,
            capture_output=True,
            text=True
        )
        return result.returncode == 0

    def create_branch(self, branch_name):
        print(f"Creating branch: {branch_name}")
        subprocess.run(["git", "checkout", "-b", branch_name], cwd=self.project_path)

    def commit_changes(self, message):
        print(f"Committing changes: {message}")
        subprocess.run(["git", "add", "."], cwd=self.project_path)
        subprocess.run(["git", "commit", "-m", message], cwd=self.project_path)
