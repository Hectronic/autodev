import datetime
import os
import re
import subprocess

class GeminiClient:
    def __init__(self, project_path, log_file):
        self.project_path = project_path
        self.log_file = log_file
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
        self._log(f"--- NEW PROMPT ---")
        self._log(f"Session ID: {self.session_id if self.session_id else 'None'}")
        self._log(f"Input Prompt: {prompt}")

        cmd = ["gemini", "-y", "-p", prompt]
        if resume and self.session_id:
            cmd.extend(["-r", self.session_id])
        
        self._log(f"Executing Command: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            cwd=self.project_path,
            capture_output=True,
            text=True
        )
        
        # After first call, if we don't have session_id, try to get it
        if not self.session_id:
            self.session_id = self._get_latest_session_id()
            self._log(f"Captured Session ID: {self.session_id}")

        if result.returncode != 0:
            self._log(f"ERROR (Code {result.returncode}): {result.stderr}")
        
        self._log(f"Output Response:\n{result.stdout}")
        self._log(f"--- END RESPONSE ---\n")
            
        return result.stdout

    def _get_latest_session_id(self):
        result = subprocess.run(
            ["gemini", "--list-sessions"],
            cwd=self.project_path,
            capture_output=True,
            text=True
        )
        matches = re.findall(r'\[([^\]]+)\]', result.stdout)
        if matches:
            return matches[0]
        return "latest"
