from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from ..domain.common import utc_now_iso
from ..storage.experiments import normalize_variant_matrix
from .runner import apply_workflow_variant_overrides, run_project_workflow


def _find_experiment_spec(manifest: dict[str, Any], experiment_id: str) -> dict[str, Any]:
    for item in manifest.get("experiment_specs", []):
        if isinstance(item, dict) and str(item.get("experiment_id") or item.get("id") or "") == experiment_id:
            return item
    raise ValueError(f"Experiment {experiment_id} not found")


def _find_workflow_index(manifest: dict[str, Any], workflow_id: str) -> int:
    for index, workflow in enumerate(manifest.get("workflow_definitions", [])):
        if isinstance(workflow, dict) and str(workflow.get("workflow_id") or "") == workflow_id:
            return index
    raise ValueError(f"Workflow {workflow_id} not found")


def _manifest_for_variant(manifest: dict[str, Any], experiment: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
    workflow_id = str(experiment["workflow_id"])
    variant_manifest = deepcopy(manifest)
    workflow_index = _find_workflow_index(variant_manifest, workflow_id)
    workflow = variant_manifest["workflow_definitions"][workflow_index]
    variant_manifest["workflow_definitions"][workflow_index] = apply_workflow_variant_overrides(
        workflow,
        variant.get("node_overrides") if isinstance(variant.get("node_overrides"), dict) else {},
    )
    variant_manifest["active_workflow_id"] = workflow_id
    return variant_manifest


def _merge_run_artifacts(target_manifest: dict[str, Any], source_manifest: dict[str, Any], run_id: str) -> None:
    existing = [
        deepcopy(item)
        for item in target_manifest.get("artifact_records", [])
        if isinstance(item, dict) and str(item.get("run_id") or "") != run_id
    ]
    incoming = [
        deepcopy(item)
        for item in source_manifest.get("artifact_records", [])
        if isinstance(item, dict) and str(item.get("run_id") or "") == run_id
    ]
    target_manifest["artifact_records"] = [*existing, *incoming]


def run_experiment_matrix(
    project_dir: Path,
    manifest: dict[str, Any],
    corpus: list[dict[str, Any]],
    experiment_id: str,
    progress_callback: Any = None,
) -> dict[str, Any]:
    experiment = _find_experiment_spec(manifest, experiment_id)
    variants = normalize_variant_matrix(experiment.get("variant_matrix"))
    if not variants:
        raise ValueError(f"Experiment {experiment_id} has no variants")

    executed_runs: list[dict[str, Any]] = []
    next_corpus = corpus
    manifest_run_ids = {
        str(item.get("run_id") or "")
        for item in manifest.get("run_history", [])
        if isinstance(item, dict)
    }

    for index, variant in enumerate(variants):
        variant_manifest = _manifest_for_variant(manifest, experiment, variant)
        variant_manifest["run_history"] = [
            deepcopy(item)
            for item in manifest.get("run_history", [])
            if isinstance(item, dict)
        ]
        variant_manifest["artifact_records"] = [
            deepcopy(item)
            for item in manifest.get("artifact_records", [])
            if isinstance(item, dict)
        ]

        variant_manifest, variant_corpus, run_record = run_project_workflow(
            project_dir,
            variant_manifest,
            deepcopy(next_corpus),
            progress_callback=progress_callback,
        )
        run_record.update({
            "experiment_id": experiment["experiment_id"],
            "experiment_name": experiment["name"],
            "variant_label": variant["label"],
            "variant_index": index,
            "variant_overrides": deepcopy(variant),
        })

        for item in variant_manifest.get("run_history", []):
            if isinstance(item, dict) and str(item.get("run_id") or "") == str(run_record.get("run_id") or ""):
                item.update(run_record)

        run_id = str(run_record.get("run_id") or "")
        if run_id and run_id not in manifest_run_ids:
            manifest.setdefault("run_history", []).append(deepcopy(run_record))
            manifest_run_ids.add(run_id)
        elif run_id:
            manifest["run_history"] = [
                deepcopy(run_record) if isinstance(item, dict) and str(item.get("run_id") or "") == run_id else item
                for item in manifest.get("run_history", [])
            ]
        _merge_run_artifacts(manifest, variant_manifest, run_id)
        manifest["results"] = deepcopy(variant_manifest.get("results", manifest.get("results", {})))
        manifest["updated_at"] = utc_now_iso()
        next_corpus = variant_corpus
        executed_runs.append(deepcopy(run_record))

    return {
        "experiment": deepcopy(experiment),
        "runs": executed_runs,
        "project": manifest,
        "corpus": next_corpus,
    }
