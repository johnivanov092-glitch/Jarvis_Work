
from fastapi import APIRouter
from app.services.agent_executor import run_agent_step

router = APIRouter(prefix="/api/agent", tags=["agent"])

@router.post("/run")
def run(payload: dict):
    return run_agent_step(payload)
