from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = BASE_DIR / "data"
STATE_DIR = DATA_DIR / "system"
STATE_FILE = STATE_DIR / "system_state.json"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SystemState:
    app_mode: str = "server"
    app_status: str = "starting"
    backend_status: str = "unknown"
    frontend_status: str = "unknown"
    desktop_attached: bool = False
    desktop_window_ready: bool = False
    backend_pid: int | None = None
    backend_url: str = "http://127.0.0.1:8000"
    started_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    last_error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class SystemStateService:
    """
    Central runtime state for Jarvis Desktop / backend lifecycle.

    Safe to use from FastAPI routes, startup hooks, and future Tauri bridge code.
    Persists a small JSON snapshot under data/system/system_state.json.
    """

    def __init__(self, state_file: Path | None = None) -> None:
        self.state_file = state_file or STATE_FILE
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._state = self._load_or_create()

    def _load_or_create(self) -> SystemState:
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return SystemState(**{**asdict(SystemState()), **data})
            except Exception:
                pass
        state = SystemState()
        self._write(state)
        return state

    def _write(self, state: SystemState) -> None:
        state.updated_at = utc_now_iso()
        self.state_file.write_text(
            json.dumps(asdict(state), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_state(self) -> dict[str, Any]:
        with self._lock:
            return asdict(self._state)

    def update(self, **changes: Any) -> dict[str, Any]:
        with self._lock:
            for key, value in changes.items():
                if hasattr(self._state, key):
                    setattr(self._state, key, value)
                else:
                    self._state.meta[key] = value
            self._write(self._state)
            return asdict(self._state)

    def mark_starting(self, app_mode: str = "server", backend_url: str = "http://127.0.0.1:8000") -> dict[str, Any]:
        return self.update(
            app_mode=app_mode,
            app_status="starting",
            backend_status="starting",
            backend_url=backend_url,
            last_error=None,
        )

    def mark_ready(self, desktop_attached: bool = False) -> dict[str, Any]:
        return self.update(
            app_status="ready",
            backend_status="ready",
            desktop_attached=desktop_attached,
            last_error=None,
        )

    def mark_stopping(self) -> dict[str, Any]:
        return self.update(app_status="stopping", backend_status="stopping")

    def mark_stopped(self) -> dict[str, Any]:
        return self.update(
            app_status="stopped",
            backend_status="stopped",
            desktop_window_ready=False,
            backend_pid=None,
        )

    def mark_error(self, error: str) -> dict[str, Any]:
        return self.update(app_status="error", backend_status="error", last_error=error)


system_state_service = SystemStateService()
