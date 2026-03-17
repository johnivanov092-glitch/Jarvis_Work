from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/project-brain", tags=["project-brain"])

PROJECT_ROOT = Path(".").resolve()
EXCLUDED_PARTS = {
    ".git",
    ".idea",
    ".vscode",
    "node_modules",
    "target",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".next",
    ".turbo",
    ".cache",
    "coverage",
    "tmp",
    "temp",
    "logs",
}
TEXT_SUFFIXES = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".json",
    ".md",
    ".txt",
    ".yaml",
    ".yml",
    ".toml",
    ".rs",
    ".css",
    ".scss",
    ".html",
    ".htm",
    ".sql",
    ".sh",
    ".bat",
    ".ps1",
    ".ini",
    ".cfg",
    ".conf",
    ".example",
    ".env",
}
TEXT_NAMES = {
    "Dockerfile",
    "Makefile",
    ".gitignore",
}
MAX_READ_BYTES = 512 * 1024
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
DEFAULT_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "")
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "180"))
MAX_AGENT_FILE_BYTES = 256 * 1024


class LocalAgentRunRequest(BaseModel):
    goal: str = Field(..., min_length=3, max_length=4000)
    selected_path: str = Field(..., min_length=1)
    selected_content: str = Field(..., min_length=1, max_length=400_000)
    model: str | None = Field(default=None, max_length=200)
    project_files: list[str] = Field(default_factory=list)
    mode: str = Field(default="patch", max_length=64)


class LocalAgentPlanRequest(BaseModel):
    goal: str = Field(..., min_length=3, max_length=4000)
    selected_path: str = Field(..., min_length=1)
    selected_content: str = Field(..., min_length=1, max_length=400_000)
    model: str | None = Field(default=None, max_length=200)



def _is_allowed(path: Path) -> bool:
    return not bool(set(path.parts) & EXCLUDED_PARTS)



def _normalize_relative_path(raw_path: str) -> Path:
    if not raw_path or not raw_path.strip():
        raise HTTPException(status_code=400, detail="Path is required")

    normalized = raw_path.replace("\\", "/").strip().lstrip("/")
    rel = Path(normalized)

    if rel.is_absolute():
        raise HTTPException(status_code=400, detail="Absolute paths are not allowed")

    if ".." in rel.parts:
        raise HTTPException(status_code=400, detail="Parent traversal is not allowed")

    return rel



def _resolve_project_file(raw_path: str) -> tuple[Path, Path]:
    rel = _normalize_relative_path(raw_path)
    full = (PROJECT_ROOT / rel).resolve()

    try:
        rel_from_root = full.relative_to(PROJECT_ROOT)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Path escapes project root") from exc

    if not _is_allowed(rel_from_root):
        raise HTTPException(status_code=403, detail="Path is excluded")

    if not full.exists():
        raise HTTPException(status_code=404, detail="File not found")

    if not full.is_file():
        raise HTTPException(status_code=400, detail="Path is not a file")

    return full, rel_from_root



def _looks_text_file(path: Path) -> bool:
    if path.suffix.lower() in TEXT_SUFFIXES:
        return True
    return path.name in TEXT_NAMES



def _make_json_request(url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = None
    headers = {"Accept": "application/json"}

    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urlrequest.Request(url, data=body, headers=headers, method="POST" if body else "GET")

    try:
        with urlrequest.urlopen(req, timeout=OLLAMA_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urlerror.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise HTTPException(status_code=502, detail=f"Ollama HTTP error: {detail}") from exc
    except urlerror.URLError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Ollama is unavailable at {OLLAMA_BASE_URL}. Start Ollama and check the local server."
            ),
        ) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Ollama request timed out") from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="Invalid JSON returned by Ollama") from exc



def _fetch_ollama_tags() -> dict[str, Any]:
    return _make_json_request(f"{OLLAMA_BASE_URL}/api/tags")



def _pick_model(requested_model: str | None, tags_payload: dict[str, Any]) -> str:
    models = tags_payload.get("models") or []
    names = [item.get("name") for item in models if item.get("name")]

    if requested_model and requested_model.strip():
        return requested_model.strip()

    if DEFAULT_OLLAMA_MODEL:
        return DEFAULT_OLLAMA_MODEL

    if names:
        return names[0]

    raise HTTPException(status_code=400, detail="No Ollama models found. Pull a model first.")



def _read_reference_context(paths: list[str], selected_path: str) -> list[dict[str, str]]:
    context_items: list[dict[str, str]] = []
    seen: set[str] = set()

    for path in paths[:12]:
        if not path or path == selected_path or path in seen:
            continue
        seen.add(path)

        try:
            full_path, rel_path = _resolve_project_file(path)
        except HTTPException:
            continue

        if not _looks_text_file(full_path):
            continue

        try:
            size = full_path.stat().st_size
        except OSError:
            continue

        if size > MAX_AGENT_FILE_BYTES:
            continue

        raw = full_path.read_bytes()
        if b"\x00" in raw:
            continue

        text = raw.decode("utf-8", errors="replace")
        context_items.append(
            {
                "path": str(rel_path).replace("\\", "/"),
                "content": text[:20_000],
            }
        )

    return context_items



def _build_agent_prompt(goal: str, selected_path: str, selected_content: str, refs: list[dict[str, str]]) -> str:
    references = []
    for item in refs:
        references.append(
            f"FILE: {item['path']}\n<<<BEGIN_FILE>>>\n{item['content']}\n<<<END_FILE>>>"
        )

    references_block = "\n\n".join(references) if references else "No additional reference files provided."

    return f"""
You are Jarvis Local Dev Agent running through Ollama inside a desktop IDE.
Return STRICT JSON only. Do not wrap in markdown. Do not add commentary outside JSON.

Your job:
- Analyze the user goal.
- Focus on a SINGLE selected file.
- Produce a safe replacement for the selected file content when a direct patch is appropriate.
- If the goal cannot be solved safely within this one file, do not invent a partial rewrite. Explain why.

JSON schema:
{{
  "mode": "patch" or "explain",
  "summary": "one short sentence",
  "target_file": "relative/path",
  "why": ["bullet", "bullet"],
  "changes": ["bullet", "bullet"],
  "warnings": ["bullet"],
  "replacement_content": "full file content when mode=patch, otherwise empty string",
  "follow_up": ["bullet", "bullet"]
}}

Hard rules:
- target_file must exactly match the selected file path.
- replacement_content must contain the COMPLETE final file text.
- Keep existing behavior unless the goal requires changing it.
- Never output placeholder text.
- Never reference files you did not receive as if you read them.
- If uncertain, use mode=explain.

USER GOAL:
{goal}

SELECTED FILE PATH:
{selected_path}

SELECTED FILE CONTENT:
<<<BEGIN_SELECTED_FILE>>>
{selected_content}
<<<END_SELECTED_FILE>>>

REFERENCE FILES:
{references_block}
""".strip()



def _build_plan_prompt(goal: str, selected_path: str, selected_content: str) -> str:
    return f"""
You are Jarvis Local Planner.
Return STRICT JSON only. Do not wrap in markdown.

Schema:
{{
  "summary": "one sentence",
  "steps": ["step 1", "step 2", "step 3"],
  "risks": ["risk"],
  "target_file": "relative/path"
}}

USER GOAL:
{goal}

SELECTED FILE PATH:
{selected_path}

SELECTED FILE CONTENT:
<<<BEGIN_SELECTED_FILE>>>
{selected_content[:15000]}
<<<END_SELECTED_FILE>>>
""".strip()



def _call_ollama_generate(model: str, prompt: str) -> dict[str, Any]:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.2,
            "top_p": 0.9,
        },
    }
    response = _make_json_request(f"{OLLAMA_BASE_URL}/api/generate", payload)
    raw_text = response.get("response", "")

    if not raw_text:
        raise HTTPException(status_code=502, detail="Ollama returned an empty response")

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail="Ollama did not return valid JSON in the response body",
        ) from exc

    parsed["_ollama"] = {
        "model": response.get("model") or model,
        "done": response.get("done"),
        "total_duration": response.get("total_duration"),
        "eval_count": response.get("eval_count"),
    }
    return parsed


@router.get("/status")
def project_brain_status():
    return {
        "status": "ok",
        "project_root": str(PROJECT_ROOT),
        "excluded_parts": sorted(EXCLUDED_PARTS),
        "max_read_bytes": MAX_READ_BYTES,
        "ollama_base_url": OLLAMA_BASE_URL,
    }


@router.get("/snapshot")
def project_snapshot():
    files: list[dict] = []

    for file_path in PROJECT_ROOT.rglob("*"):
        if not file_path.is_file():
            continue

        try:
            rel = file_path.relative_to(PROJECT_ROOT)
        except Exception:
            continue

        if not _is_allowed(rel):
            continue

        try:
            stat = file_path.stat()
        except OSError:
            continue

        files.append(
            {
                "path": str(rel).replace("\\", "/"),
                "name": file_path.name,
                "suffix": file_path.suffix.lower(),
                "size": stat.st_size,
            }
        )

    files.sort(key=lambda item: item["path"])

    return {
        "status": "ok",
        "project_root": str(PROJECT_ROOT),
        "files": files,
        "files_count": len(files),
    }


@router.get("/file")
def read_project_file(path: str = Query(..., min_length=1)):
    full_path, rel_path = _resolve_project_file(path)

    if not _looks_text_file(full_path):
        raise HTTPException(
            status_code=415,
            detail="Only text-like source files are readable from this endpoint",
        )

    size = full_path.stat().st_size
    if size > MAX_READ_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File is too large to open in IDE view ({size} bytes)",
        )

    raw = full_path.read_bytes()

    if b"\x00" in raw:
        raise HTTPException(status_code=415, detail="Binary files are not supported")

    try:
        content = raw.decode("utf-8")
        encoding = "utf-8"
    except UnicodeDecodeError:
        content = raw.decode("utf-8", errors="replace")
        encoding = "utf-8/replace"

    sha256 = hashlib.sha256(raw).hexdigest()

    return {
        "status": "ok",
        "path": str(rel_path).replace("\\", "/"),
        "name": full_path.name,
        "suffix": full_path.suffix.lower(),
        "size": size,
        "encoding": encoding,
        "sha256": sha256,
        "content": content,
    }


@router.get("/agent/ollama/status")
def ollama_status():
    tags = _fetch_ollama_tags()
    models = tags.get("models") or []
    model_names = [item.get("name") for item in models if item.get("name")]

    return {
        "status": "ok",
        "provider": "ollama",
        "base_url": OLLAMA_BASE_URL,
        "models": model_names,
        "default_model": DEFAULT_OLLAMA_MODEL or (model_names[0] if model_names else ""),
        "model_count": len(model_names),
    }


@router.post("/agent/ollama/plan")
def ollama_plan(request: LocalAgentPlanRequest):
    selected_full, selected_rel = _resolve_project_file(request.selected_path)
    if not _looks_text_file(selected_full):
        raise HTTPException(status_code=415, detail="Selected file is not text-like")

    tags = _fetch_ollama_tags()
    model = _pick_model(request.model, tags)
    prompt = _build_plan_prompt(request.goal, str(selected_rel).replace("\\", "/"), request.selected_content)
    parsed = _call_ollama_generate(model, prompt)

    return {
        "status": "ok",
        "provider": "ollama",
        "model": parsed.get("_ollama", {}).get("model", model),
        "summary": parsed.get("summary", ""),
        "steps": parsed.get("steps") or [],
        "risks": parsed.get("risks") or [],
        "target_file": parsed.get("target_file") or str(selected_rel).replace("\\", "/"),
    }


@router.post("/agent/ollama/run")
def ollama_run(request: LocalAgentRunRequest):
    selected_full, selected_rel = _resolve_project_file(request.selected_path)
    if not _looks_text_file(selected_full):
        raise HTTPException(status_code=415, detail="Selected file is not text-like")

    refs = _read_reference_context(request.project_files, str(selected_rel).replace("\\", "/"))
    tags = _fetch_ollama_tags()
    model = _pick_model(request.model, tags)
    prompt = _build_agent_prompt(
        request.goal,
        str(selected_rel).replace("\\", "/"),
        request.selected_content,
        refs,
    )
    parsed = _call_ollama_generate(model, prompt)

    target_file = parsed.get("target_file") or str(selected_rel).replace("\\", "/")
    if target_file != str(selected_rel).replace("\\", "/"):
        raise HTTPException(
            status_code=502,
            detail="Agent returned a target file that does not match the selected file",
        )

    mode = parsed.get("mode") or "explain"
    replacement_content = parsed.get("replacement_content") or ""
    changed = bool(mode == "patch" and replacement_content and replacement_content != request.selected_content)

    return {
        "status": "ok",
        "provider": "ollama",
        "model": parsed.get("_ollama", {}).get("model", model),
        "mode": mode,
        "changed": changed,
        "summary": parsed.get("summary", ""),
        "why": parsed.get("why") or [],
        "changes": parsed.get("changes") or [],
        "warnings": parsed.get("warnings") or [],
        "follow_up": parsed.get("follow_up") or [],
        "target_file": target_file,
        "replacement_content": replacement_content,
        "reference_files_used": [item["path"] for item in refs],
    }
