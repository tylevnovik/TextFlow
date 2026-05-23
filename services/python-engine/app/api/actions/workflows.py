from __future__ import annotations

import shutil
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any
import pandas as pd

from .support import ProgressCallback, notify, ensure_bootstrap_project, load_project_or_fail
from ...domain.defaults import deep_copy_manifest
from ...ingestion import import_files, ensure_sample_files
from ...workflow.runner import run_project_workflow
from ...storage.projects import (
    save_project,
    remember_project,
    load_project,
    compact_results_bundle,
    list_project_templates,
    save_import_template_record,
    list_import_templates,
    load_import_template,
    save_project_template,
)
from ...storage.run_diff import compare_runs
from ...storage.artifacts import load_artifact_preview, load_artifact_payload


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
            "output_previews": deepcopy(node_run.get("output_previews") or {}),
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
    response_project = deepcopy(saved_manifest)
    response_project["results"] = compact_results_bundle(saved_manifest.get("results"))
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
        "project": response_project,
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

