from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.project_brain_engine_service import ProjectBrainEngineService

try:
    from app.services.run_trace_service import RunTraceService
except Exception:
    RunTraceService = None

try:
    from app.services.event_bus_service import EventBusService
except Exception:
    EventBusService = None

try:
    from app.services.tool_service import ToolService
except Exception:
    ToolService = None

try:
    from app.services.project_brain_service import ProjectBrainService
except Exception:
    ProjectBrainService = None


router = APIRouter(prefix="/api/project-brain", tags=["project-brain"])

run_trace_service = RunTraceService() if RunTraceService else None
event_bus = EventBusService() if EventBusService else None
tool_service = ToolService() if ToolService else None
project_brain_service = ProjectBrainService() if ProjectBrainService else None

engine = ProjectBrainEngineService(
    project_root=".",
    dependency_graph_service=None,
    project_brain_service=project_brain_service,
    tool_service=tool_service,
    run_trace_service=run_trace_service,
    event_bus=event_bus,
)


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)


class GoalRequest(BaseModel):
    goal: str = Field(..., min_length=1)


@router.get("/status")
async def status():
    return await engine.health()


@router.get("/snapshot")
async def snapshot():
    return await engine.build_project_snapshot()


@router.post("/index/search")
async def search_index(payload: QueryRequest):
    return await engine.search_index(payload.query)


@router.post("/analyze")
async def analyze(payload: GoalRequest):
    return await engine.analyze_project_goal(payload.goal)


@router.post("/plan")
async def plan(payload: GoalRequest):
    return await engine.create_refactor_plan(payload.goal)
