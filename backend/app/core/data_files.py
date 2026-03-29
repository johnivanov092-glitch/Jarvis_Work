from __future__ import annotations

import json
import os
import shutil
import sqlite3
from pathlib import Path
from typing import Iterable

from app.core.config import BACKEND_DIR, DATA_DIR as CONFIG_DATA_DIR


DATA_DIR = Path(os.getenv("ELIRA_DATA_DIR", str(CONFIG_DATA_DIR))).resolve()
LEGACY_DATA_DIR = Path(
    os.getenv("ELIRA_LEGACY_DATA_DIR", str(BACKEND_DIR / "data"))
).resolve()
_SKIP_LEGACY_ADOPTION = os.getenv("ELIRA_SKIP_LEGACY_ADOPTION") == "1"


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def data_file(name: str) -> Path:
    _ensure_data_dir()
    return DATA_DIR / name


def _legacy_file(name: str) -> Path:
    return LEGACY_DATA_DIR / name


def _copy_sidecar_files(src: Path, dst: Path) -> None:
    for suffix in (".wal", ".shm"):
        src_sidecar = Path(f"{src}{suffix}")
        dst_sidecar = Path(f"{dst}{suffix}")
        if src_sidecar.exists() and not dst_sidecar.exists():
            shutil.copy2(src_sidecar, dst_sidecar)


def _backup_existing_file(path: Path) -> None:
    if not path.exists():
        return
    backup = path.with_suffix(f"{path.suffix}.pre-adopt.bak")
    if not backup.exists():
        shutil.copy2(path, backup)


def _sqlite_total_rows(path: Path, tables: Iterable[str]) -> int:
    if not path.exists():
        return 0
    try:
        conn = sqlite3.connect(path)
        total = 0
        for table in tables:
            try:
                total += int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            except sqlite3.Error:
                continue
        conn.close()
        return total
    except sqlite3.Error:
        return 0


def _json_item_count(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return 0

    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        return len(payload)
    return 0


def sqlite_data_file(name: str, key_tables: Iterable[str]) -> Path:
    target = data_file(name)
    legacy = _legacy_file(name)

    if _SKIP_LEGACY_ADOPTION or not legacy.exists() or legacy == target:
        return target

    if _sqlite_total_rows(target, key_tables) == 0 and _sqlite_total_rows(legacy, key_tables) > 0:
        _backup_existing_file(target)
        shutil.copy2(legacy, target)
        _copy_sidecar_files(legacy, target)

    return target


def json_data_file(name: str) -> Path:
    target = data_file(name)
    legacy = _legacy_file(name)

    if _SKIP_LEGACY_ADOPTION or not legacy.exists() or legacy == target:
        return target

    if _json_item_count(target) == 0 and _json_item_count(legacy) > 0:
        _backup_existing_file(target)
        shutil.copy2(legacy, target)

    return target
