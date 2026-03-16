
from __future__ import annotations

from typing import Any
from app.services.project_service import list_project_tree, search_project, read_project_file
from app.services.tool_service import run_tool


class ProjectBrainService:
    '''
    Stage 8 – Project Brain

    Capabilities:
    - scan project structure
    - search codebase
    - read important files
    - suggest improvements
    - optionally trigger patches + git commits
    '''

    def scan_project(self) -> dict[str, Any]:
        tree = list_project_tree(max_depth=4, max_items=500)
        return {
            "ok": True,
            "type": "project_scan",
            "tree": tree
        }

    def find_code(self, query: str) -> dict[str, Any]:
        results = search_project(query=query, max_hits=50)
        return {
            "ok": True,
            "type": "search",
            "query": query,
            "results": results
        }

    def read_file(self, path: str) -> dict[str, Any]:
        return read_project_file(path, max_chars=20000)

    def apply_patch_and_push(self, path: str, new_content: str, message: str = "AI Project Brain patch"):
        preview = run_tool("preview_project_patch", {
            "path": path,
            "new_content": new_content
        })

        if not preview.get("ok"):
            return preview

        apply = run_tool("apply_project_patch", {
            "path": path,
            "new_content": new_content
        })

        if not apply.get("ok"):
            return apply

        git = run_tool("git_commit_push", {
            "message": message
        })

        return {
            "ok": True,
            "preview": preview,
            "apply": apply,
            "git": git
        }
