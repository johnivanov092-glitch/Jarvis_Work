from __future__ import annotations

from typing import Any

from app.services.backend_process_service import backend_process_service
from app.services.system_state_service import system_state_service


class AppLifecycleService:
    """
    Unified startup/shutdown orchestration.

    Works now for backend mode and is ready for later Tauri integration.
    """

    def startup(self, app_mode: str = "server", desktop_attached: bool = False) -> dict[str, Any]:
        system_state_service.mark_starting(app_mode=app_mode)
        state = system_state_service.update(desktop_attached=desktop_attached)
        return {
            "ok": True,
            "message": "Jarvis lifecycle startup completed",
            "state": state,
        }

    def shutdown(self) -> dict[str, Any]:
        system_state_service.mark_stopping()
        process_status = backend_process_service.status()
        if process_status.get("managed_process"):
            backend_process_service.stop()
        state = system_state_service.mark_stopped()
        return {
            "ok": True,
            "message": "Jarvis lifecycle shutdown completed",
            "state": state,
        }

    def desktop_window_ready(self) -> dict[str, Any]:
        state = system_state_service.update(
            desktop_attached=True,
            desktop_window_ready=True,
            app_status="ready",
        )
        return {"ok": True, "state": state}

    def desktop_handshake(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        state = system_state_service.update(
            desktop_attached=True,
            app_mode="desktop",
            app_status="ready",
            meta={
                **system_state_service.get_state().get("meta", {}),
                "desktop": payload,
            },
        )
        return {
            "ok": True,
            "message": "Desktop handshake accepted",
            "state": state,
        }


app_lifecycle_service = AppLifecycleService()
