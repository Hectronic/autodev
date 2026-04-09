import subprocess
import datetime

class CodexClient:
    def __init__(self, project_path, log_file):
        self.project_path = project_path
        self.log_file = log_file
        self.has_started = False

    def _log(self, message):
        timestamp = datetime.datetime.now().isoformat()
        with open(self.log_file, "a") as f:
            f.write(f"[{timestamp}] {message}\n")

    def run_prompt(self, prompt, resume=False):
        self._log(f"--- NEW PROMPT (Codex) ---")
        self._log(f"Input Prompt: {prompt}")

        # Command construction for Codex
        # Iteration 1: codex --yolo exec "prompt"
        # Iteration 2+: codex --yolo exec resume --last "prompt"
        cmd = ["codex", "--yolo", "exec"]
        
        if resume and self.has_started:
            cmd.extend(["resume", "--last"])
        
        cmd.append(prompt)
        
        self._log(f"Executing Command: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            cwd=self.project_path,
            capture_output=True,
            text=True
        )
        
        self.has_started = True

        if result.returncode != 0:
            self._log(f"ERROR (Code {result.returncode}): {result.stderr}")
        
        self._log(f"Output Response:\n{result.stdout}")
        self._log(f"--- END RESPONSE ---\n")
            
        return result.stdout
