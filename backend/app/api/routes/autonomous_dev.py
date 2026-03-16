from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.autonomous_dev_engine_service import AutonomousDevEngineService

# Optional integrations
try:
    from app.services.event_bus_service import EventBusService
except Exception:
    EventBusService = None

try:
    from app.services.run_trace_service import RunTraceService
except Exception:
    RunTraceService = None

try:
    from app.services.project_brain_service import ProjectBrainService
except Exception:
    ProjectBrainService = None

try:
    from app.services.project_patch_service import ProjectPatchService
except Exception:
    ProjectPatchService = None

try:
    from app.services.tool_service import ToolService
except Exception:
    ToolService = None


router = APIRouter(prefix="/api/autodev", tags=["autonomous-dev"])

event_bus = EventBusService() if EventBusService else None
run_trace_service = RunTraceService() if RunTraceService else None
project_brain_service = ProjectBrainService() if ProjectBrainService else None
project_patch_service = ProjectPatchService() if ProjectPatchService else None
tool_service = ToolService() if ToolService else None

engine = AutonomousDevEngineService(
    project_brain_service=project_brain_service,
    project_patch_service=project_patch_service,
    run_trace_service=run_trace_service,
    event_bus=event_bus,
    tool_service=tool_service,
)


class AutoDevRunRequest(BaseModel):
    goal: str = Field(..., min_length=1)
    auto_apply: bool = False
    run_checks: bool = False
    commit_changes: bool = False
    requested_by: str = "user"


@router.get("/status")
def status():
    return {
        "status": "ok",
        "engine": "autonomous-dev",
        "integrations": {
            "event_bus": event_bus is not None,
            "run_trace_service": run_trace_service is not None,
            "project_brain_service": project_brain_service is not None,
            "project_patch_service": project_patch_service is not None,
            "tool_service": tool_service is not None,
        },
    }


@router.post("/run")
async def run_autonomous_dev(payload: AutoDevRunRequest):
    return await engine.run_goal(
        goal=payload.goal,
        auto_apply=payload.auto_apply,
        run_checks=payload.run_checks,
        commit_changes=payload.commit_changes,
        requested_by=payload.requested_by,
    )
