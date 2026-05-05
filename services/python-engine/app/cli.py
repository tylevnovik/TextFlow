from __future__ import annotations

import hashlib
import json
import shutil
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from .artifact_store import load_artifact_payload, load_artifact_preview
from .bundled_sample_workspace import restore_bundled_sample_workspace
from .defaults import deep_copy_manifest, json_ready
from .experiment_store import list_experiment_specs, run_experiment_matrix, save_experiment_spec
from .ingestion import ensure_sample_files, import_files, parse_optional_year
from .ingestion_specs import list_ingestion_specs, save_ingestion_spec
from .review_store import create_review_task, list_review_tasks, resolve_review_task
from .resource_store import create_corpus_view, delete_corpus_view, update_corpus_view
from .run_diff import compare_runs
from .workflow_runner import run_project_workflow
from .project_store import (
    PROJECT_FILENAME,
    backfill_manifest_summary_fields,
    build_project_summary,
    create_project,
    create_project_from_template,
    delete_project,
    duplicate_project,
    export_project_package,
    find_project_dir,
    import_project_package,
    list_import_templates,
    list_project_templates,
    list_project_dirs,
    load_import_template,
    load_project_template,
    load_project,
    load_workspace_state,
    load_workspace_snapshot,
    mark_workspace_bootstrapped,
    remember_project,
    read_json,
    save_import_template_record,
    save_project_template,
    save_project,
    workspace_root,
    write_json,
)
from .sample_projects import (
    BUILTIN_SAMPLE_PROJECT_DATA_REVISION,
    FIRST_BUILTIN_SAMPLE_PROJECT_NAME,
    reconcile_builtin_sample_projects,
)

ProgressCallback = Callable[[float, str, dict[str, Any] | None], None]


def emit(payload: Any) -> None:
    sys.stdout.write(json.dumps(json_ready(payload), ensure_ascii=False))


def notify(
    progress_callback: ProgressCallback | None,
    progress: float,
    message: str,
    detail: dict[str, Any] | None = None,
) -> None:
    if progress_callback is None:
        return
    progress_callback(progress, message, detail)


def workflow_progress_detail_from_run_record(
    run_record: dict[str, Any],
    *,
    stage: str,
    detail_message: str,
) -> dict[str, Any]:
    node_runs = [
        node_run
        for node_run in run_record.get("node_runs", [])
        if isinstance(node_run, dict) and node_run.get("node_id")
    ]
    node_states = {
        str(node_run["node_id"]): {
            "node_id": str(node_run["node_id"]),
            "node_type": str(node_run.get("node_type") or ""),
            "label": str(node_run.get("label") or node_run.get("node_type") or "节点"),
            "status": str(node_run.get("status") or "completed"),
            "node_index": index,
            "total_nodes": max(len(node_runs), 1),
            "progress": 1.0,
            "started_at": node_run.get("started_at"),
            "ended_at": node_run.get("ended_at"),
            "duration_ms": node_run.get("duration_ms"),
            "cache_hit": bool(node_run.get("cache_hit")),
            "cache_key": node_run.get("cache_key"),
            "cache_path": node_run.get("cache_path"),
            "output_ports": list(node_run.get("output_ports") or []),
            "output_summary": node_run.get("output_summary"),
            "sample_outputs": list(node_run.get("sample_outputs") or []),
            "error": node_run.get("error"),
        }
        for index, node_run in enumerate(node_runs, start=1)
    }
    last_completed = node_runs[-1] if node_runs else None
    started_at = str(run_record.get("started_at") or "")
    ended_at = str(run_record.get("ended_at") or "")
    elapsed_ms: float | None = None
    if started_at and ended_at:
        try:
            started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            ended = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
            elapsed_ms = round(max(0.0, (ended - started).total_seconds()) * 1000, 3)
        except ValueError:
            elapsed_ms = None
    return {
        "kind": "workflow_run",
        "run_id": run_record.get("run_id"),
        "workflow_id": run_record.get("workflow_id"),
        "workflow_name": run_record.get("workflow_name"),
        "stage": stage,
        "total_nodes": max(len(node_runs), 1),
        "completed_nodes": len(node_runs),
        "current_node_id": None,
        "current_node_label": None,
        "current_node_index": None,
        "last_completed_node_id": last_completed.get("node_id") if isinstance(last_completed, dict) else None,
        "elapsed_ms": elapsed_ms,
        "detail": detail_message,
        "node_states": node_states,
        "node_state_delta": node_states,
        "full_node_state_sync": True,
    }


def parse_payload() -> dict[str, Any]:
    if len(sys.argv) < 3:
        return {}
    return json.loads(sys.argv[2])


def ensure_bootstrap_project() -> None:
    workspace_state = load_workspace_state()
    if (
        workspace_state.get("bootstrap_completed")
        and int(workspace_state.get("builtin_samples_revision") or 0) >= BUILTIN_SAMPLE_PROJECT_DATA_REVISION
    ):
        return

    project_dirs = list_project_dirs()
    if not project_dirs and not workspace_state.get("bootstrap_completed"):
        if restore_bundled_sample_workspace(workspace_root()):
            restored_state = load_workspace_state()
            if (
                restored_state.get("bootstrap_completed")
                and int(restored_state.get("builtin_samples_revision") or 0) >= BUILTIN_SAMPLE_PROJECT_DATA_REVISION
            ):
                return
        project_dirs = list_project_dirs()

    created = reconcile_builtin_sample_projects(
        create_missing=not project_dirs and not workspace_state.get("bootstrap_completed"),
    )
    if workspace_state.get("current_project_id") is None:
        starter_manifest = next(
            (manifest for _project_dir, manifest in created if manifest.get("name") == FIRST_BUILTIN_SAMPLE_PROJECT_NAME),
            created[0][1] if created else None,
        )
        if starter_manifest is not None:
            remember_project(starter_manifest["id"], set_current=True)

    mark_workspace_bootstrapped(builtin_samples_revision=BUILTIN_SAMPLE_PROJECT_DATA_REVISION)


def load_project_or_fail(project_id: str) -> tuple[Any, dict[str, Any], list[dict[str, Any]]]:
    project_dir = find_project_dir(project_id)
    if project_dir is None:
        raise ValueError(f"Project {project_id} not found")
    manifest, corpus = load_project(project_dir)
    return project_dir, manifest, corpus


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


def normalize_corpus_document(document: dict[str, Any], current: dict[str, Any] | None = None) -> dict[str, Any]:
    normalized = dict(current or {})
    normalized.update(document)
    doc_id = str(normalized.get("doc_id") or normalized.get("id") or f"doc-{hashlib.md5(json.dumps(json_ready(document), ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()[:8]}")
    raw_text = str(normalized.get("raw_text") or "")
    normalized["id"] = doc_id
    normalized["doc_id"] = doc_id
    normalized["title"] = str(normalized.get("title") or doc_id)
    normalized["source_profile"] = str(normalized.get("source_profile") or "generic")
    normalized["raw_text"] = raw_text
    normalized["clean_text"] = ""
    normalized["normalized_text"] = ""
    normalized["tokens"] = []
    normalized["phrase_hits"] = []
    normalized["filtered_tokens"] = []
    normalized["year"] = parse_optional_year(normalized.get("year"))
    normalized["extra_metadata"] = dict(normalized.get("extra_metadata") or {})
    normalized["status"] = "ready" if raw_text.strip() else "warning"
    normalized["raw_hash"] = hashlib.md5(raw_text.encode("utf-8")).hexdigest()
    return normalized


def refresh_source_files(project_dir: Path, manifest: dict[str, Any], corpus: list[dict[str, Any]]) -> dict[str, Any]:
    tracked_counts: dict[str, int] = {}
    has_untracked_documents = False
    for item in corpus:
        relative_path = item.get("extra_metadata", {}).get("_source_relative_path")
        if isinstance(relative_path, str) and relative_path:
            tracked_counts[relative_path] = tracked_counts.get(relative_path, 0) + 1
        else:
            has_untracked_documents = True

    next_sources: list[dict[str, Any]] = []
    for source in manifest.get("source_files", []):
        relative_path = str(source.get("relative_path") or "")
        next_source = dict(source)
        if relative_path in tracked_counts:
            next_source["row_count"] = tracked_counts[relative_path]
            next_sources.append(next_source)
            continue
        source_path = project_dir / relative_path if relative_path else None
        if not has_untracked_documents and relative_path.startswith("corpus/imported/") and source_path and source_path.exists():
            try:
                source_path.unlink()
            except OSError:
                pass
            continue
        next_sources.append(next_source)

    manifest["source_files"] = next_sources
    return manifest


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


def action_import_project_files(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.08, "正在读取项目配置")
    ensure_bootstrap_project()
    project_dir, manifest, corpus = load_project_or_fail(payload["project_id"])

    if payload.get("import_template"):
        manifest["import_template"] = payload["import_template"]

    existing_hashes = [item.get("raw_hash", "") for item in corpus if item.get("raw_hash")]
    notify(progress_callback, 0.35, "正在导入并校验文件")
    imported_corpus, source_files, validation_issues = import_files(
        payload.get("file_paths", []),
        manifest["import_template"],
        project_dir=project_dir,
        existing_hashes=existing_hashes,
    )
    corpus.extend(imported_corpus)
    manifest["source_files"] = [*manifest.get("source_files", []), *source_files]
    notify(progress_callback, 0.8, "正在保存导入结果")
    save_project(project_dir, manifest, corpus, already_normalized=True, dirty_sections={"manifest", "corpus"})
    remember_project(manifest["id"], set_current=True)

    notify(progress_callback, 1.0, "导入完成")
    return {
        "project_id": manifest["id"],
        "imported_documents": len(imported_corpus),
        "documents": imported_corpus,
        "project": manifest,
        "source_files": source_files,
        "document_count": len(corpus),
        "skipped_rows": len(validation_issues),
        "validation_issues": validation_issues[:10],
    }


def action_run_workflow(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.05, "正在准备流程", {
        "kind": "workflow_run",
        "stage": "preparing",
        "total_nodes": 1,
        "completed_nodes": 0,
        "detail": "正在准备流程",
        "node_states": {},
    })
    ensure_bootstrap_project()
    project_dir, manifest, corpus = load_project_or_fail(payload["project_id"])
    if not corpus:
        notify(progress_callback, 0.12, "当前项目为空，正在载入示例语料")
        corpus, source_files, _issues = import_files(ensure_sample_files(), manifest["import_template"], project_dir=project_dir)
        manifest["source_files"] = source_files
    run_options = {
        key: payload[key]
        for key in (
            "run_mode",
            "changed_doc_ids",
            "changed_dictionary_tables",
            "process_changed_only",
            "changed_docs_only",
            "incremental_scope",
            "source_node_ids",
        )
        if key in payload
    }
    manifest, corpus, run_record = run_project_workflow(
        project_dir,
        manifest,
        corpus,
        progress_callback=progress_callback,
        run_options=run_options,
    )
    notify(
        progress_callback,
        0.95,
        "正在保存运行结果",
        workflow_progress_detail_from_run_record(
            run_record,
            stage="saving",
            detail_message="正在保存运行结果",
        ),
    )
    save_project(project_dir, manifest, corpus, already_normalized=True, dirty_sections={"manifest", "corpus"})
    remember_project(manifest["id"], set_current=True)
    saved_manifest, _saved_corpus = load_project(project_dir)
    notify(
        progress_callback,
        1.0,
        "流程运行完成",
        workflow_progress_detail_from_run_record(
            run_record,
            stage="completed",
            detail_message="流程运行完成",
        ),
    )
    return {
        "run": run_record,
        "project": saved_manifest,
    }


def action_export_project(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.08, "正在准备导出")
    ensure_bootstrap_project()
    project_dir, manifest, corpus = load_project_or_fail(payload["project_id"])
    formats = payload.get("formats", [])
    if not manifest.get("run_history"):
        notify(progress_callback, 0.2, "尚无运行结果，先生成一次分析结果")
        manifest, corpus, _ = run_project_workflow(project_dir, manifest, corpus, progress_callback=progress_callback)
        save_project(project_dir, manifest, corpus, already_normalized=True, dirty_sections={"manifest", "corpus"})

    latest_run = manifest["run_history"][-1]["run_id"]
    latest_run_dir = project_dir / "runs" / latest_run
    export_dir = project_dir / "exports" / latest_run
    export_dir.mkdir(parents=True, exist_ok=True)
    exported: list[dict[str, str]] = []

    if "csv" in formats:
        notify(progress_callback, 0.45, "正在整理 CSV 文件")
        for path in (latest_run_dir / "outputs").glob("*.csv"):
            target = export_dir / path.name
            shutil.copy2(path, target)
            exported.append({
                "path": str(target),
                "relative_path": str(target.relative_to(project_dir).as_posix()),
            })

    if "html" in formats:
        notify(progress_callback, 0.6, "正在整理 HTML 报告")
        report_path = latest_run_dir / "report" / "report.html"
        target = export_dir / report_path.name
        shutil.copy2(report_path, target)
        exported.append({
            "path": str(target),
            "relative_path": str(target.relative_to(project_dir).as_posix()),
        })

    if "png" in formats:
        notify(progress_callback, 0.72, "正在整理图表文件")
        for path in (latest_run_dir / "charts").glob("*.png"):
            target = export_dir / path.name
            shutil.copy2(path, target)
            exported.append({
                "path": str(target),
                "relative_path": str(target.relative_to(project_dir).as_posix()),
            })

    if "xlsx" in formats:
        notify(progress_callback, 0.84, "正在写出 Excel 汇总")
        source_xlsx = latest_run_dir / "outputs" / "analysis_bundle.xlsx"
        xlsx_path = export_dir / "analysis_bundle.xlsx"
        if source_xlsx.exists():
            shutil.copy2(source_xlsx, xlsx_path)
        else:
            with pd.ExcelWriter(xlsx_path) as writer:
                for key, rows in manifest["results"].items():
                    if isinstance(rows, list) and key != "report_files":
                        pd.DataFrame(rows).to_excel(writer, sheet_name=key[:31], index=False)
        exported.append({
            "path": str(xlsx_path),
            "relative_path": str(xlsx_path.relative_to(project_dir).as_posix()),
        })

    remember_project(manifest["id"], set_current=True)
    notify(progress_callback, 1.0, "导出完成")
    return {
        "project_id": manifest["id"],
        "export_dir": str(export_dir),
        "relative_export_dir": str(export_dir.relative_to(project_dir).as_posix()),
        "files": exported,
    }


def action_export_project_backup(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.1, "正在整理项目文件")
    ensure_bootstrap_project()
    project_dir, manifest, _corpus = load_project_or_fail(payload["project_id"])
    output_path = Path(payload["path"]).expanduser() if payload.get("path") else None
    notify(progress_callback, 0.6, "正在打包 .tfproj 项目包")
    archive_path = export_project_package(project_dir, output_path)
    remember_project(manifest["id"], set_current=True)
    notify(progress_callback, 1.0, "项目包已导出")
    try:
        relative_path = archive_path.relative_to(project_dir).as_posix()
    except ValueError:
        relative_path = str(archive_path)
    return {"path": str(archive_path), "relative_path": relative_path}


def action_import_project_package(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.1, "正在读取 .tfproj 项目包")
    project_dir, manifest, corpus = import_project_package(Path(payload["path"]))
    remember_project(manifest["id"], set_current=True)
    notify(progress_callback, 1.0, "项目包已导入")
    return build_project_summary(project_dir, manifest, corpus)


def action_save_project_template(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.1, "正在保存项目模板")
    ensure_bootstrap_project()
    _project_dir, manifest, _corpus = load_project_or_fail(payload["project_id"])
    template = save_project_template(
        manifest,
        name=payload.get("name"),
        description=payload.get("description"),
        template_id=payload.get("template_id"),
    )
    remember_project(manifest["id"], set_current=True)
    notify(progress_callback, 1.0, "项目模板已保存")
    return template


def action_list_project_templates(
    _payload: dict[str, Any] | None = None,
    progress_callback: ProgressCallback | None = None,
) -> list[dict[str, Any]]:
    notify(progress_callback, 0.1, "正在读取项目模板")
    templates = list_project_templates()
    notify(progress_callback, 1.0, "项目模板已加载")
    return templates


def action_save_import_template(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.1, "正在保存导入模板")
    ensure_bootstrap_project()
    template_payload = payload.get("template")
    if template_payload is None:
        _project_dir, manifest, _corpus = load_project_or_fail(payload["project_id"])
        template_payload = manifest["import_template"]
        remember_project(manifest["id"], set_current=True)
    saved = save_import_template_record(
        template_payload,
        name=payload.get("name"),
        description=payload.get("description"),
        template_id=payload.get("template_id"),
    )
    notify(progress_callback, 1.0, "导入模板已保存")
    return saved


def action_list_import_templates(
    _payload: dict[str, Any] | None = None,
    progress_callback: ProgressCallback | None = None,
) -> list[dict[str, Any]]:
    notify(progress_callback, 0.1, "正在读取导入模板")
    templates = list_import_templates()
    notify(progress_callback, 1.0, "导入模板已加载")
    return templates


def action_load_import_template(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.1, "正在读取导入模板")
    template = load_import_template(payload["template_id"])
    notify(progress_callback, 1.0, "导入模板已加载")
    return template


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


def action_update_corpus_document(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.1, "正在保存语料文档")
    ensure_bootstrap_project()
    project_dir, manifest, corpus = load_project_or_fail(payload["project_id"])
    document = payload["document"]
    doc_id = str(document.get("doc_id") or document.get("id") or "")
    existing = next((item for item in corpus if item.get("doc_id") == doc_id or item.get("id") == doc_id), None)
    normalized = normalize_corpus_document(document, current=existing)

    updated = False
    next_corpus: list[dict[str, Any]] = []
    for item in corpus:
        item_doc_id = str(item.get("doc_id") or item.get("id") or "")
        if item_doc_id == normalized["doc_id"]:
            next_corpus.append(normalized)
            updated = True
        else:
            next_corpus.append(item)
    if not updated:
        next_corpus.append(normalized)

    manifest = refresh_source_files(project_dir, manifest, next_corpus)
    save_project(project_dir, manifest, next_corpus, already_normalized=True, dirty_sections={"manifest", "corpus"})
    remember_project(manifest["id"], set_current=True)
    notify(progress_callback, 1.0, "语料文档已保存，请重新运行处理流程")
    return {
        **normalized,
        "document": normalized,
        "document_count": len(next_corpus),
        "source_files": manifest.get("source_files", []),
        "project_updated_at": manifest.get("updated_at"),
    }


def action_delete_corpus_document(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.1, "正在删除语料文档")
    ensure_bootstrap_project()
    project_dir, manifest, corpus = load_project_or_fail(payload["project_id"])
    doc_id = str(payload["doc_id"])
    next_corpus = [item for item in corpus if str(item.get("doc_id") or item.get("id") or "") != doc_id]
    if len(next_corpus) == len(corpus):
        raise ValueError(f"Corpus document {doc_id} not found")

    manifest = refresh_source_files(project_dir, manifest, next_corpus)
    save_project(project_dir, manifest, next_corpus, already_normalized=True, dirty_sections={"manifest", "corpus"})
    remember_project(manifest["id"], set_current=True)
    notify(progress_callback, 1.0, "语料文档已删除，请重新运行处理流程")
    return {
        "doc_id": doc_id,
        "document_count": len(next_corpus),
        "source_files": manifest.get("source_files", []),
        "project_updated_at": manifest.get("updated_at"),
    }


def action_import_dictionary_sheet(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.1, "正在读取词表文件")
    ensure_bootstrap_project()
    project_dir, manifest, corpus = load_project_or_fail(payload["project_id"])
    kind = payload["kind"]
    source_path = Path(payload["path"])
    imported_table = read_json(source_path)
    if not isinstance(imported_table, dict):
        raise ValueError(f"Invalid dictionary sheet: {source_path}")

    collection = manifest["dictionary_set"]["collections"][kind]
    existing_ids = {
        str(table.get("id") or "")
        for table in collection.get("tables", [])
        if isinstance(table, dict)
    }
    base_id = str(imported_table.get("id") or f"{kind}-imported-{source_path.stem}")
    table_id = base_id
    suffix = 2
    while table_id in existing_ids:
        table_id = f"{base_id}-{suffix}"
        suffix += 1

    imported_table["id"] = table_id
    imported_table["kind"] = kind
    imported_table.setdefault("name", source_path.stem or "导入词表")
    imported_table.setdefault("version", "2.0.0")
    imported_table.setdefault("description", f"从 {source_path.name} 导入的词表资源。")
    imported_table.setdefault("source_url", None)
    imported_table["built_in"] = False
    imported_table["editable"] = True
    imported_table["enabled"] = bool(imported_table.get("enabled", True))
    imported_table.setdefault("tags", ["imported"])
    imported_table.setdefault("entries", [])
    collection.setdefault("tables", []).append(imported_table)
    notify(progress_callback, 0.7, "正在写入项目词表")
    save_project(project_dir, manifest, corpus, already_normalized=True, dirty_sections={"manifest", "dictionary_set"})
    remember_project(manifest["id"], set_current=True)
    notify(progress_callback, 1.0, "词表已导入")
    return {
        **imported_table,
        "table": imported_table,
        "dictionary_set": manifest["dictionary_set"],
        "project_updated_at": manifest.get("updated_at"),
    }


def action_export_dictionary_sheet(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.1, "正在整理词表")
    ensure_bootstrap_project()
    _project_dir, manifest, _corpus = load_project_or_fail(payload["project_id"])
    kind = payload["kind"]
    table_id = str(payload["table_id"])
    output_path = payload["path"]
    table = next(
        (
            item
            for item in manifest["dictionary_set"]["collections"][kind].get("tables", [])
            if isinstance(item, dict) and str(item.get("id") or "") == table_id
        ),
        None,
    )
    if table is None:
        raise ValueError(f"Dictionary table {table_id} not found in {kind}")
    write_json(Path(output_path), table)
    remember_project(manifest["id"], set_current=True)
    notify(progress_callback, 1.0, "词表已导出")
    return {
        "kind": kind,
        "table_id": table_id,
        "path": output_path,
    }


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


def action_compare_runs(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.1, "正在比较运行结果")
    ensure_bootstrap_project()
    _project_dir, manifest, _corpus = load_project_or_fail(payload["project_id"])
    diff = compare_runs(
        manifest,
        str(payload.get("left_run_id") or payload.get("leftRunId") or ""),
        str(payload.get("right_run_id") or payload.get("rightRunId") or ""),
    )
    remember_project(manifest["id"], set_current=True)
    notify(progress_callback, 1.0, "运行对比已完成")
    return diff


def action_save_ingestion_spec(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.1, "正在保存导入规格")
    ensure_bootstrap_project()
    project_dir, manifest, corpus = load_project_or_fail(payload["project_id"])
    spec_payload = payload.get("spec") if isinstance(payload.get("spec"), dict) else {key: value for key, value in payload.items() if key != "project_id"}
    saved = save_ingestion_spec(project_dir, manifest, spec_payload)
    save_project(project_dir, manifest, corpus, already_normalized=True, dirty_sections={"manifest", "ingestion_specs"})
    remember_project(manifest["id"], set_current=True)
    notify(progress_callback, 1.0, "导入规格已保存")
    return saved


def action_list_ingestion_specs(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> list[dict[str, Any]]:
    notify(progress_callback, 0.1, "正在读取导入规格")
    ensure_bootstrap_project()
    project_dir, manifest, _corpus = load_project_or_fail(payload["project_id"])
    specs = list_ingestion_specs(project_dir, manifest)
    remember_project(manifest["id"], set_current=True)
    notify(progress_callback, 1.0, "导入规格已加载")
    return specs


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


def action_load_artifact_preview(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.1, "正在读取产物预览")
    ensure_bootstrap_project()
    project_dir, manifest, _corpus = load_project_or_fail(payload["project_id"])
    preview = load_artifact_preview(project_dir, str(payload["artifact_id"]), limit=int(payload.get("limit", 50) or 50))
    remember_project(manifest["id"], set_current=True)
    notify(progress_callback, 1.0, "产物预览已加载")
    return preview


def action_load_artifact_payload(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> Any:
    notify(progress_callback, 0.1, "正在读取产物内容")
    ensure_bootstrap_project()
    project_dir, manifest, _corpus = load_project_or_fail(payload["project_id"])
    artifact_payload = load_artifact_payload(project_dir, str(payload["artifact_id"]))
    remember_project(manifest["id"], set_current=True)
    notify(progress_callback, 1.0, "产物内容已加载")
    return artifact_payload


def action_list_run_artifacts(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> list[dict[str, Any]]:
    notify(progress_callback, 0.1, "正在整理运行产物")
    ensure_bootstrap_project()
    _project_dir, manifest, _corpus = load_project_or_fail(payload["project_id"])
    run_id = str(payload.get("run_id") or "")
    records = [
        deepcopy(item)
        for item in manifest.get("artifact_records", [])
        if isinstance(item, dict) and (not run_id or str(item.get("run_id") or "") == run_id)
    ]
    notify(progress_callback, 1.0, "运行产物已加载")
    return records


ACTION_HANDLERS: dict[str, Callable[..., Any]] = {
    "load-workspace": action_load_workspace,
    "create-project": action_create_project,
    "create-project-from-template": action_create_project_from_template,
    "open-project": action_open_project,
    "duplicate-project": action_duplicate_project,
    "delete-project": action_delete_project,
    "import-project-files": action_import_project_files,
    "run-workflow": action_run_workflow,
    "export-project": action_export_project,
    "export-project-backup": action_export_project_backup,
    "import-project-package": action_import_project_package,
    "save-project-template": action_save_project_template,
    "list-project-templates": action_list_project_templates,
    "save-import-template": action_save_import_template,
    "list-import-templates": action_list_import_templates,
    "load-import-template": action_load_import_template,
    "save-project": action_save_project,
    "update-corpus-document": action_update_corpus_document,
    "delete-corpus-document": action_delete_corpus_document,
    "import-dictionary-sheet": action_import_dictionary_sheet,
    "export-dictionary-sheet": action_export_dictionary_sheet,
    "create-review-task": action_create_review_task,
    "list-review-tasks": action_list_review_tasks,
    "resolve-review-task": action_resolve_review_task,
    "apply-review-resolution": action_apply_review_resolution,
    "save-experiment-spec": action_save_experiment_spec,
    "list-experiment-specs": action_list_experiment_specs,
    "run-experiment-matrix": action_run_experiment_matrix,
    "compare-runs": action_compare_runs,
    "save-ingestion-spec": action_save_ingestion_spec,
    "list-ingestion-specs": action_list_ingestion_specs,
    "create-corpus-view": action_create_corpus_view,
    "update-corpus-view": action_update_corpus_view,
    "delete-corpus-view": action_delete_corpus_view,
    "load-artifact-preview": action_load_artifact_preview,
    "load-artifact-payload": action_load_artifact_payload,
    "list-run-artifacts": action_list_run_artifacts,
}


def execute_action(
    action: str,
    payload: dict[str, Any] | None = None,
    progress_callback: ProgressCallback | None = None,
) -> Any:
    handler = ACTION_HANDLERS.get(action)
    if handler is None:
        raise ValueError(f"Unknown action: {action}")
    payload = payload or {}
    return handler(payload, progress_callback)


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python -m app.cli <action> [json-payload]")

    action = sys.argv[1]
    payload = parse_payload()

    emit(execute_action(action, payload))


if __name__ == "__main__":
    main()
