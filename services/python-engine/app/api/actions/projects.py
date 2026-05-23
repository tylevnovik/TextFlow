from __future__ import annotations

from typing import Any
from copy import deepcopy

from .support import ProgressCallback, notify, ensure_bootstrap_project, load_project_or_fail
from ...storage.projects import (
    load_workspace_snapshot,
    create_project,
    remember_project,
    build_project_summary,
    load_project_template,
    create_project_from_template,
    find_project_dir,
    read_json,
    backfill_manifest_summary_fields,
    duplicate_project,
    delete_project,
    save_project,
    PROJECT_FILENAME,
)
from ...defaults import deep_copy_manifest
from ...storage.resources import create_corpus_view, update_corpus_view, delete_corpus_view


def _save_sections_from_project_payload(payload: dict[str, Any]) -> set[str]:
    dirty_sections = {"manifest"}
    if "import_template" in payload:
        dirty_sections.add("import_template")
    if "dictionary_set" in payload:
        dirty_sections.add("dictionary_set")
    if "corpus_views" in payload:
        dirty_sections.add("corpus_views")
    if "ingestion_specs" in payload:
        dirty_sections.add("ingestion_specs")
    return dirty_sections


def action_load_workspace(_payload: dict[str, Any] | None = None, progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.1, "正在准备工作区")
    ensure_bootstrap_project()
    snapshot = load_workspace_snapshot()
    notify(progress_callback, 1.0, "工作区已就绪")
    return snapshot


def action_create_project(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.1, "正在创建项目")
    name = payload["name"]
    description = payload.get("description", "")
    project_dir, manifest = create_project(name, description)
    remember_project(manifest["id"], set_current=True)
    notify(progress_callback, 1.0, "项目已创建")
    return build_project_summary(project_dir, manifest, [])


def action_create_project_from_template(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.1, "正在应用项目模板")
    template = load_project_template(payload["template_id"])
    project_dir, manifest = create_project_from_template(
        payload["name"],
        payload.get("description", ""),
        template,
    )
    remember_project(manifest["id"], set_current=True)
    notify(progress_callback, 1.0, "模板项目已创建")
    return build_project_summary(project_dir, manifest, [])


def action_open_project(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.1, "正在打开项目")
    ensure_bootstrap_project()
    project_dir = find_project_dir(payload["project_id"])
    if project_dir is None:
        raise ValueError(f"Project {payload['project_id']} not found")
    manifest = read_json(project_dir / PROJECT_FILENAME)
    if not isinstance(manifest, dict):
        raise ValueError(f"Invalid project manifest: {project_dir / PROJECT_FILENAME}")
    manifest = backfill_manifest_summary_fields(project_dir, manifest)
    remember_project(str(manifest["id"]), set_current=True)
    notify(progress_callback, 1.0, "项目已打开")
    return build_project_summary(project_dir, manifest)


def action_duplicate_project(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.1, "正在复制项目")
    ensure_bootstrap_project()
    duplicated_name = payload.get("name")
    project_dir, manifest, corpus = duplicate_project(payload["project_id"], duplicated_name)
    remember_project(manifest["id"], set_current=True)
    notify(progress_callback, 1.0, "项目副本已生成")
    return build_project_summary(project_dir, manifest, corpus)


def action_delete_project(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.1, "正在删除项目")
    ensure_bootstrap_project()
    result = delete_project(payload["project_id"])
    notify(progress_callback, 1.0, "项目已删除")
    return result


def action_save_project(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.1, "正在保存项目设置")
    ensure_bootstrap_project()
    project_dir, manifest, corpus = load_project_or_fail(payload["id"])
    updated = deep_copy_manifest(manifest)
    updated.update(payload)
    save_project(project_dir, updated, corpus, dirty_sections=_save_sections_from_project_payload(payload))
    remember_project(updated["id"], set_current=True)
    notify(progress_callback, 1.0, "项目设置已保存")
    return build_project_summary(project_dir, updated, corpus)


def action_create_corpus_view(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.1, "正在创建语料视图")
    ensure_bootstrap_project()
    project_dir, manifest, corpus = load_project_or_fail(payload["project_id"])
    view_payload = payload.get("view") if isinstance(payload.get("view"), dict) else {key: value for key, value in payload.items() if key != "project_id"}
    created = create_corpus_view(project_dir, manifest, view_payload)
    save_project(project_dir, manifest, corpus, already_normalized=True, dirty_sections={"manifest", "corpus_views"})
    remember_project(manifest["id"], set_current=True)
    notify(progress_callback, 1.0, "语料视图已创建")
    return created


def action_update_corpus_view(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.1, "正在更新语料视图")
    ensure_bootstrap_project()
    project_dir, manifest, corpus = load_project_or_fail(payload["project_id"])
    view_payload = payload.get("view") if isinstance(payload.get("view"), dict) else {key: value for key, value in payload.items() if key != "project_id"}
    updated = update_corpus_view(project_dir, manifest, view_payload)
    save_project(project_dir, manifest, corpus, already_normalized=True, dirty_sections={"manifest", "corpus_views"})
    remember_project(manifest["id"], set_current=True)
    notify(progress_callback, 1.0, "语料视图已更新")
    return updated


def action_delete_corpus_view(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.1, "正在删除语料视图")
    ensure_bootstrap_project()
    project_dir, manifest, corpus = load_project_or_fail(payload["project_id"])
    removed = delete_corpus_view(project_dir, manifest, str(payload.get("view_id") or payload.get("id") or ""))
    save_project(project_dir, manifest, corpus, already_normalized=True, dirty_sections={"manifest", "corpus_views"})
    remember_project(manifest["id"], set_current=True)
    notify(progress_callback, 1.0, "语料视图已删除")
    return removed
