from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..domain.common import utc_now_iso
from .constants import CORPUS_VIEWS_FILENAME
from .io import write_json


def normalize_corpus_view_payload(payload: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    current = existing if isinstance(existing, dict) else {}
    next_payload = payload if isinstance(payload, dict) else {}
    timestamp = utc_now_iso()
    view_id = str(current.get("id") or current.get("view_id") or next_payload.get("id") or next_payload.get("view_id") or f"view-{uuid4().hex[:12]}")
    return {
        "id": view_id,
        "name": str(next_payload.get("name") or current.get("name") or "未命名视图"),
        "resource_ids": [str(item) for item in next_payload.get("resource_ids", current.get("resource_ids", [])) if str(item)],
        "filter_spec": deepcopy(next_payload.get("filter_spec") if isinstance(next_payload.get("filter_spec"), dict) else current.get("filter_spec", {})),
        "doc_ids": [str(item) for item in next_payload.get("doc_ids", current.get("doc_ids", [])) if str(item)],
        "created_at": str(current.get("created_at") or timestamp),
        "updated_at": timestamp,
    }


def persist_corpus_views(project_dir: Path, manifest: dict[str, Any]) -> None:
    write_json(project_dir / CORPUS_VIEWS_FILENAME, manifest.get("corpus_views", []))


def create_corpus_view(project_dir: Path, manifest: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    created = normalize_corpus_view_payload(payload)
    manifest["corpus_views"] = [*manifest.get("corpus_views", []), created]
    persist_corpus_views(project_dir, manifest)
    return created


def update_corpus_view(project_dir: Path, manifest: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    view_id = str(payload.get("view_id") or payload.get("id") or "")
    if not view_id:
        raise ValueError("Missing corpus view id")

    next_views: list[dict[str, Any]] = []
    updated: dict[str, Any] | None = None
    for item in manifest.get("corpus_views", []):
        if not isinstance(item, dict):
            continue
        if str(item.get("id") or item.get("view_id") or "") != view_id:
            next_views.append(deepcopy(item))
            continue
        updated = normalize_corpus_view_payload(payload, existing=item)
        next_views.append(updated)

    if updated is None:
        raise ValueError(f"Corpus view {view_id} not found")

    manifest["corpus_views"] = next_views
    persist_corpus_views(project_dir, manifest)
    return updated


def delete_corpus_view(project_dir: Path, manifest: dict[str, Any], view_id: str) -> dict[str, Any]:
    removed: dict[str, Any] | None = None
    next_views: list[dict[str, Any]] = []
    for item in manifest.get("corpus_views", []):
        if not isinstance(item, dict):
            continue
        if removed is None and str(item.get("id") or item.get("view_id") or "") == str(view_id):
            removed = deepcopy(item)
            continue
        next_views.append(deepcopy(item))

    if removed is None:
        raise ValueError(f"Corpus view {view_id} not found")

    manifest["corpus_views"] = next_views
    persist_corpus_views(project_dir, manifest)
    return removed


def _document_matches_filter(document: dict[str, Any], field: str, expected: Any) -> bool:
    value = document.get(field)
    if value in (None, "") and isinstance(document.get("extra_metadata"), dict):
        value = document["extra_metadata"].get(field)

    if isinstance(expected, dict):
        operator = str(expected.get("operator") or "eq")
        values = expected.get("values", [])
        normalized_values = [str(item) for item in values] if isinstance(values, list) else [str(values)]
        if operator == "in":
            return str(value) in normalized_values
        if operator == "not_in":
            return str(value) not in normalized_values
        if operator == "contains":
            return any(item in str(value or "") for item in normalized_values)
        return str(value) == normalized_values[0]

    if isinstance(expected, list):
        return str(value) in {str(item) for item in expected}

    return str(value) == str(expected)


def resolve_corpus_view(manifest: dict[str, Any], corpus: list[dict[str, Any]], view_id: str) -> list[dict[str, Any]]:
    view = next(
        (
            item
            for item in manifest.get("corpus_views", [])
            if isinstance(item, dict) and str(item.get("id") or item.get("view_id") or "") == str(view_id)
        ),
        None,
    )
    if view is None:
        raise ValueError(f"Corpus view {view_id} not found")

    resource_ids = {str(item) for item in view.get("resource_ids", []) if str(item)}
    doc_ids = {str(item) for item in view.get("doc_ids", []) if str(item)}
    allowed_source_files: set[str] = set()
    if resource_ids:
        for resource in manifest.get("corpus_resources", []):
            if not isinstance(resource, dict) or str(resource.get("id") or "") not in resource_ids:
                continue
            allowed_source_files.update(str(item) for item in resource.get("source_files", []) if str(item))

    resolved: list[dict[str, Any]] = []
    for document in corpus:
        if allowed_source_files:
            extra_metadata = document.get("extra_metadata") if isinstance(document.get("extra_metadata"), dict) else {}
            source_relative_path = str(extra_metadata.get("_source_relative_path") or "")
            source_file_name = str(extra_metadata.get("_source_file_name") or "")
            if source_relative_path not in allowed_source_files and source_file_name not in allowed_source_files:
                continue
        if doc_ids:
            document_id = str(document.get("doc_id") or document.get("id") or "")
            if document_id not in doc_ids:
                continue
        if not all(_document_matches_filter(document, field, expected) for field, expected in view.get("filter_spec", {}).items()):
            continue
        resolved.append(document)

    return resolved

