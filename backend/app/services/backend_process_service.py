from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.system_state_service import system_state_service


BASE_DIR = Path(__file__).resolve().parents[3]
BACKEND_DIR = BASE_DIR / "backend"


@dataclass
class BackendProcessConfig:
    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = False
    startup_timeout_seconds: int = 20
    python_executable: str = sys.executable

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


class BackendProcessService:
    """
    Future-proof helper for Tauri mode.

    Today it can:
    - detect whether backend port is already listening
    - start uvicorn in a subprocess when needed
    - stop the subprocess gracefully

    It is safe to keep unused in pure browser/server mode.
    """

    def __init__(self, config: BackendProcessConfig | None = None) -> None:
        self.config = config or BackendProcessConfig()
        self._process: subprocess.Popen[str] | None = None

    def is_port_open(self, host: str | None = None, port: int | None = None) -> bool:
        host = host or self.config.host
        port = port or self.config.port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            return sock.connect_ex((host, port)) == 0

    def status(self) -> dict[str, Any]:
        pid = self._process.pid if self._process else None
        alive = bool(self._process and self._process.poll() is None)
        return {
            "ok": True,
            "managed_process": self._process is not None,
            "pid": pid,
            "alive": alive,
            "base_url": self.config.base_url,
            "port_open": self.is_port_open(),
        }

    def start_if_needed(self) -> dict[str, Any]:
        if self.is_port_open():
            system_state_service.update(backend_status="ready", backend_url=self.config.base_url)
            return {
                "ok": True,
                "started": False,
                "reason": "backend already listening",
                "base_url": self.config.base_url,
            }

        command = [
            self.config.python_executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            self.config.host,
            "--port",
            str(self.config.port),
        ]
        if self.config.reload:
            command.append("--reload")

        env = os.environ.copy()
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(BACKEND_DIR) + (os.pathsep + existing if existing else "")

        self._process = subprocess.Popen(
            command,
            cwd=str(BACKEND_DIR),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        system_state_service.update(
            backend_status="starting",
            backend_pid=self._process.pid,
            backend_url=self.config.base_url,
        )

        deadline = time.time() + self.config.startup_timeout_seconds
        while time.time() < deadline:
            if self.is_port_open():
                system_state_service.update(backend_status="ready", backend_pid=self._process.pid)
                return {
                    "ok": True,
                    "started": True,
                    "pid": self._process.pid,
                    "base_url": self.config.base_url,
                }
            if self._process.poll() is not None:
                break
            time.sleep(0.25)

        error = "Backend process failed to start within timeout"
        system_state_service.mark_error(error)
        return {
            "ok": False,
            "started": False,
            "error": error,
            "base_url": self.config.base_url,
        }

    def stop(self, timeout_seconds: int = 8) -> dict[str, Any]:
        if not self._process:
            return {"ok": True, "stopped": False, "reason": "no managed process"}

        if self._process.poll() is not None:
            pid = self._process.pid
            self._process = None
            return {"ok": True, "stopped": False, "reason": "process already exited", "pid": pid}

        self._process.terminate()
        try:
            self._process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait(timeout=3)

        pid = self._process.pid
        self._process = None
        system_state_service.update(backend_status="stopped", backend_pid=None)
        return {"ok": True, "stopped": True, "pid": pid}


backend_process_service = BackendProcessService()
