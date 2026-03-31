"""Workflow-backed multi-agent compatibility shim.

The legacy service entrypoint stays stable for `/api/advanced/multi-agent`,
but execution is fully delegated to the Workflow Engine.
"""
from __future__ import annotations

from typing import Any


def run_multi_agent(
    query: str,
    model_name: str = "qwen3:8b",
    context: str = "",
    agents: list[str] | None = None,
    use_reflection: bool = False,
    use_orchestrator: bool = False,
) -> dict[str, Any]:
    from app.services.workflow_engine import run_multi_agent_workflow

    return run_multi_agent_workflow(
        query=query,
        model_name=model_name,
        context=context,
        agents=agents,
        use_reflection=use_reflection,
        use_orchestrator=use_orchestrator,
    )
