from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.agent_runtime_service import run_isolated_agent


router = APIRouter(prefix="/api/agent-runtime", tags=["agent-runtime"])


class AgentRuntimeRequest(BaseModel):
    user_input: str = Field(..., min_length=1)


@router.post("/run")
def run_agent_runtime(payload: AgentRuntimeRequest):
    return run_isolated_agent(payload.user_input)
