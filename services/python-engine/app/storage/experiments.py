from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4

from ..domain.common import utc_now_iso


def _experiment_id(payload: dict[str, Any], existing: dict[str, Any] | None = None) -> str:
    current = existing if isinstance(existing, dict) else {}
    return str(
        current.get("experiment_id")
        or current.get("id")
        or payload.get("experiment_id")
        or payload.get("id")
        or f"exp-{uuid4().hex[:12]}"
    )


def normalize_variant_matrix(raw_variants: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_variants, list):
        return []

    variants: list[dict[str, Any]] = []
    for index, item in enumerate(raw_variants):
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or f"variant-{index + 1}")
        node_overrides = item.get("node_overrides") if isinstance(item.get("node_overrides"), dict) else {}
        variants.append(
            {
                **deepcopy(item),
                "label": label,
                "node_overrides": deepcopy(node_overrides),
            }
        )
    return variants


def normalize_experiment_spec(payload: dict[str, Any], manifest: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    current = existing if isinstance(existing, dict) else {}
    next_payload = payload if isinstance(payload, dict) else {}
    timestamp = utc_now_iso()
    return {
        "experiment_id": _experiment_id(next_payload, current),
        "name": str(next_payload.get("name") or current.get("name") or "未命名实验"),
        "workflow_id": str(
            next_payload.get("workflow_id")
            or current.get("workflow_id")
            or manifest.get("active_workflow_id")
            or "wf-default"
        ),
        "variant_matrix": normalize_variant_matrix(
            next_payload.get("variant_matrix", current.get("variant_matrix", []))
        ),
        "created_at": str(current.get("created_at") or timestamp),
        "updated_at": timestamp,
    }


def save_experiment_spec(manifest: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    experiment_id = str(payload.get("experiment_id") or payload.get("id") or "")
    next_specs: list[dict[str, Any]] = []
    saved: dict[str, Any] | None = None

    for item in manifest.get("experiment_specs", []):
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("experiment_id") or item.get("id") or "")
        if experiment_id and item_id == experiment_id:
            saved = normalize_experiment_spec(payload, manifest, existing=item)
            next_specs.append(saved)
        else:
            next_specs.append(deepcopy(item))

    if saved is None:
        saved = normalize_experiment_spec(payload, manifest)
        next_specs.append(saved)

    manifest["experiment_specs"] = next_specs
    manifest["updated_at"] = utc_now_iso()
    return saved


def list_experiment_specs(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return [deepcopy(item) for item in manifest.get("experiment_specs", []) if isinstance(item, dict)]
