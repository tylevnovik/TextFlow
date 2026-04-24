from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .artifact_store import load_artifact_payload, load_artifact_preview
from .dag_runtime import run_project_workflow_native

DEFAULT_WORKFLOW_STEP_ORDER = [
    "ingestion",
    "cleaning",
    "normalization",
    "tokenization",
    "dictionary_application",
    "filtering",
    "analysis",
    "export",
]


def enabled_workflow_step_order(runtime_profile: dict[str, Any]) -> list[str]:
    enabled = set(runtime_profile.get("enabled_steps") or DEFAULT_WORKFLOW_STEP_ORDER)
    requested_order = runtime_profile.get("execution_order") or DEFAULT_WORKFLOW_STEP_ORDER
    ordered = [step for step in requested_order if step in enabled and step in DEFAULT_WORKFLOW_STEP_ORDER]
    for step in DEFAULT_WORKFLOW_STEP_ORDER:
        if step in enabled and step not in ordered:
            ordered.append(step)
    return ordered


def workflow_step_enabled(runtime_profile: dict[str, Any], step: str) -> bool:
    return step in set(enabled_workflow_step_order(runtime_profile))


def apply_workflow_variant_overrides(
    workflow_definition: dict[str, Any],
    node_overrides: dict[str, Any] | None,
) -> dict[str, Any]:
    next_workflow = deepcopy(workflow_definition)
    overrides = node_overrides if isinstance(node_overrides, dict) else {}
    for node in next_workflow.get("nodes", []):
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("node_id") or "")
        override = overrides.get(node_id)
        if not isinstance(override, dict):
            continue
        node["config"] = {
            **(node.get("config") if isinstance(node.get("config"), dict) else {}),
            **deepcopy(override),
        }
    return next_workflow


def run_project_workflow_bridge(
    project_dir: Path,
    manifest: dict[str, Any],
    corpus: list[dict[str, Any]],
    progress_callback: Any = None,
    run_options: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    return run_project_workflow_native(project_dir, manifest, corpus, progress_callback, run_options=run_options)


def run_project_workflow(
    project_dir: Path,
    manifest: dict[str, Any],
    corpus: list[dict[str, Any]],
    progress_callback: Any = None,
    run_options: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    return run_project_workflow_native(project_dir, manifest, corpus, progress_callback, run_options=run_options)


def load_workflow_artifact_preview(project_dir: Path, artifact_id: str, limit: int = 50) -> dict[str, Any]:
    return load_artifact_preview(project_dir, artifact_id, limit=limit)


def load_workflow_artifact_payload(project_dir: Path, artifact_id: str) -> Any:
    return load_artifact_payload(project_dir, artifact_id)
