import subprocess

class GitManager:
    def __init__(self, project_path):
        self.project_path = project_path

    def _run_git(self, args):
        return subprocess.run(
            ["git", *args],
            cwd=self.project_path,
            capture_output=True,
            text=True,
        )

    def is_git_repo(self):
        result = self._run_git(["rev-parse", "--is-inside-work-tree"])
        return result.returncode == 0

    def create_branch(self, branch_name):
        print(f"Creating branch: {branch_name}")
        subprocess.run(["git", "checkout", "-b", branch_name], cwd=self.project_path)

    def commit_changes(self, message):
        print(f"Committing changes: {message}")
        subprocess.run(["git", "add", "."], cwd=self.project_path)
        subprocess.run(["git", "commit", "-m", message], cwd=self.project_path)

    def get_current_branch(self):
        result = self._run_git(["branch", "--show-current"])
        if result.returncode != 0:
            return None
        branch = result.stdout.strip()
        return branch or None

    def get_head_sha(self):
        result = self._run_git(["rev-parse", "HEAD"])
        if result.returncode != 0:
            return None
        sha = result.stdout.strip()
        return sha or None

    def get_branch_upstream(self, branch_name=None):
        branch_name = branch_name or self.get_current_branch()
        if not branch_name:
            return None
        result = self._run_git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", f"{branch_name}@{{u}}"])
        if result.returncode != 0:
            return None
        upstream = result.stdout.strip()
        return upstream or None

    def get_default_remote_branch(self, remote="origin"):
        result = self._run_git(["symbolic-ref", "--quiet", "--short", f"refs/remotes/{remote}/HEAD"])
        if result.returncode != 0:
            return None
        default_branch = result.stdout.strip()
        return default_branch or None

    def get_branch_origin(self, branch_name=None):
        branch_name = branch_name or self.get_current_branch()
        if not branch_name:
            return None

        upstream = self.get_branch_upstream(branch_name)
        if upstream:
            return upstream

        default_branch = self.get_default_remote_branch()
        if default_branch:
            return default_branch

        for candidate in ("main", "master"):
            result = self._run_git(["show-ref", "--verify", "--quiet", f"refs/heads/{candidate}"])
            if result.returncode == 0:
                return candidate

        return None

    def get_merge_base(self, ref_a, ref_b):
        result = self._run_git(["merge-base", ref_a, ref_b])
        if result.returncode != 0:
            return None
        merge_base = result.stdout.strip()
        return merge_base or None

    def get_changed_files(self, base_ref, compare_ref="HEAD"):
        result = self._run_git(["diff", "--name-only", f"{base_ref}...{compare_ref}"])
        if result.returncode != 0:
            return []
        return [line for line in result.stdout.splitlines() if line.strip()]

    def get_diff_stat(self, base_ref, compare_ref="HEAD"):
        result = self._run_git(["diff", "--stat", f"{base_ref}...{compare_ref}"])
        if result.returncode != 0:
            return ""
        return result.stdout.strip()

    def get_diff_name_status(self, base_ref, compare_ref="HEAD"):
        result = self._run_git(["diff", "--name-status", f"{base_ref}...{compare_ref}"])
        if result.returncode != 0:
            return ""
        return result.stdout.strip()

    def get_commit_summary(self, base_ref, compare_ref="HEAD", limit=50):
        result = self._run_git([
            "log",
            "--oneline",
            "--decorate",
            "--no-merges",
            f"{base_ref}..{compare_ref}",
        ])
        if result.returncode != 0:
            return ""
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        if limit and len(lines) > limit:
            lines = lines[:limit]
            lines.append("... (resumen truncado)")
        return "\n".join(lines)

    def get_diff_patch(self, base_ref, compare_ref="HEAD", paths=None, max_lines=400):
        args = ["diff", "--unified=2", "--no-color", f"{base_ref}...{compare_ref}"]
        if paths:
            args.extend(["--", *paths])
        result = self._run_git(args)
        if result.returncode != 0:
            return ""
        lines = result.stdout.splitlines()
        if max_lines and len(lines) > max_lines:
            lines = lines[:max_lines]
            lines.append("... (diff truncado)")
        return "\n".join(lines)
