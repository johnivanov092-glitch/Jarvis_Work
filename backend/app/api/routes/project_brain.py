from pathlib import Path
from fastapi import APIRouter

router = APIRouter(prefix="/api/project-brain", tags=["project-brain"])

PROJECT_ROOT = Path(".").resolve()
EXCLUDED_PARTS = {".git", "node_modules", "target", "__pycache__", ".venv", "dist", "build"}


def _is_allowed(path: Path) -> bool:
    parts = set(path.parts)
    return not bool(parts & EXCLUDED_PARTS)


@router.get("/snapshot")
def project_snapshot():
    files = []

    for p in PROJECT_ROOT.rglob("*"):
        if not p.is_file():
            continue
        if not _is_allowed(p):
            continue

        try:
            rel = p.relative_to(PROJECT_ROOT)
        except Exception:
            continue

        files.append({
            "path": str(rel).replace("\\", "/"),
            "suffix": p.suffix.lower(),
            "size": p.stat().st_size,
        })

    files.sort(key=lambda x: x["path"])

    return {
        "status": "ok",
        "project_root": str(PROJECT_ROOT),
        "files": files,
        "files_count": len(files),
    }
