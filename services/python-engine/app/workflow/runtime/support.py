from __future__ import annotations

from datetime import datetime
from inspect import Parameter, signature
from typing import Any, Callable
from uuid import uuid4

from ...defaults import compile_runtime_profile_from_workflow, default_runtime_profile, utc_now_iso, workflow_payload_hash

ProgressCallback = Callable[[float, str, dict[str, Any] | None], None]

_PROGRESS_CALLBACK_DETAIL_SUPPORT: dict[int, bool] = {}


def _progress_callback_accepts_detail(progress_callback: ProgressCallback) -> bool:
    try:
        code = progress_callback.__code__
    except AttributeError:
        code = None
    cache_key = id(code) if code is not None else id(progress_callback)
    cached = _PROGRESS_CALLBACK_DETAIL_SUPPORT.get(cache_key)
    if cached is not None:
        return cached

    accepts_detail = True
    try:
        parameters = signature(progress_callback).parameters.values()
    except (TypeError, ValueError):
        accepts_detail = True
    else:
        positional_count = 0
        has_varargs = False
        for parameter in parameters:
            if parameter.kind == Parameter.VAR_POSITIONAL:
                has_varargs = True
                break
            if parameter.kind in {Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD}:
                positional_count += 1
        accepts_detail = has_varargs or positional_count >= 3

    _PROGRESS_CALLBACK_DETAIL_SUPPORT[cache_key] = accepts_detail
    return accepts_detail


def dispatch_progress_callback(
    progress_callback: ProgressCallback | Callable[[float, str], None] | None,
    progress: float,
    message: str,
    detail: dict[str, Any] | None = None,
) -> None:
    if progress_callback is None:
        return
    if _progress_callback_accepts_detail(progress_callback):
        progress_callback(progress, message, detail)
        return
    progress_callback(progress, message)


def normalize_run_scope(scope: dict[str, Any] | None) -> dict[str, Any]:
    scope = dict(scope or {})
    return {
        "mode": scope.get("mode", "all_documents"),
        "source_values": [str(value) for value in scope.get("source_values", []) if str(value).strip()],
        "institution_values": [str(value) for value in scope.get("institution_values", []) if str(value).strip()],
        "category_values": [str(value) for value in scope.get("category_values", []) if str(value).strip()],
        "year_from": scope.get("year_from"),
        "year_to": scope.get("year_to"),
        "selected_doc_ids": [str(value) for value in scope.get("selected_doc_ids", []) if str(value).strip()],
    }


def document_matches_scope(item: dict[str, Any], scope: dict[str, Any]) -> bool:
    mode = scope.get("mode", "all_documents")
    doc_id = str(item.get("doc_id") or item.get("id") or "")
    if mode == "selected_documents":
        selected_doc_ids = set(scope.get("selected_doc_ids", []))
        return doc_id in selected_doc_ids
    if mode != "filtered_subset":
        return True

    source_values = set(scope.get("source_values", []))
    institution_values = set(scope.get("institution_values", []))
    category_values = set(scope.get("category_values", []))
    year_from = scope.get("year_from")
    year_to = scope.get("year_to")
    year = item.get("year")

    if source_values and str(item.get("source") or "") not in source_values:
        return False
    if institution_values and str(item.get("institution") or "") not in institution_values:
        return False
    if category_values and str(item.get("category_or_tag") or "") not in category_values:
        return False
    if year_from not in (None, ""):
        if year is None or int(year) < int(year_from):
            return False
    if year_to not in (None, ""):
        if year is None or int(year) > int(year_to):
            return False
    return True


def describe_run_scope(scope: dict[str, Any], total_count: int, matched_count: int) -> str:
    mode = scope.get("mode", "all_documents")
    if mode == "selected_documents":
        selected_doc_ids = scope.get("selected_doc_ids", [])
        return f"手动选择 {len(selected_doc_ids)} 篇文档，实际命中 {matched_count}/{total_count} 篇。"
    if mode != "filtered_subset":
        return f"处理对象为项目内全部资料，共 {matched_count}/{total_count} 篇文档。"

    parts: list[str] = []
    if scope.get("source_values"):
        parts.append(f"来源={', '.join(scope['source_values'])}")
    if scope.get("institution_values"):
        parts.append(f"机构={', '.join(scope['institution_values'])}")
    if scope.get("category_values"):
        parts.append(f"标签={', '.join(scope['category_values'])}")
    year_from = scope.get("year_from")
    year_to = scope.get("year_to")
    if year_from not in (None, "") or year_to not in (None, ""):
        if year_from not in (None, "") and year_to not in (None, ""):
            parts.append(f"年份={year_from}-{year_to}")
        elif year_from not in (None, ""):
            parts.append(f"年份>= {year_from}")
        else:
            parts.append(f"年份<= {year_to}")
    detail = "；".join(parts) if parts else "已启用条件筛选"
    return f"处理对象为筛选资料：{detail}，实际命中 {matched_count}/{total_count} 篇文档。"


def describe_output_bundle(export_params: dict[str, Any]) -> str:
    outputs: list[str] = []
    if export_params.get("export_csv", True) or export_params.get("export_xlsx", True):
        outputs.append("表格包")
    if export_params.get("export_png", True):
        outputs.append("图表包")
    if export_params.get("export_html_report", True):
        outputs.append("HTML 报告")
    if export_params.get("include_audit", True):
        outputs.append("审计表")
    return "、".join(outputs) or "仅运行快照"


def select_active_workflow(manifest: dict[str, Any]) -> dict[str, Any]:
    workflow_definitions = [
        workflow
        for workflow in manifest.get("workflow_definitions", [])
        if isinstance(workflow, dict) and workflow.get("workflow_id")
    ]
    active_workflow_id = str(manifest.get("active_workflow_id") or "")
    workflow_lookup = {str(workflow["workflow_id"]): workflow for workflow in workflow_definitions}
    return workflow_lookup.get(active_workflow_id) or (workflow_definitions[0] if workflow_definitions else {})


def workflow_runtime_profile(workflow_definition: dict[str, Any] | None) -> dict[str, Any]:
    runtime_profile = compile_runtime_profile_from_workflow(workflow_definition, default_runtime_profile())
    runtime_profile["run_scope"] = normalize_run_scope(runtime_profile.get("run_scope"))
    runtime_profile["recipe_id"] = str(runtime_profile.get("recipe_id") or "standard_analysis")
    runtime_profile["output_bundle_id"] = str(runtime_profile.get("output_bundle_id") or "full_report")
    return runtime_profile


def build_run_params_snapshot(
    workflow_definition: dict[str, Any],
    runtime_profile: dict[str, Any],
) -> dict[str, Any]:
    return {
        "workflow_id": str(workflow_definition.get("workflow_id") or "wf-default"),
        "workflow_name": str(workflow_definition.get("name") or "默认工作流"),
        "workflow_hash": workflow_payload_hash(workflow_definition),
        "workflow_definition": workflow_definition,
        "runtime_profile": runtime_profile,
    }


def build_run_record(
    manifest: dict[str, Any],
    logs: list[dict[str, Any]],
    warnings: list[str],
    errors: list[str],
    processed_document_count: int,
    run_scope_summary: str,
    recipe_id: str,
    output_bundle_id: str,
    output_summary: str,
    workflow_definition: dict[str, Any],
) -> dict[str, Any]:
    run_id = f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:6]}"
    return {
        "run_id": run_id,
        "project_id": manifest["id"],
        "workflow_version": str(
            workflow_definition.get("version")
            or manifest.get("schema_version")
            or manifest.get("version")
            or "1.0.0"
        ),
        "workflow_id": str(workflow_definition.get("workflow_id") or "wf-default"),
        "workflow_name": str(workflow_definition.get("name") or "默认工作流"),
        "workflow_hash": workflow_payload_hash(workflow_definition),
        "dictionary_version": manifest["dictionary_set"]["version"],
        "started_at": utc_now_iso(),
        "ended_at": None,
        "status": "running",
        "warnings": warnings,
        "errors": errors,
        "logs": logs,
        "artifacts": [],
        "params_snapshot_path": f"runs/{run_id}/params_snapshot.json",
        "processed_document_count": processed_document_count,
        "run_scope_summary": run_scope_summary,
        "recipe_id": recipe_id,
        "output_bundle_id": output_bundle_id,
        "output_summary": output_summary,
    }


def build_artifact_handle(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_id": str(record.get("artifact_id") or ""),
        "run_id": str(record.get("run_id") or ""),
        "node_id": str(record.get("node_id") or ""),
        "kind": str(record.get("kind") or "artifact"),
        "path": str(record.get("path") or ""),
        "preview_path": str(record.get("preview_path") or ""),
        "row_count": int(record.get("row_count") or 0),
        "preview_rows": int(record.get("preview_rows") or 0),
    }


def update_log(logs: list[dict[str, Any]], step: str, message: str, level: str = "info") -> None:
    logs.append({"timestamp": utc_now_iso(), "level": level, "step": step, "message": message})


def notify_progress(
    progress_callback: ProgressCallback | None,
    progress: float,
    message: str,
    detail: dict[str, Any] | None = None,
) -> None:
    dispatch_progress_callback(progress_callback, progress, message, detail)

