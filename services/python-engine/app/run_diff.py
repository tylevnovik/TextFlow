from __future__ import annotations

from copy import deepcopy
from typing import Any


def _find_run(manifest: dict[str, Any], run_id: str) -> dict[str, Any]:
    for run in manifest.get("run_history", []):
        if isinstance(run, dict) and str(run.get("run_id") or "") == str(run_id):
            return run
    raise ValueError(f"Run {run_id} not found")


def _number_metric(left: dict[str, Any], right: dict[str, Any], key: str) -> dict[str, int | float]:
    left_value = left.get(key)
    right_value = right.get(key)
    left_number = left_value if isinstance(left_value, (int, float)) else 0
    right_number = right_value if isinstance(right_value, (int, float)) else 0
    return {
        "left": left_number,
        "right": right_number,
        "delta": right_number - left_number,
    }


def _artifact_step(artifact: dict[str, Any]) -> str:
    return str(
        artifact.get("step")
        or artifact.get("result_key")
        or artifact.get("kind")
        or artifact.get("node_id")
        or "artifact"
    )


def _artifact_record_count(artifact: dict[str, Any] | None) -> int:
    if not artifact:
        return 0
    for key in ("record_count", "row_count", "preview_rows"):
        value = artifact.get(key)
        if isinstance(value, int):
            return value
    return 0


def _artifact_files(artifact: dict[str, Any] | None) -> list[str]:
    if not artifact:
        return []
    files = artifact.get("output_files")
    if isinstance(files, list):
        return [str(item) for item in files if str(item)]
    relative_path = artifact.get("relative_path")
    return [str(relative_path)] if relative_path else []


def _artifact_by_step(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    by_step: dict[str, dict[str, Any]] = {}
    for artifact in run.get("artifacts", []):
        if isinstance(artifact, dict):
            by_step[_artifact_step(artifact)] = artifact
    return by_step


def _changed_top_terms(left: dict[str, Any], right: dict[str, Any], key: str) -> dict[str, list[str]]:
    left_terms = {
        str(item.get("term") or item.get("keyword") or item.get("label") or "")
        for item in left.get(key, [])
        if isinstance(item, dict)
    }
    right_terms = {
        str(item.get("term") or item.get("keyword") or item.get("label") or "")
        for item in right.get(key, [])
        if isinstance(item, dict)
    }
    left_terms.discard("")
    right_terms.discard("")
    return {
        "added": sorted(right_terms - left_terms)[:25],
        "removed": sorted(left_terms - right_terms)[:25],
    }


def compare_runs(manifest: dict[str, Any], left_run_id: str, right_run_id: str) -> dict[str, Any]:
    left = _find_run(manifest, left_run_id)
    right = _find_run(manifest, right_run_id)

    left_artifacts = _artifact_by_step(left)
    right_artifacts = _artifact_by_step(right)
    artifact_diffs: list[dict[str, Any]] = []
    for step in sorted(set(left_artifacts) | set(right_artifacts)):
        left_artifact = left_artifacts.get(step)
        right_artifact = right_artifacts.get(step)
        left_count = _artifact_record_count(left_artifact)
        right_count = _artifact_record_count(right_artifact)
        left_files = set(_artifact_files(left_artifact))
        right_files = set(_artifact_files(right_artifact))
        artifact_diffs.append({
            "step": step,
            "left_record_count": left_count,
            "right_record_count": right_count,
            "record_count_delta": right_count - left_count,
            "added_files": sorted(right_files - left_files),
            "removed_files": sorted(left_files - right_files),
            "left": deepcopy(left_artifact),
            "right": deepcopy(right_artifact),
        })

    result_bundle = manifest.get("results") if isinstance(manifest.get("results"), dict) else {}
    metrics = {
        "processed_document_count": _number_metric(left, right, "processed_document_count"),
        "warning_count": {
            "left": len(left.get("warnings", []) if isinstance(left.get("warnings"), list) else []),
            "right": len(right.get("warnings", []) if isinstance(right.get("warnings"), list) else []),
        },
        "error_count": {
            "left": len(left.get("errors", []) if isinstance(left.get("errors"), list) else []),
            "right": len(right.get("errors", []) if isinstance(right.get("errors"), list) else []),
        },
        "artifact_count": {
            "left": len(left_artifacts),
            "right": len(right_artifacts),
            "delta": len(right_artifacts) - len(left_artifacts),
        },
    }
    metrics["warning_count"]["delta"] = metrics["warning_count"]["right"] - metrics["warning_count"]["left"]
    metrics["error_count"]["delta"] = metrics["error_count"]["right"] - metrics["error_count"]["left"]

    total_delta = sum(item["record_count_delta"] for item in artifact_diffs)
    return {
        "left_run_id": left_run_id,
        "right_run_id": right_run_id,
        "metrics": metrics,
        "runtime_profile_diff": {
            "recipe": {"left": left.get("recipe_id"), "right": right.get("recipe_id")},
            "output_bundle": {"left": left.get("output_bundle_id"), "right": right.get("output_bundle_id")},
            "workflow_hash": {"left": left.get("workflow_hash"), "right": right.get("workflow_hash")},
        },
        "artifact_diffs": artifact_diffs,
        "top_term_diff": _changed_top_terms(result_bundle, result_bundle, "frequency_table"),
        "top_keyword_diff": _changed_top_terms(result_bundle, result_bundle, "keyword_result"),
        "cluster_count_diff": _number_metric(
            {"cluster_count": len(result_bundle.get("keyword_cluster_result", []) if isinstance(result_bundle.get("keyword_cluster_result"), list) else [])},
            {"cluster_count": len(result_bundle.get("keyword_cluster_result", []) if isinstance(result_bundle.get("keyword_cluster_result"), list) else [])},
            "cluster_count",
        ),
        "summary": f"Compared {left_run_id} vs {right_run_id}: artifact row delta {total_delta}, document delta {metrics['processed_document_count']['delta']}.",
    }
