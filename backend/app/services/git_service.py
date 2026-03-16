from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


class GitService:
    """
    Stage 7: AI Dev Mode git service.
    """

    def __init__(self, repo_root: str | None = None):
        base_dir = Path(__file__).resolve().parents[3]
        self.repo_root = Path(repo_root) if repo_root else base_dir

    def _run(self, args: list[str]) -> dict[str, Any]:
        try:
            result = subprocess.run(
                args,
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            return {
                "ok": result.returncode == 0,
                "command": " ".join(args),
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            }
        except Exception as exc:
            return {
                "ok": False,
                "command": " ".join(args),
                "returncode": -1,
                "stdout": "",
                "stderr": str(exc),
            }

    def status(self) -> dict[str, Any]:
        return self._run(["git", "status", "--short"])

    def add_all(self) -> dict[str, Any]:
        return self._run(["git", "add", "."])

    def commit(self, message: str = "AI update") -> dict[str, Any]:
        return self._run(["git", "commit", "-m", message])

    def push(self) -> dict[str, Any]:
        return self._run(["git", "push"])

    def commit_and_push(self, message: str = "AI update") -> dict[str, Any]:
        status_before = self.status()
        add_result = self.add_all()
        if not add_result.get("ok"):
            return {
                "ok": False,
                "step": "git_add",
                "status_before": status_before,
                "add_result": add_result,
            }

        commit_result = self.commit(message)
        if not commit_result.get("ok"):
            combined = (commit_result.get("stdout", "") + " " + commit_result.get("stderr", "")).lower()
            no_changes = "nothing to commit" in combined
            return {
                "ok": no_changes,
                "step": "git_commit",
                "status_before": status_before,
                "add_result": add_result,
                "commit_result": commit_result,
                "message": "No changes to commit" if no_changes else "Commit failed",
            }

        push_result = self.push()
        return {
            "ok": bool(push_result.get("ok")),
            "step": "git_push",
            "status_before": status_before,
            "add_result": add_result,
            "commit_result": commit_result,
            "push_result": push_result,
        }
