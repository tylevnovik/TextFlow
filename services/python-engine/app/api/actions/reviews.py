from __future__ import annotations

from typing import Any

from .support import ProgressCallback, notify, ensure_bootstrap_project, load_project_or_fail
from ...storage.projects import save_project, remember_project
from ...storage.reviews import create_review_task, list_review_tasks, resolve_review_task
from .imports import refresh_source_files


def action_create_review_task(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.1, "正在创建复核任务")
    ensure_bootstrap_project()
    project_dir, manifest, corpus = load_project_or_fail(payload["project_id"])
    task_payload = payload.get("task") if isinstance(payload.get("task"), dict) else payload
    created = create_review_task(
        manifest,
        review_type=str(task_payload["review_type"]),
        target_ref=task_payload.get("target_ref"),
        title=task_payload.get("title"),
        description=task_payload.get("description"),
        payload=task_payload.get("payload"),
    )
    save_project(project_dir, manifest, corpus, already_normalized=True, dirty_sections={"manifest"})
    remember_project(manifest["id"], set_current=True)
    notify(progress_callback, 1.0, "复核任务已创建")
    return {
        "task": created,
        "project": manifest,
        "project_updated_at": manifest.get("updated_at"),
    }


def action_list_review_tasks(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.1, "正在加载复核任务")
    ensure_bootstrap_project()
    _project_dir, manifest, _corpus = load_project_or_fail(payload["project_id"])
    tasks = list_review_tasks(manifest, status=payload.get("status"))
    remember_project(manifest["id"], set_current=True)
    notify(progress_callback, 1.0, "复核任务已加载")
    return {
        "project_id": manifest["id"],
        "tasks": tasks,
    }


def action_resolve_review_task(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.1, "正在处理复核结果")
    ensure_bootstrap_project()
    project_dir, manifest, corpus = load_project_or_fail(payload["project_id"])
    resolved_task, dirty_sections = resolve_review_task(
        manifest,
        corpus,
        str(payload["review_id"]),
        payload.get("resolution") if isinstance(payload.get("resolution"), dict) else {},
    )
    if "corpus" in dirty_sections:
        manifest = refresh_source_files(project_dir, manifest, corpus)
    save_project(project_dir, manifest, corpus, already_normalized=True, dirty_sections=dirty_sections)
    remember_project(manifest["id"], set_current=True)
    notify(progress_callback, 1.0, "复核结果已写回项目")
    return {
        "task": resolved_task,
        "project": manifest,
        "corpus": corpus,
        "source_files": manifest.get("source_files", []),
        "project_updated_at": manifest.get("updated_at"),
    }


def action_apply_review_resolution(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    return action_resolve_review_task(payload, progress_callback)
