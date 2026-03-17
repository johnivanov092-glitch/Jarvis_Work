
from fastapi import APIRouter
from pydantic import BaseModel
from pathlib import Path
import datetime

router = APIRouter(prefix="/api/jarvis/supervisor", tags=["jarvis-supervisor-auto"])

PROJECT_ROOT = Path(".").resolve()

class AutoApplyPayload(BaseModel):
    path: str
    content: str

@router.post("/auto-apply")
def auto_apply(payload: AutoApplyPayload):
    target = (PROJECT_ROOT / payload.path).resolve()

    if not target.exists():
        return {"status": "error", "message": "file not found"}

    old = target.read_text(encoding="utf-8")

    if old == payload.content:
        return {"status": "no_change"}

    backup = target.with_suffix(target.suffix + ".bak")
    backup.write_text(old, encoding="utf-8")

    target.write_text(payload.content, encoding="utf-8")

    return {
        "status": "applied",
        "path": payload.path,
        "backup": str(backup),
        "time": datetime.datetime.utcnow().isoformat()
    }
