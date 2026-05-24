from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..domain.common import utc_now_iso
from ..storage.constants import INGESTION_SPECS_FILENAME
from ..storage.io import read_json, write_json
from .importers import stable_payload_hash


def ingestion_specs_path(project_dir: Path) -> Path:
    return project_dir / INGESTION_SPECS_FILENAME


def normalize_ingestion_spec_payload(payload: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    current = existing if isinstance(existing, dict) else {}
    next_payload = payload if isinstance(payload, dict) else {}
    timestamp = utc_now_iso()
    normalized_payload = {
        "source_profile": str(next_payload.get("source_profile") or current.get("source_profile") or "generic"),
        "field_mappings": [deepcopy(item) for item in next_payload.get("field_mappings", current.get("field_mappings", [])) if isinstance(item, dict)],
        "text_build": deepcopy(next_payload.get("text_build") if isinstance(next_payload.get("text_build"), dict) else current.get("text_build", {})),
        "dedupe_rules": deepcopy(next_payload.get("dedupe_rules") if isinstance(next_payload.get("dedupe_rules"), dict) else current.get("dedupe_rules", {})),
        "metadata_normalization_rules": deepcopy(
            next_payload.get("metadata_normalization_rules")
            if isinstance(next_payload.get("metadata_normalization_rules"), dict)
            else current.get("metadata_normalization_rules", {})
        ),
    }
    return {
        "id": str(current.get("id") or current.get("spec_id") or next_payload.get("id") or next_payload.get("spec_id") or f"ingestion-{uuid4().hex[:12]}"),
        "name": str(next_payload.get("name") or current.get("name") or "未命名导入规格"),
        **normalized_payload,
        "spec_hash": stable_payload_hash(normalized_payload),
        "created_at": str(current.get("created_at") or timestamp),
        "updated_at": timestamp,
    }


def persist_ingestion_specs(project_dir: Path, manifest: dict[str, Any]) -> None:
    write_json(ingestion_specs_path(project_dir), manifest.get("ingestion_specs", []))


def save_ingestion_spec(project_dir: Path, manifest: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    spec_id = str(payload.get("id") or payload.get("spec_id") or "")
    next_specs: list[dict[str, Any]] = []
    saved: dict[str, Any] | None = None
    updated_existing = False

    for item in manifest.get("ingestion_specs", []):
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id") or item.get("spec_id") or "")
        if spec_id and item_id == spec_id:
            saved = normalize_ingestion_spec_payload(payload, existing=item)
            next_specs.append(saved)
            updated_existing = True
        else:
            next_specs.append(deepcopy(item))

    if not updated_existing:
        saved = normalize_ingestion_spec_payload(payload)
        next_specs.append(saved)

    manifest["ingestion_specs"] = next_specs
    persist_ingestion_specs(project_dir, manifest)
    return saved if saved is not None else {}


def list_ingestion_specs(project_dir: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    path = ingestion_specs_path(project_dir)
    if path.exists():
        payload = read_json(path)
        if isinstance(payload, list):
            manifest["ingestion_specs"] = [deepcopy(item) for item in payload if isinstance(item, dict)]
            return manifest["ingestion_specs"]
    return [deepcopy(item) for item in manifest.get("ingestion_specs", []) if isinstance(item, dict)]
