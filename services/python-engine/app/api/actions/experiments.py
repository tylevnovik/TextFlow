from __future__ import annotations

from typing import Any

from .support import ProgressCallback, notify, ensure_bootstrap_project, load_project_or_fail
from ...storage.experiments import list_experiment_specs, save_experiment_spec
from ...storage.projects import save_project, remember_project, load_project
from ...workflow.experiments import run_experiment_matrix
from ...ingestion import import_files, ensure_sample_files


def action_save_experiment_spec(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.1, "正在保存实验规格")
    ensure_bootstrap_project()
    project_dir, manifest, corpus = load_project_or_fail(payload["project_id"])
    spec_payload = payload.get("experiment") if isinstance(payload.get("experiment"), dict) else payload.get("spec")
    if not isinstance(spec_payload, dict):
        spec_payload = {key: value for key, value in payload.items() if key != "project_id"}
    saved = save_experiment_spec(manifest, spec_payload)
    save_project(project_dir, manifest, corpus, already_normalized=True, dirty_sections={"manifest"})
    remember_project(manifest["id"], set_current=True)
    notify(progress_callback, 1.0, "实验规格已保存")
    return {
        "experiment": saved,
        "project": manifest,
        "project_updated_at": manifest.get("updated_at"),
    }


def action_list_experiment_specs(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.1, "正在读取实验规格")
    ensure_bootstrap_project()
    _project_dir, manifest, _corpus = load_project_or_fail(payload["project_id"])
    experiments = list_experiment_specs(manifest)
    remember_project(manifest["id"], set_current=True)
    notify(progress_callback, 1.0, "实验规格已加载")
    return {
        "project_id": manifest["id"],
        "experiments": experiments,
    }


def action_run_experiment_matrix(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.05, "正在准备实验矩阵")
    ensure_bootstrap_project()
    project_dir, manifest, corpus = load_project_or_fail(payload["project_id"])
    if not corpus:
        notify(progress_callback, 0.12, "当前项目为空，正在载入示例语料")
        corpus, source_files, _issues = import_files(ensure_sample_files(), manifest["import_template"], project_dir=project_dir)
        manifest["source_files"] = source_files
    result = run_experiment_matrix(
        project_dir,
        manifest,
        corpus,
        str(payload["experiment_id"]),
        progress_callback=progress_callback,
    )
    save_project(project_dir, manifest, result["corpus"], already_normalized=True, dirty_sections={"manifest", "corpus"})
    remember_project(manifest["id"], set_current=True)
    saved_manifest, _saved_corpus = load_project(project_dir)
    result["project"] = saved_manifest
    notify(progress_callback, 1.0, "实验矩阵运行完成")
    return result
