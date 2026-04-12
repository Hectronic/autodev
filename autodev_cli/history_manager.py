import datetime
import shutil
import sqlite3
from pathlib import Path

from .runtime_store import RuntimeStore

class HistoryManager:
    def __init__(self, storage=None):
        self.storage = storage or RuntimeStore()
        self.db_dir = self.storage.base_dir
        self.db_path = self.storage.history_db_path
        self._migrate_legacy_history_db()
        self._init_db()

    def _migrate_legacy_history_db(self):
        legacy_db_path = self.storage.legacy_history_db_path
        if self.db_path.exists() or not legacy_db_path.exists():
            return
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy_db_path, self.db_path)

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS execution_sessions (
                    id TEXT PRIMARY KEY,
                    project_path TEXT,
                    branch_name TEXT,
                    workflow TEXT,
                    base_branch TEXT,
                    merge_base_sha TEXT,
                    agent TEXT,
                    instructions TEXT,
                    timestamp DATETIME,
                    updated_at DATETIME,
                    status TEXT,
                    results_dir TEXT,
                    log_path TEXT,
                    summary_md_path TEXT,
                    summary_html_path TEXT,
                    agent_session_id TEXT,
                    head_sha TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS session_steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    step_order INTEGER,
                    step_label TEXT,
                    prompt TEXT,
                    response TEXT,
                    input_path TEXT,
                    output_path TEXT,
                    timestamp DATETIME,
                    FOREIGN KEY (session_id) REFERENCES execution_sessions(id)
                )
            """)
            self._ensure_columns(cursor, "execution_sessions", {
                "branch_name": "TEXT",
                "workflow": "TEXT",
                "base_branch": "TEXT",
                "merge_base_sha": "TEXT",
                "updated_at": "DATETIME",
                "status": "TEXT",
                "log_path": "TEXT",
                "summary_md_path": "TEXT",
                "summary_html_path": "TEXT",
                "agent_session_id": "TEXT",
                "head_sha": "TEXT",
            })
            self._ensure_columns(cursor, "session_steps", {
                "step_order": "INTEGER",
                "input_path": "TEXT",
                "output_path": "TEXT",
            })
            conn.commit()

    def _ensure_columns(self, cursor, table_name, columns):
        cursor.execute(f"PRAGMA table_info({table_name})")
        existing = {row[1] for row in cursor.fetchall()}
        for column_name, column_type in columns.items():
            if column_name not in existing:
                cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")

    def create_session(self, session_id, project_path, agent, instructions, results_dir,
                       branch_name=None, workflow=None, base_branch=None, merge_base_sha=None,
                       status="running", log_path=None,
                       summary_md_path=None, summary_html_path=None,
                       agent_session_id=None, head_sha=None):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO execution_sessions (
                    id, project_path, branch_name, workflow, base_branch, merge_base_sha,
                    agent, instructions,
                    timestamp, updated_at, status, results_dir, log_path,
                    summary_md_path, summary_html_path, agent_session_id, head_sha
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    project_path,
                    branch_name,
                    workflow,
                    base_branch,
                    merge_base_sha,
                    agent,
                    instructions,
                    datetime.datetime.now().isoformat(),
                    datetime.datetime.now().isoformat(),
                    status,
                    results_dir,
                    log_path,
                    summary_md_path,
                    summary_html_path,
                    agent_session_id,
                    head_sha,
                ),
            )
            conn.commit()

    def update_session(self, session_id, **fields):
        if not fields:
            return
        fields["updated_at"] = datetime.datetime.now().isoformat()
        columns = ", ".join(f"{key} = ?" for key in fields)
        values = list(fields.values())
        values.append(session_id)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE execution_sessions SET {columns} WHERE id = ?", values)
            conn.commit()

    def save_step(self, session_id, step_label, prompt, response, step_order=None,
                  input_path=None, output_path=None):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO session_steps (
                    session_id, step_order, step_label, prompt, response,
                    input_path, output_path, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    step_order,
                    step_label,
                    prompt,
                    response,
                    input_path,
                    output_path,
                    datetime.datetime.now().isoformat(),
                ),
            )
            conn.commit()

    def get_sessions(self, limit=10):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, project_path, branch_name, workflow, base_branch, merge_base_sha,
                       agent, instructions, timestamp,
                       status, results_dir, log_path, summary_md_path, summary_html_path,
                       agent_session_id, head_sha
                FROM execution_sessions
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_session_steps(self, session_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT step_order, step_label, prompt, response, input_path, output_path, timestamp
                FROM session_steps
                WHERE session_id = ?
                ORDER BY COALESCE(step_order, id) ASC, timestamp ASC
                """,
                (session_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_session(self, session_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, project_path, branch_name, workflow, base_branch, merge_base_sha,
                       agent, instructions, timestamp,
                       updated_at, status, results_dir, log_path, summary_md_path,
                       summary_html_path, agent_session_id, head_sha
                FROM execution_sessions
                WHERE id = ?
                """,
                (session_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_running_session_for_branch(self, project_path, branch_name, agent=None, workflow=None):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            query = """
                SELECT id, project_path, branch_name, workflow, base_branch, merge_base_sha,
                       agent, instructions, timestamp,
                       updated_at, status, results_dir, log_path, summary_md_path,
                       summary_html_path, agent_session_id, head_sha
                FROM execution_sessions
                WHERE project_path = ? AND branch_name = ? AND status = 'running'
            """
            params = [project_path, branch_name]
            if workflow:
                query += " AND (workflow = ? OR workflow IS NULL)"
                params.append(workflow)
            if agent:
                query += " AND agent = ?"
                params.append(agent)
            query += " ORDER BY timestamp DESC LIMIT 1"
            cursor.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_step_count(self, session_id):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM session_steps WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            return row[0] if row else 0

    def close_session(self, session_id, status="completed"):
        self.update_session(session_id, status=status)
