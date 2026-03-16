from __future__ import annotations

from typing import Any

from app.services.project_service import list_project_tree, search_project, read_project_file


class ProjectMapService:
    """
    Stage 10: project map / lightweight index.

    Safe:
    - reads tree
    - can search
    - can inspect important files
    - does NOT modify anything
    """

    IMPORTANT_HINTS = [
        "backend/app/main.py",
        "backend/app/services/agents_service.py",
        "backend/app/services/planner_v2_service.py",
        "backend/app/services/tool_service.py",
        "backend/app/services/project_patch_service.py",
        "backend/app/services/project_brain_service.py",
        "frontend/src/App.jsx",
        "frontend/src/api/api.js",
    ]

    def build_map(self, max_depth: int = 4, max_items: int = 500) -> dict[str, Any]:
        tree = list_project_tree(max_depth=max_depth, max_items=max_items)
        items = tree.get("items", []) if isinstance(tree, dict) else []

        dirs = [x.get("path") for x in items if isinstance(x, dict) and x.get("type") == "dir"]
        files = [x.get("path") for x in items if isinstance(x, dict) and x.get("type") == "file"]

        important_existing = [p for p in self.IMPORTANT_HINTS if p in files]

        return {
            "ok": True,
            "type": "project_map",
            "root": tree.get("root"),
            "dir_count": len(dirs),
            "file_count": len(files),
            "important_files": important_existing,
            "tree": tree,
        }

    def search(self, query: str, max_hits: int = 30) -> dict[str, Any]:
        result = search_project(query=query, max_hits=max_hits)
        return {
            "ok": True,
            "type": "project_map_search",
            "query": query,
            "result": result,
        }

    def inspect_file(self, path: str, max_chars: int = 20000) -> dict[str, Any]:
        result = read_project_file(path, max_chars=max_chars)
        return {
            "ok": bool(result.get("ok")),
            "type": "project_map_file",
            "path": path,
            "result": result,
        }
