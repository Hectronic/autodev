import datetime
import json
import os
import subprocess

class CodexClient:
    def __init__(self, project_path, log_file):
        self.project_path = project_path
        self.log_file = log_file
        self.has_started = False
        self.session_id = None
        self._ensure_log_directory()

    def _ensure_log_directory(self):
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)

    def _log(self, message):
        self._ensure_log_directory()
        timestamp = datetime.datetime.now().isoformat()
        with open(self.log_file, "a") as f:
            f.write(f"[{timestamp}] {message}\n")

    def run_prompt(self, prompt, resume=False):
        self._log(f"--- NEW PROMPT (Codex) ---")
        self._log(f"Session ID: {self.session_id if self.session_id else 'None'}")
        self._log(f"Input Prompt: {prompt}")

        # Command construction for Codex
        # Iteration 1: codex --yolo exec --json "prompt"
        # Iteration 2+: codex --yolo exec resume <session_id> --json "prompt"
        cmd = ["codex", "--yolo", "exec"]

        if resume:
            cmd.append("resume")
            cmd.append("--json")
            if self.session_id:
                cmd.extend([self.session_id, prompt])
            elif self.has_started:
                cmd.extend(["--last", prompt])
            else:
                cmd.append(prompt)
        else:
            cmd.extend(["--json", prompt])

        self._log(f"Executing Command: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            cwd=self.project_path,
            capture_output=True,
            text=True
        )

        self.has_started = True

        response_text = self._extract_response_text(result.stdout)
        agent_session_id = self._extract_session_id(result.stdout)
        if agent_session_id and agent_session_id != self.session_id:
            self.session_id = agent_session_id
            self._log(f"Captured Session ID: {self.session_id}")

        if result.returncode != 0:
            self._log(f"ERROR (Code {result.returncode}): {result.stderr}")

        self._log(f"Output Response:\n{response_text}")
        self._log(f"--- END RESPONSE ---\n")

        return response_text

    def _extract_session_id(self, output):
        for line in (output or "").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            if event.get("type") in {"thread.started", "thread.resumed"} and event.get("thread_id"):
                return event["thread_id"]

        return None

    def _extract_response_text(self, output):
        messages = []
        for line in (output or "").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            if event.get("type") != "item.completed":
                continue

            item = event.get("item") or {}
            if item.get("type") == "agent_message" and item.get("text"):
                messages.append(item["text"])

        if messages:
            return "\n".join(messages).strip()

        return (output or "").strip()
