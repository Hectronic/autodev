from __future__ import annotations

import json
import os
from pathlib import Path


class RuntimeStore:
    def __init__(self, base_dir: str | None = None):
        self.base_dir = Path(base_dir) if base_dir else self._default_base_dir()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir = self.base_dir / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.legacy_base_dir = Path.home() / ".autodev"

    def _default_base_dir(self) -> Path:
        xdg_data_home = os.environ.get("XDG_DATA_HOME")
        if xdg_data_home:
            return Path(xdg_data_home) / "autodev"
        return Path.home() / ".local" / "share" / "autodev"

    @property
    def history_db_path(self) -> Path:
        return self.base_dir / "history.db"

    @property
    def legacy_history_db_path(self) -> Path:
        return self.legacy_base_dir / "history.db"

    def session_dir(self, session_id: str) -> Path:
        path = self.sessions_dir / session_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def session_file(self, session_id: str, filename: str) -> Path:
        return self.session_dir(session_id) / filename

    def write_text(self, path: Path, content: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content or "", encoding="utf-8")
        return path

    def write_json(self, path: Path, payload: dict) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return path
