from __future__ import annotations

from typing import Any

from app.services.app_lifecycle_service import app_lifecycle_service
from app.services.backend_process_service import backend_process_service
from app.services.system_state_service import system_state_service


class DesktopRuntimeService:
    """
    Desktop-focused facade for Tauri and future OS-level runtime actions.
    """

    def get_runtime_status(self) -> dict[str, Any]:
        return {
            "ok": True,
            "mode": system_state_service.get_state().get("app_mode", "server"),
            "system": system_state_service.get_state(),
            "backend_process": backend_process_service.status(),
        }

    def desktop_bootstrap(self) -> dict[str, Any]:
        startup = app_lifecycle_service.startup(app_mode="desktop", desktop_attached=True)
        return {
            "ok": True,
            "message": "Desktop runtime bootstrap complete",
            "startup": startup,
            "runtime": self.get_runtime_status(),
        }

    def desktop_handshake(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        handshake = app_lifecycle_service.desktop_handshake(payload)
        return {
            "ok": True,
            "handshake": handshake,
            "runtime": self.get_runtime_status(),
        }

    def mark_window_ready(self) -> dict[str, Any]:
        result = app_lifecycle_service.desktop_window_ready()
        return {
            "ok": True,
            "message": "Desktop window marked as ready",
            "result": result,
            "runtime": self.get_runtime_status(),
        }


desktop_runtime_service = DesktopRuntimeService()
