from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.desktop_runtime_service import desktop_runtime_service

router = APIRouter(prefix="/api/desktop", tags=["desktop"])


class DesktopHandshakeRequest(BaseModel):
    client: str = Field(default="tauri")
    version: str = Field(default="0.1.0")
    meta: dict[str, Any] = Field(default_factory=dict)


@router.get("/status")
def desktop_status():
    return desktop_runtime_service.get_runtime_status()


@router.post("/bootstrap")
def desktop_bootstrap():
    return desktop_runtime_service.desktop_bootstrap()


@router.post("/handshake")
def desktop_handshake(payload: DesktopHandshakeRequest):
    return desktop_runtime_service.desktop_handshake(payload.model_dump())


@router.post("/window-ready")
def desktop_window_ready():
    return desktop_runtime_service.mark_window_ready()
