
from fastapi import APIRouter
from pydantic import BaseModel
from pathlib import Path
import datetime

router = APIRouter(prefix="/api/jarvis/autoloop", tags=["jarvis-autoloop"])

PROJECT_ROOT = Path(".").resolve()

class LoopPayload(BaseModel):
    goal: str
    path: str
    content: str

@router.post("/run")
def run_loop(payload: LoopPayload):
    """
    Phase 18.3 autonomous dev loop (safe mode)
    """
    target = (PROJECT_ROOT / payload.path).resolve()

    if not target.exists():
        return {"status": "error", "message": "file not found"}

    disk = target.read_text(encoding="utf-8")

    changed = payload.content != disk

    steps = [
        {"step": "plan", "status": "done"},
        {"step": "preview", "status": "done"},
        {"step": "apply", "status": "ready" if changed else "skip"},
        {"step": "verify", "status": "queued"}
    ]

    return {
        "status": "ok",
        "goal": payload.goal,
        "path": payload.path,
        "changed": changed,
        "steps": steps,
        "time": datetime.datetime.utcnow().isoformat()
    }
