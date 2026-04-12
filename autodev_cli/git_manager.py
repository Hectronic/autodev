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

    def push_branch(self, branch_name, remote="origin"):
        print(f"Pushing branch: {remote} {branch_name}")
        subprocess.run(["git", "push", "-u", remote, branch_name], cwd=self.project_path)

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

    def get_status_porcelain(self):
        result = self._run_git(["status", "--porcelain"])
        if result.returncode != 0:
            return []
        return [line for line in result.stdout.splitlines() if line.strip()]

    def has_changes(self):
        return bool(self.get_status_porcelain())

    def generate_commit_message(self, default_scope="changes"):
        entries = self.get_status_porcelain()
        if not entries:
            return None

        files = []
        has_docs = False
        has_tests = False
        has_config = False
        has_code = False
        additions = 0
        deletions = 0
        renames = 0

        for entry in entries:
            status = entry[:2]
            path = entry[3:].strip()
            if " -> " in path:
                _, path = path.split(" -> ", 1)
                renames += 1

            files.append(path)

            normalized = path.lower()
            parts = normalized.split("/")
            basename = parts[-1]
            if any(token in parts for token in ("docs", "doc")) or basename in ("readme.md", "changelog.md"):
                has_docs = True
            if any(token in parts for token in ("tests", "test")) or basename.startswith("test_") or basename.endswith("_test.py"):
                has_tests = True
            if any(token in parts for token in ("config", "configs", "settings")) or basename in (
                "package.json",
                "package-lock.json",
                "poetry.lock",
                "requirements.txt",
                "pyproject.toml",
                "setup.py",
                "setup.cfg",
                "tox.ini",
                ".gitignore",
            ):
                has_config = True
            if basename.endswith((".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rb", ".java", ".rs", ".php", ".cs", ".c", ".cc", ".cpp", ".h", ".hpp", ".swift", ".kt", ".kts", ".m", ".mm", ".sql", ".sh")):
                has_code = True

            if "A" in status:
                additions += 1
            if "D" in status:
                deletions += 1

        if has_docs and not (has_tests or has_code):
            prefix = "docs"
        elif has_tests and not (has_docs or has_config):
            prefix = "test"
        elif has_config and not has_code:
            prefix = "chore"
        elif deletions and not additions and not has_docs:
            prefix = "fix"
        elif renames and not has_docs:
            prefix = "refactor"
        else:
            prefix = "feat" if has_code else "chore"

        scope = self._derive_commit_scope(files) or default_scope
        return f"{prefix}: update {scope}"

    def commit_and_push_generated_changes(self, remote="origin"):
        if not self.has_changes():
            print("No hay cambios para commitear.")
            return None

        message = self.generate_commit_message()
        if not message:
            print("No se pudo generar un mensaje de commit.")
            return None

        current_branch = self.get_current_branch()
        if not current_branch:
            print("No se pudo determinar la rama actual para hacer push.")
            return None
        self.commit_changes(message)
        self.push_branch(current_branch, remote=remote)
        return message

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

    def get_staged_changed_files(self):
        result = self._run_git(["diff", "--cached", "--name-only"])
        if result.returncode != 0:
            return []
        return [line for line in result.stdout.splitlines() if line.strip()]

    def get_unstaged_changed_files(self):
        result = self._run_git(["diff", "--name-only"])
        if result.returncode != 0:
            return []
        return [line for line in result.stdout.splitlines() if line.strip()]

    def get_untracked_files(self):
        result = self._run_git(["ls-files", "--others", "--exclude-standard"])
        if result.returncode != 0:
            return []
        return [line for line in result.stdout.splitlines() if line.strip()]

    def get_diff_stat(self, base_ref, compare_ref="HEAD"):
        result = self._run_git(["diff", "--stat", f"{base_ref}...{compare_ref}"])
        if result.returncode != 0:
            return ""
        return result.stdout.strip()

    def get_staged_diff_stat(self):
        result = self._run_git(["diff", "--cached", "--stat"])
        if result.returncode != 0:
            return ""
        return result.stdout.strip()

    def get_unstaged_diff_stat(self):
        result = self._run_git(["diff", "--stat"])
        if result.returncode != 0:
            return ""
        return result.stdout.strip()

    def get_diff_name_status(self, base_ref, compare_ref="HEAD"):
        result = self._run_git(["diff", "--name-status", f"{base_ref}...{compare_ref}"])
        if result.returncode != 0:
            return ""
        return result.stdout.strip()

    def get_staged_diff_name_status(self):
        result = self._run_git(["diff", "--cached", "--name-status"])
        if result.returncode != 0:
            return ""
        return result.stdout.strip()

    def get_unstaged_diff_name_status(self):
        result = self._run_git(["diff", "--name-status"])
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

    def get_staged_diff_patch(self, paths=None, max_lines=400):
        args = ["diff", "--cached", "--unified=2", "--no-color"]
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

    def get_unstaged_diff_patch(self, paths=None, max_lines=400):
        args = ["diff", "--unified=2", "--no-color"]
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

    def _derive_commit_scope(self, files):
        if not files:
            return None
        if len(files) == 1:
            return self._normalize_scope_token(files[0].rsplit("/", 1)[-1].rsplit(".", 1)[0])

        top_level = []
        for path in files:
            parts = path.split("/")
            if len(parts) > 1:
                top_level.append(parts[0])
            else:
                stem = parts[0].rsplit(".", 1)[0]
                top_level.append(stem)

        if top_level:
            first = top_level[0]
            if all(item == first for item in top_level):
                return self._normalize_scope_token(first)

        return self._normalize_scope_token(self._common_prefix_token(files))

    def _normalize_scope_token(self, token):
        token = (token or "").strip().replace("_", " ").replace("-", " ")
        token = " ".join(part for part in token.split() if part)
        if not token:
            return None
        if token.isupper():
            return token
        return token[:1].lower() + token[1:]

    def _common_prefix_token(self, files):
        if not files:
            return None

        first = files[0].split("/")
        common = []
        for index, part in enumerate(first):
            if all(len(path.split("/")) > index and path.split("/")[index] == part for path in files):
                common.append(part)
            else:
                break

        if common:
            return common[-1]

        return files[0].rsplit("/", 1)[-1].rsplit(".", 1)[0]
