from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from ..domain.common import utc_now_iso
from .io import read_json, write_json
from .workspace import import_templates_root, project_templates_root

def template_path(root: Path, template_id: str) -> Path:
    return root / f"{template_id}.json"


def list_templates(root: Path) -> list[dict[str, Any]]:
    templates: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        payload = read_json(path)
        if isinstance(payload, dict):
            templates.append(payload)
    templates.sort(key=lambda item: (item.get("updated_at", ""), item.get("name", "")), reverse=True)
    return templates


def load_template(root: Path, template_id: str) -> dict[str, Any]:
    path = template_path(root, template_id)
    if not path.exists():
        raise ValueError(f"Template {template_id} not found")
    payload = read_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid template payload: {path}")
    return payload


def save_template(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    record = deepcopy(payload)
    timestamp = utc_now_iso()
    record.setdefault("created_at", timestamp)
    record["updated_at"] = timestamp
    write_json(template_path(root, str(record["id"])), record)
    return record

def save_project_template(
    manifest: dict[str, Any],
    name: str | None = None,
    description: str | None = None,
    template_id: str | None = None,
) -> dict[str, Any]:
    from .projects import build_project_template

    payload = build_project_template(manifest, name=name, description=description, template_id=template_id)
    return save_template(project_templates_root(), payload)


def list_project_templates() -> list[dict[str, Any]]:
    return list_templates(project_templates_root())


def load_project_template(template_id: str) -> dict[str, Any]:
    return load_template(project_templates_root(), template_id)


def save_import_template_record(
    import_template: dict[str, Any],
    name: str | None = None,
    description: str | None = None,
    template_id: str | None = None,
) -> dict[str, Any]:
    from .projects import uuid_suffix

    payload = deepcopy(import_template)
    payload["id"] = template_id or payload.get("id") or f"import-template-{uuid_suffix()}"
    if name:
        payload["name"] = name
    if description is not None:
        payload["description"] = description
    return save_template(import_templates_root(), payload)


def list_import_templates() -> list[dict[str, Any]]:
    return list_templates(import_templates_root())


def load_import_template(template_id: str) -> dict[str, Any]:
    return load_template(import_templates_root(), template_id)
