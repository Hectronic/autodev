import sqlite3
import os
import datetime
from pathlib import Path

class HistoryManager:
    def __init__(self):
        self.db_dir = Path.home() / ".autodev"
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.db_dir / "history.db"
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Tabla de sesiones de ejecución
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS execution_sessions (
                    id TEXT PRIMARY KEY,
                    project_path TEXT,
                    agent TEXT,
                    instructions TEXT,
                    timestamp DATETIME,
                    results_dir TEXT
                )
            """)
            # Tabla de prompts y respuestas (pasos)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS session_steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    step_label TEXT,
                    prompt TEXT,
                    response TEXT,
                    timestamp DATETIME,
                    FOREIGN KEY (session_id) REFERENCES execution_sessions(id)
                )
            """)
            conn.commit()

    def create_session(self, session_id, project_path, agent, instructions, results_dir):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO execution_sessions (id, project_path, agent, instructions, timestamp, results_dir) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, project_path, agent, instructions, datetime.datetime.now().isoformat(), results_dir)
            )
            conn.commit()

    def save_step(self, session_id, step_label, prompt, response):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO session_steps (session_id, step_label, prompt, response, timestamp) VALUES (?, ?, ?, ?, ?)",
                (session_id, step_label, prompt, response, datetime.datetime.now().isoformat())
            )
            conn.commit()

    def get_sessions(self, limit=10):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, project_path, agent, instructions, timestamp FROM execution_sessions ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_session_steps(self, session_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT step_label, prompt, response, timestamp FROM session_steps WHERE session_id = ? ORDER BY timestamp ASC",
                (session_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
