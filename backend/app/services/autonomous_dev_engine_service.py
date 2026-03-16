from __future__ import annotations

import time
import uuid
from typing import Any, Dict, Optional


class AutonomousDevEngineService:
    def __init__(
        self,
        project_brain_service=None,
        project_patch_service=None,
        run_trace_service=None,
        event_bus=None,
        tool_service=None,
    ) -> None:
        self.project_brain_service = project_brain_service
        self.project_patch_service = project_patch_service
        self.run_trace_service = run_trace_service
        self.event_bus = event_bus
        self.tool_service = tool_service

    async def run_goal(
        self,
        goal: str,
        auto_apply: bool = False,
        run_checks: bool = False,
        commit_changes: bool = False,
        requested_by: str = "user",
    ) -> dict:
        run = self._create_run(goal=goal, requested_by=requested_by)

        try:
            await self._emit("autodev.started", {"run_id": run["id"], "goal": goal})

            context = await self._scan_project(goal)
            run["steps"].append(self._step("scan_project", "completed", result=context))

            architecture = await self._analyze_architecture(goal, context)
            run["steps"].append(self._step("analyze_architecture", "completed", result=architecture))

            plan = await self._plan_refactor(goal, context, architecture)
            run["steps"].append(self._step("plan_refactor", "completed", result=plan))
            run["artifacts"].append({"title": "refactor_plan", "kind": "json", "value": plan})

            patch_preview = await self._generate_patch_preview(goal, plan)
            run["steps"].append(self._step("generate_patch", "completed", result=patch_preview))
            run["artifacts"].append({"title": "patch_preview", "kind": "json", "value": patch_preview})

            if auto_apply:
                apply_result = await self._apply_patch(patch_preview)
                run["steps"].append(self._step("apply_patch", "completed", result=apply_result))
            else:
                run["steps"].append(self._step("apply_patch", "skipped", result={"reason": "auto_apply=false"}))

            if run_checks:
                checks = await self._run_verification(goal)
                run["steps"].append(self._step("run_verification", "completed", result=checks))
            else:
                run["steps"].append(self._step("run_verification", "skipped", result={"reason": "run_checks=false"}))

            if commit_changes:
                commit_result = await self._commit_changes(goal)
                run["steps"].append(self._step("commit_git", "completed", result=commit_result))
            else:
                run["steps"].append(self._step("commit_git", "skipped", result={"reason": "commit_changes=false"}))

            run["status"] = "completed"
            run["summary"] = f"Autonomous dev flow completed for goal: {goal}"
            run["finished_at"] = time.time()

            await self._persist_trace(run)
            await self._emit("autodev.completed", {"run_id": run["id"], "goal": goal})
            return run

        except Exception as exc:
            run["status"] = "failed"
            run["error"] = str(exc)
            run["finished_at"] = time.time()
            await self._persist_trace(run)
            await self._emit("autodev.failed", {"run_id": run["id"], "error": str(exc)})
            return run

    def _create_run(self, goal: str, requested_by: str) -> dict:
        return {
            "id": str(uuid.uuid4()),
            "goal": goal,
            "requested_by": requested_by,
            "status": "running",
            "created_at": time.time(),
            "steps": [],
            "artifacts": [],
            "summary": None,
            "error": None,
        }

    def _step(self, name: str, status: str, result: Optional[dict] = None) -> dict:
        return {
            "name": name,
            "status": status,
            "timestamp": time.time(),
            "result": result or {},
        }

    async def _scan_project(self, goal: str) -> dict:
        if self.tool_service and hasattr(self.tool_service, "run_tool"):
            try:
                tree = await self._maybe_await(
                    self.tool_service.run_tool("list_project_tree", {})
                )
                return {"goal": goal, "project_tree": tree}
            except Exception:
                pass
        return {
            "goal": goal,
            "note": "Project scan placeholder. Connect to tool_service or project_service.",
        }

    async def _analyze_architecture(self, goal: str, context: dict) -> dict:
        if self.project_brain_service and hasattr(self.project_brain_service, "analyze_project"):
            result = self.project_brain_service.analyze_project(goal=goal, context=context)
            result = await self._maybe_await(result)
            return {"analysis": result}
        return {
            "analysis": "Architecture analysis placeholder",
            "focus": ["services", "routes", "tool routing", "runtime", "desktop"],
        }

    async def _plan_refactor(self, goal: str, context: dict, architecture: dict) -> dict:
        if self.project_brain_service and hasattr(self.project_brain_service, "suggest_improvement"):
            result = self.project_brain_service.suggest_improvement(goal=goal, context=context, architecture=architecture)
            result = await self._maybe_await(result)
            return {"plan": result}
        return {
            "plan": [
                "Inspect impacted services",
                "Propose minimal patch",
                "Preview diff",
                "Apply safely",
                "Run checks",
            ],
            "goal": goal,
        }

    async def _generate_patch_preview(self, goal: str, plan: dict) -> dict:
        if self.project_patch_service and hasattr(self.project_patch_service, "preview_patch"):
            result = self.project_patch_service.preview_patch(goal=goal, plan=plan)
            result = await self._maybe_await(result)
            return {"preview": result}
        return {
            "preview": {
                "mode": "placeholder",
                "goal": goal,
                "message": "Connect to project_patch_service.preview_patch(...)",
            }
        }

    async def _apply_patch(self, patch_preview: dict) -> dict:
        if self.project_patch_service and hasattr(self.project_patch_service, "apply_patch"):
            result = self.project_patch_service.apply_patch(patch_preview)
            result = await self._maybe_await(result)
            return {"apply": result}
        return {"apply": "placeholder", "message": "Connect to project_patch_service.apply_patch(...)"}

    async def _run_verification(self, goal: str) -> dict:
        if self.tool_service and hasattr(self.tool_service, "run_tool"):
            try:
                result = await self._maybe_await(
                    self.tool_service.run_tool("python_execute", {"code": "print('verification placeholder')"})
                )
                return {"checks": result}
            except Exception:
                pass
        return {"checks": "placeholder", "message": "Connect to python runner / test commands"}

    async def _commit_changes(self, goal: str) -> dict:
        if self.tool_service and hasattr(self.tool_service, "run_tool"):
            try:
                result = await self._maybe_await(
                    self.tool_service.run_tool("git_commit", {"message": f"autodev: {goal}"})
                )
                return {"commit": result}
            except Exception:
                pass
        return {"commit": "placeholder", "message": "Connect to git commit command"}

    async def _persist_trace(self, run: dict) -> None:
        if self.run_trace_service:
            try:
                existing = None
                if hasattr(self.run_trace_service, "create_run"):
                    existing = self.run_trace_service.create_run(run["goal"], source="autodev")
                if existing:
                    for step in run.get("steps", []):
                        self.run_trace_service.add_step(existing["id"], step)
                    for artifact in run.get("artifacts", []):
                        self.run_trace_service.add_artifact(existing["id"], artifact["title"], artifact["kind"], artifact["value"])
                    self.run_trace_service.update_status(
                        existing["id"],
                        run["status"],
                        summary=run.get("summary"),
                        error=run.get("error"),
                    )
            except Exception:
                pass

    async def _emit(self, event_name: str, payload: dict) -> None:
        if self.event_bus:
            try:
                await self.event_bus.publish(event_name, payload)
            except Exception:
                pass

    async def _maybe_await(self, value: Any) -> Any:
        if hasattr(value, "__await__"):
            return await value
        return value
