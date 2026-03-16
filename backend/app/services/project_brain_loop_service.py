from __future__ import annotations

from typing import Any

from app.services.project_brain_service import ProjectBrainService
from app.services.project_map_service import ProjectMapService


class ProjectBrainLoopService:
    """
    Stage 9: bounded project-brain loop.

    IMPORTANT:
    - default mode is ANALYZE ONLY
    - no infinite loop
    - no automatic git push unless auto_push=True
    - loop is bounded by max_iterations
    """

    def __init__(self) -> None:
        self.brain = ProjectBrainService()
        self.map_service = ProjectMapService()

    def analyze(self, focus: str = "backend", max_iterations: int = 3) -> dict[str, Any]:
        project_map = self.map_service.build_map()
        search = self.brain.find_code(focus)
        iterations: list[dict[str, Any]] = []

        hits = ((search.get("results") or {}).get("hits") or []) if isinstance(search, dict) else []
        candidate_paths = []
        for item in hits[:max_iterations]:
            if isinstance(item, dict) and item.get("path"):
                candidate_paths.append(item["path"])

        if not candidate_paths:
            candidate_paths = [
                "backend/app/services/agents_service.py",
                "backend/app/services/planner_v2_service.py",
                "backend/app/services/tool_service.py",
            ]

        candidate_paths = candidate_paths[:max_iterations]

        for idx, path in enumerate(candidate_paths, start=1):
            file_info = self.brain.read_file(path)
            content = ""
            if isinstance(file_info, dict):
                content = str(file_info.get("content") or file_info.get("result", {}).get("content", ""))

            suggestion = self._suggest_for_path(path, content)
            iterations.append(
                {
                    "iteration": idx,
                    "path": path,
                    "analysis": suggestion,
                    "can_patch": True,
                    "auto_pushed": False,
                }
            )

        return {
            "ok": True,
            "mode": "analyze",
            "focus": focus,
            "max_iterations": max_iterations,
            "project_map": project_map,
            "search": search,
            "iterations": iterations,
            "summary": {
                "count": len(iterations),
                "auto_push": False,
            },
        }

    def run_loop(
        self,
        *,
        path: str,
        new_content: str,
        message: str = "AI Project Brain patch",
        max_iterations: int = 1,
        auto_push: bool = False,
    ) -> dict[str, Any]:
        """
        Safe bounded loop:
        - preview
        - apply
        - optional git push
        """
        iterations: list[dict[str, Any]] = []
        loop_count = max(1, min(int(max_iterations), 3))

        for idx in range(1, loop_count + 1):
            if auto_push:
                result = self.brain.apply_patch_and_push(path, new_content, message=message)
            else:
                preview = self.brain.apply_patch_and_push.__self__.apply_patch_and_push  # keep reference stable
                # safer local flow without git
                preview_result = self.brain.apply_patch_and_push.__self__.brain.read_file(path) if False else None
                patch_preview = self.brain.apply_patch_and_push.__self__.apply_patch_and_push if False else None
                from app.services.tool_service import run_tool
                preview_only = run_tool("preview_project_patch", {"path": path, "new_content": new_content})
                apply_only = run_tool("apply_project_patch", {"path": path, "new_content": new_content})
                result = {
                    "ok": bool(apply_only.get("ok")),
                    "preview": preview_only,
                    "apply": apply_only,
                    "git": None,
                }

            iterations.append(
                {
                    "iteration": idx,
                    "path": path,
                    "result": result,
                    "auto_pushed": auto_push,
                }
            )

            # avoid repeated identical writes in the same run
            break

        return {
            "ok": True,
            "mode": "apply_loop",
            "iterations": iterations,
            "summary": {
                "count": len(iterations),
                "auto_push": auto_push,
                "bounded": True,
                "max_iterations": loop_count,
            },
        }

    def _suggest_for_path(self, path: str, content: str) -> dict[str, Any]:
        text = (content or "").lower()

        suggestions: list[str] = []
        if "run_tool(" in text and path.endswith("agents_service.py"):
            suggestions.append("Вынести повторяющиеся вызовы tool-логики в отдельные helper-функции.")
        if "timeline" in text:
            suggestions.append("Упростить формирование timeline через единый builder/helper.")
        if "route" in text and "tools" in text:
            suggestions.append("Разделить planner-логику и runtime-логику по разным слоям.")
        if "project_patch" in text:
            suggestions.append("Сделать явный dry-run режим по умолчанию перед apply.")
        if not suggestions:
            suggestions.append("Провести локальный рефакторинг и сократить ответственность файла.")

        return {
            "path": path,
            "suggestions": suggestions,
            "risk": "medium",
        }
