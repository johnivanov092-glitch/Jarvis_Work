from __future__ import annotations

import os
import platform
from pathlib import Path
from fastapi import APIRouter

from app.services.desktop_launch_config_service import DesktopLaunchConfigService


router = APIRouter(prefix="/api/desktop-lifecycle", tags=["desktop-lifecycle"])


@router.get("/config")
def get_desktop_config():
    service = DesktopLaunchConfigService()
    return {
        "status": "ok",
        "platform": platform.platform(),
        "cwd": str(Path.cwd()),
        "config": service.to_dict(),
    }


@router.get("/env")
def get_desktop_env():
    keys = [
        "JARVIS_PYTHON",
        "VIRTUAL_ENV",
        "PYTHONPATH",
    ]
    return {
        "status": "ok",
        "env": {key: os.getenv(key) for key in keys},
    }
