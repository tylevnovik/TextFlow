from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from .database import (
    initialize_project_database,
    load_artifact_payload as db_load_artifact_payload,
    load_artifact_preview as db_load_artifact_preview,
    write_artifact_payload as db_write_artifact_payload,
)
from .projects import PROJECT_DATABASE_FILENAME


def _json_ready(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(item) for item in value]
    if hasattr(value, "tolist"):
        try:
            return value.tolist()
        except Exception:
            pass
    return str(value)


def _artifact_paths(project_dir: Path, run_id: str, artifact_id: str) -> tuple[Path, Path]:
    artifact_dir = project_dir / "runs" / run_id / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return artifact_dir / f"{artifact_id}.json.gz", artifact_dir / f"{artifact_id}.preview.json"


def _relative_path(project_dir: Path, path: Path) -> str:
    return path.relative_to(project_dir).as_posix()


def _preview_rows(payload: Any, limit: int) -> list[Any]:
    if isinstance(payload, list):
        return [_json_ready(item) for item in payload[:limit]]
    if isinstance(payload, dict):
        return [_json_ready(payload)]
    if payload is None:
        return []
    return [_json_ready(payload)]


def write_artifact(project_dir: Path, run_id: str, node_id: str, kind: str, payload: Any) -> dict[str, Any]:
    db_path = project_dir / PROJECT_DATABASE_FILENAME
    if db_path.exists():
        db = initialize_project_database(db_path)
        return db_write_artifact_payload(db, run_id, node_id, kind, payload)

    artifact_id = f"artifact-{uuid4().hex[:12]}"
    payload_path, preview_path = _artifact_paths(project_dir, run_id, artifact_id)
    normalized_payload = _json_ready(payload)
    row_count = len(normalized_payload) if isinstance(normalized_payload, list) else (1 if normalized_payload not in (None, "") else 0)
    preview_rows = _preview_rows(normalized_payload, 50)
    preview_payload = {
        "artifact_id": artifact_id,
        "run_id": run_id,
        "node_id": node_id,
        "kind": kind,
        "row_count": row_count,
        "preview_rows": len(preview_rows),
        "rows": preview_rows,
    }

    with gzip.open(payload_path, "wt", encoding="utf-8", compresslevel=6) as handle:
        handle.write(json.dumps(normalized_payload, ensure_ascii=False, separators=(",", ":")))
    preview_path.write_text(json.dumps(preview_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "artifact_id": artifact_id,
        "run_id": run_id,
        "node_id": node_id,
        "kind": kind,
        "path": _relative_path(project_dir, payload_path),
        "preview_path": _relative_path(project_dir, preview_path),
        "row_count": row_count,
        "preview_rows": len(preview_rows),
    }


def _find_artifact_path(project_dir: Path, artifact_id: str, *suffixes: str) -> Path:
    matches: list[Path] = []
    for suffix in suffixes:
        matches.extend(project_dir.glob(f"runs/*/artifacts/{artifact_id}{suffix}"))
    if not matches:
        raise ValueError(f"Artifact {artifact_id} not found")
    return matches[0]


def load_artifact_preview(project_dir: Path, artifact_id: str, limit: int = 50) -> dict[str, Any]:
    db_path = project_dir / PROJECT_DATABASE_FILENAME
    if db_path.exists():
        db = initialize_project_database(db_path)
        try:
            return db_load_artifact_preview(db, artifact_id, limit)
        except ValueError:
            pass
    preview_path = _find_artifact_path(project_dir, artifact_id, ".preview.json")
    preview = json.loads(preview_path.read_text(encoding="utf-8"))
    rows = preview.get("rows", [])
    if isinstance(rows, list) and limit >= 0:
        preview["rows"] = rows[:limit]
        preview["preview_rows"] = len(preview["rows"])
    return preview


def load_artifact_payload(project_dir: Path, artifact_id: str) -> Any:
    db_path = project_dir / PROJECT_DATABASE_FILENAME
    if db_path.exists():
        db = initialize_project_database(db_path)
        try:
            return db_load_artifact_payload(db, artifact_id)
        except ValueError:
            pass
    payload_path = _find_artifact_path(project_dir, artifact_id, ".json.gz", ".json")
    if payload_path.name.endswith(".preview.json"):
        raise ValueError(f"Artifact payload {artifact_id} not found")
    if payload_path.name.endswith(".json.gz"):
        with gzip.open(payload_path, "rt", encoding="utf-8") as handle:
            return json.loads(handle.read())
    return json.loads(payload_path.read_text(encoding="utf-8"))

