from __future__ import annotations

import os
import sys
from pathlib import Path


class DesktopLaunchConfigService:
    def __init__(self, project_root: str | None = None) -> None:
        self.project_root = Path(project_root or Path.cwd()).resolve()
        self.backend_root = self.project_root / "backend"

    def detect_python_executable(self) -> str:
        candidates = [
            os.getenv("JARVIS_PYTHON"),
            str(self.project_root / ".venv" / "Scripts" / "python.exe"),
            str(self.project_root / ".venv" / "bin" / "python"),
            sys.executable,
            "python",
        ]
        for candidate in candidates:
            if candidate:
                return candidate
        return "python"

    def build_uvicorn_command(self) -> list[str]:
        python_exe = self.detect_python_executable()
        return [python_exe, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"]

    def to_dict(self) -> dict:
        return {
            "project_root": str(self.project_root),
            "backend_root": str(self.backend_root),
            "python_executable": self.detect_python_executable(),
            "uvicorn_command": self.build_uvicorn_command(),
        }
