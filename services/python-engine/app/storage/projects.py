from __future__ import annotations

from copy import deepcopy
import json
import os
import platform
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..domain.common import utc_now_iso
from ..domain.dictionary import default_dictionary_set_seed
from ..domain.import_profiles import default_import_template
from ..domain.project import default_project_manifest
from ..domain.results import empty_result_bundle
from ..domain.runtime_profile import default_runtime_profile
from ..domain.workflow import default_workflow_definition, workflow_payload_hash
from ..workflow.registry import builtin_node_definitions
from .constants import (
    CORPUS_FILENAME,
    CORPUS_VIEWS_FILENAME,
    IMPORT_TEMPLATES_DIRNAME,
    INGESTION_SPECS_FILENAME,
    PERSISTED_CORPUS_FIELDS,
    PROJECT_DATABASE_FILENAME,
    PROJECT_FILENAME,
    PROJECT_PACKAGE_EXTENSION,
    PROJECT_TEMPLATES_DIRNAME,
    RESULT_PREVIEW_DEFAULT_LIMIT,
    RESULT_PREVIEW_LIMITS,
    WORKSPACE_ENV_VAR,
    WORKSPACE_FILENAME,
)
from .database import (
    initialize_project_database,
    list_artifact_records,
    load_corpus_rows,
    load_result_bundle,
    migrate_corpus_from_json,
    replace_corpus_rows,
    replace_dictionary_set,
    replace_result_bundle,
)
from .dictionaries import (
    dictionary_entry_signature_for_storage,
    dictionary_set_manifest_reference,
    editable_dictionary_table_for_kind,
    load_dictionary_set_from_database,
    load_dictionary_set_payload,
    normalize_dictionary_set_record,
    serialize_builtin_entry_delta_for_storage,
    serialize_dictionary_collection_for_storage,
    serialize_dictionary_entry_for_storage,
    serialize_dictionary_set_for_storage,
    serialize_dictionary_table_for_storage,
)
from .io import read_json, write_json
from .workspace import (
    data_root,
    default_user_workspace_root,
    default_workspace_state,
    forget_missing_projects,
    import_templates_root,
    load_workspace_state,
    mark_workspace_bootstrapped,
    normalize_workspace_state,
    project_templates_root,
    projects_root,
    remember_project,
    remove_project_from_workspace,
    save_workspace_state,
    templates_root,
    workspace_root,
    workspace_state_path,
)
from ..workflow.runtime.support import workflow_runtime_profile





def slugify(name: str) -> str:
    lowered = name.strip().lower()
    lowered = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", lowered)
    lowered = re.sub(r"-{2,}", "-", lowered).strip("-")
    return lowered or "textflow-project"


def project_dir_from_name(name: str) -> Path:
    return projects_root() / f"{slugify(name)}.tfproj"


def ensure_unique_project_dir(name: str) -> Path:
    base_slug = slugify(name)
    candidate = projects_root() / f"{base_slug}.tfproj"
    if not candidate.exists():
        return candidate

    index = 2
    while True:
        candidate = projects_root() / f"{base_slug}-{index}.tfproj"
        if not candidate.exists():
            return candidate
        index += 1


def ensure_project_layout(project_dir: Path) -> None:
    for relative in [
        "corpus/imported",
        "dictionaries",
        "metadata",
        "runs",
        "cache",
        "exports",
    ]:
        (project_dir / relative).mkdir(parents=True, exist_ok=True)




def _result_preview_limit(result_key: str) -> int | None:
    override = os.getenv("TEXTFLOW_RESULT_PREVIEW_LIMIT")
    if override:
        try:
            return max(int(override), 0)
        except ValueError:
            return RESULT_PREVIEW_LIMITS.get(result_key, RESULT_PREVIEW_DEFAULT_LIMIT)
    return RESULT_PREVIEW_LIMITS.get(result_key, RESULT_PREVIEW_DEFAULT_LIMIT)


def compact_results_bundle(results: dict[str, Any] | None) -> dict[str, Any]:
    baseline = empty_result_bundle()
    if not isinstance(results, dict):
        return baseline

    compacted: dict[str, Any] = {}
    ordered_keys = [*baseline.keys(), *[key for key in results.keys() if key not in baseline]]
    for result_key in ordered_keys:
        value = results.get(result_key, baseline.get(result_key, []))
        if result_key == "report_files":
            compacted[result_key] = [str(item) for item in value] if isinstance(value, list) else []
            continue
        if isinstance(value, list):
            limit = _result_preview_limit(result_key)
            compacted[result_key] = deepcopy(value if limit is None else value[:limit])
            continue
        compacted[result_key] = deepcopy(value)
    return compacted


def compact_corpus_for_storage(corpus: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compacted: list[dict[str, Any]] = []
    for item in corpus:
        compacted_row = {
            key: deepcopy(item.get(key))
            for key in PERSISTED_CORPUS_FIELDS
            if key in item
        }
        compacted_row.setdefault("id", str(item.get("id") or item.get("doc_id") or ""))
        compacted_row.setdefault("doc_id", str(item.get("doc_id") or item.get("id") or ""))
        compacted_row.setdefault("source_profile", str(item.get("source_profile") or "generic"))
        compacted_row.setdefault("language", str(item.get("language") or ""))
        compacted_row.setdefault("title", str(item.get("title") or compacted_row["doc_id"]))
        compacted_row.setdefault("raw_text", str(item.get("raw_text") or ""))
        compacted_row["clean_text"] = ""
        compacted_row["normalized_text"] = ""
        compacted_row["tokens"] = []
        compacted_row["phrase_hits"] = []
        compacted_row["filtered_tokens"] = []
        compacted_row["extra_metadata"] = deepcopy(item.get("extra_metadata") if isinstance(item.get("extra_metadata"), dict) else {})
        compacted_row["status"] = str(item.get("status") or ("ready" if compacted_row["raw_text"].strip() else "warning"))
        compacted.append(compacted_row)
    return compacted


def project_relative_root(project_dir: Path) -> str:
    return project_dir.relative_to(workspace_root()).as_posix()




def refresh_manifest_paths(manifest: dict[str, Any], project_dir: Path) -> dict[str, Any]:
    manifest.setdefault("paths", {})
    manifest["paths"].update(
        {
            "root": project_relative_root(project_dir),
            "corpus_dir": "corpus",
            "dictionaries_dir": "dictionaries",
            "runs_dir": "runs",
            "cache_dir": "cache",
            "exports_dir": "exports",
        }
    )
    return manifest


def normalize_import_template_record(import_template: dict[str, Any] | None) -> dict[str, Any]:
    source_profile = str((import_template or {}).get("source_profile") or "generic")
    baseline = default_import_template(source_profile)
    if not isinstance(import_template, dict):
        return baseline

    normalized = deepcopy(baseline)
    for key, value in import_template.items():
        if key == "text_build" and isinstance(value, dict):
            normalized["text_build"].update(value)
            continue
        normalized[key] = value

    if not isinstance(normalized.get("field_mappings"), list):
        normalized["field_mappings"] = baseline["field_mappings"]
    return normalized




def result_bundle_manifest_reference(project_dir: Path, results: dict[str, Any]) -> dict[str, Any]:
    keys: dict[str, Any] = {}
    for key, value in normalize_results_bundle(results).items():
        if isinstance(value, list):
            row_count = len(value)
            preview_rows = min(row_count, 50)
        else:
            row_count = 1 if value not in (None, "") else 0
            preview_rows = row_count
        keys[str(key)] = {"row_count": row_count, "preview_rows": preview_rows}
    return {"storage": "project.db", "table": "result_tables", "keys": keys}


def load_results_payload(project_dir: Path, manifest: dict[str, Any]) -> dict[str, Any] | None:
    db_path = project_dir / PROJECT_DATABASE_FILENAME
    if db_path.exists():
        db = initialize_project_database(db_path)
        results = load_result_bundle(db)
        if results is not None:
            return results
    manifest_results = manifest.get("results")
    if isinstance(manifest_results, dict) and manifest_results.get("storage") == "project.db":
        return None
    return manifest_results if isinstance(manifest_results, dict) else None




def write_project_payload(
    project_dir: Path,
    manifest: dict[str, Any],
    corpus: list[dict[str, Any]],
    *,
    dirty_sections: set[str] | None = None,
) -> None:
    baseline_manifest = default_project_manifest(
        str(manifest.get("name") or project_dir.stem),
        str(manifest.get("description") or ""),
        project_relative_root(project_dir),
        include_dictionary_set=False,
    )
    storage_manifest: dict[str, Any] = {}
    for key, value in baseline_manifest.items():
        if key == "dictionary_set":
            continue
        if key == "results":
            storage_manifest[key] = result_bundle_manifest_reference(
                project_dir,
                manifest.get("results") if isinstance(manifest.get("results"), dict) else value,
            )
            continue
        if key == "artifact_records":
            storage_manifest[key] = {
                "storage": "project.db",
                "table": "artifacts",
                "current_run_artifact_count": len(
                    manifest.get("artifact_records") if isinstance(manifest.get("artifact_records"), list) else []
                ),
            }
            continue
        storage_manifest[key] = deepcopy(manifest[key]) if key in manifest else deepcopy(value)
    serialized_dictionary_set = serialize_dictionary_set_for_storage(manifest.get("dictionary_set"))
    storage_manifest["dictionary_set"] = dictionary_set_manifest_reference(
        manifest.get("dictionary_set") if isinstance(manifest.get("dictionary_set"), dict) else serialized_dictionary_set
    )
    storage_manifest["incremental_state"] = deepcopy(
        manifest.get("incremental_state") if isinstance(manifest.get("incremental_state"), dict) else {}
    )
    storage_manifest["document_count"] = len(corpus)
    storage_manifest["run_count"] = len(storage_manifest.get("run_history", []))
    normalized_dirty = {str(item) for item in dirty_sections} if dirty_sections is not None else None

    if normalized_dirty is None or "manifest" in normalized_dirty:
        write_json(project_dir / PROJECT_FILENAME, storage_manifest)
    if normalized_dirty is None or "corpus" in normalized_dirty:
        db_path = project_dir / PROJECT_DATABASE_FILENAME
        db = initialize_project_database(db_path)
        replace_corpus_rows(db, compact_corpus_for_storage(corpus))
        if (project_dir / CORPUS_FILENAME).exists():
            (project_dir / CORPUS_FILENAME).unlink()
    if normalized_dirty is None or "import_template" in normalized_dirty:
        write_json(project_dir / "metadata/import_template.json", manifest["import_template"])
    if normalized_dirty is None or "dictionary_set" in normalized_dirty:
        db_path = project_dir / PROJECT_DATABASE_FILENAME
        db = initialize_project_database(db_path)
        replace_dictionary_set(db, manifest.get("dictionary_set") or default_dictionary_set_seed())
        for path in (project_dir / "dictionaries").glob("*.json"):
            try:
                path.unlink()
            except OSError:
                pass
    if normalized_dirty is None or "results" in normalized_dirty or "manifest" in normalized_dirty:
        db_path = project_dir / PROJECT_DATABASE_FILENAME
        db = initialize_project_database(db_path)
        replace_result_bundle(db, normalize_results_bundle(manifest.get("results")))
    if normalized_dirty is None or "corpus_views" in normalized_dirty:
        write_json(project_dir / CORPUS_VIEWS_FILENAME, storage_manifest.get("corpus_views", []))
    if normalized_dirty is None or "ingestion_specs" in normalized_dirty:
        write_json(project_dir / INGESTION_SPECS_FILENAME, storage_manifest.get("ingestion_specs", []))


def normalize_workflow_definition_record(
    workflow_definition: dict[str, Any] | None,
    runtime_profile: dict[str, Any],
    *,
    source: str = "manual",
) -> dict[str, Any]:
    baseline = default_workflow_definition(
        runtime_profile,
        source=source,
    )
    if not isinstance(workflow_definition, dict):
        return baseline

    normalized = deepcopy(baseline)
    for key, value in workflow_definition.items():
        if key == "meta" and isinstance(value, dict):
            normalized["meta"].update(value)
            continue
        if key == "viewport" and isinstance(value, dict):
            normalized["viewport"].update(value)
            continue
        normalized[key] = value

    if not isinstance(normalized.get("nodes"), list):
        normalized["nodes"] = baseline["nodes"]
    if not isinstance(normalized.get("edges"), list):
        normalized["edges"] = baseline["edges"]
    if not isinstance(normalized.get("groups"), list):
        normalized["groups"] = baseline["groups"]
    if not isinstance(normalized.get("meta"), dict):
        normalized["meta"] = deepcopy(baseline["meta"])
    else:
        normalized["meta"] = {
            **deepcopy(baseline["meta"]),
            **normalized["meta"],
        }
    if not isinstance(normalized.get("viewport"), dict):
        normalized["viewport"] = deepcopy(baseline["viewport"])
    else:
        normalized["viewport"] = {
            **deepcopy(baseline["viewport"]),
            **normalized["viewport"],
        }

    normalized["workflow_id"] = str(normalized.get("workflow_id") or baseline["workflow_id"])
    normalized["name"] = str(normalized.get("name") or baseline["name"])
    normalized["version"] = str(normalized.get("version") or baseline["version"])
    normalized["graph_mode"] = str(normalized.get("graph_mode") or baseline["graph_mode"])
    normalized["source"] = str(normalized.get("source") or source)
    normalized["created_at"] = str(normalized.get("created_at") or baseline["created_at"])
    normalized["updated_at"] = str(normalized.get("updated_at") or baseline["updated_at"])
    normalized["meta"]["template_id"] = str(normalized["meta"].get("template_id") or runtime_profile.get("recipe_id") or "standard_analysis")
    normalized["meta"]["output_bundle_id"] = str(
        normalized["meta"].get("output_bundle_id") or runtime_profile.get("output_bundle_id") or "full_report"
    )
    return normalized


def normalize_workflow_definitions(
    workflow_definitions: list[dict[str, Any]] | None,
    runtime_profile: dict[str, Any],
) -> list[dict[str, Any]]:
    if not isinstance(workflow_definitions, list) or not workflow_definitions:
        return [default_workflow_definition(runtime_profile)]

    normalized: list[dict[str, Any]] = []
    seen_workflow_ids: set[str] = set()
    for item in workflow_definitions:
        if not isinstance(item, dict):
            continue
        workflow = normalize_workflow_definition_record(item, runtime_profile)
        workflow_id = workflow["workflow_id"]
        if workflow_id in seen_workflow_ids:
            continue
        seen_workflow_ids.add(workflow_id)
        normalized.append(workflow)

    if not normalized:
        return [default_workflow_definition(runtime_profile)]
    return normalized


def resolve_active_workflow(
    workflow_definitions: list[dict[str, Any]],
    active_workflow_id: str | None,
) -> tuple[str, dict[str, Any]]:
    lookup = {
        str(workflow["workflow_id"]): workflow
        for workflow in workflow_definitions
        if isinstance(workflow, dict) and workflow.get("workflow_id")
    }
    if active_workflow_id and active_workflow_id in lookup:
        return active_workflow_id, lookup[active_workflow_id]
    first_workflow = workflow_definitions[0]
    return str(first_workflow["workflow_id"]), first_workflow


def normalize_results_bundle(results: dict[str, Any] | None) -> dict[str, Any]:
    baseline = empty_result_bundle()
    if not isinstance(results, dict):
        return baseline
    normalized = deepcopy(baseline)
    for key, value in results.items():
        normalized[key] = value
    return normalized


def normalize_manifest_record_list(records: Any) -> list[Any]:
    if not isinstance(records, list):
        return []
    return [deepcopy(item) for item in records]


def default_run_scope_summary(document_count: int) -> str:
    return f"处理对象：项目内全部资料（共 {document_count} 篇）"


def default_output_summary(export_settings: dict[str, Any] | None) -> str:
    export_config = export_settings if isinstance(export_settings, dict) else {}
    outputs: list[str] = []
    if export_config.get("export_csv"):
        outputs.append("CSV 表格")
    if export_config.get("export_xlsx"):
        outputs.append("XLSX 汇总包")
    if export_config.get("export_png"):
        outputs.append("PNG 图表")
    if export_config.get("export_html_report"):
        outputs.append("HTML 报告")
    return "、".join(outputs) if outputs else "仅更新项目内结果快照"


def normalize_run_record(
    run_record: dict[str, Any] | None,
    workflow_definition: dict[str, Any],
    corpus: list[dict[str, Any]],
) -> dict[str, Any]:
    normalized = deepcopy(run_record) if isinstance(run_record, dict) else {}
    runtime_profile = workflow_runtime_profile(workflow_definition)
    processed_document_count = normalized.get("processed_document_count")
    if not isinstance(processed_document_count, int):
        processed_document_count = len(corpus)
    normalized["processed_document_count"] = processed_document_count
    normalized["run_scope_summary"] = str(
        normalized.get("run_scope_summary") or default_run_scope_summary(processed_document_count)
    )
    normalized["recipe_id"] = str(normalized.get("recipe_id") or runtime_profile.get("recipe_id") or "standard_analysis")
    normalized["output_bundle_id"] = str(
        normalized.get("output_bundle_id") or runtime_profile.get("output_bundle_id") or "full_report"
    )
    normalized["output_summary"] = str(
        normalized.get("output_summary") or default_output_summary(runtime_profile.get("export"))
    )
    normalized["workflow_version"] = str(
        normalized.get("workflow_version")
        or workflow_definition.get("version")
        or "1.0.0"
    )
    normalized["workflow_id"] = str(
        normalized.get("workflow_id") or workflow_definition.get("workflow_id") or "wf-default"
    )
    normalized["workflow_name"] = str(
        normalized.get("workflow_name") or workflow_definition.get("name") or "默认工作流"
    )
    normalized["workflow_hash"] = str(
        normalized.get("workflow_hash") or workflow_payload_hash(workflow_definition)
    )
    normalized.setdefault("warnings", [])
    normalized.setdefault("errors", [])
    normalized.setdefault("logs", [])
    normalized.setdefault("artifacts", [])
    allowed_keys = [
        "run_id",
        "project_id",
        "workflow_version",
        "workflow_id",
        "workflow_name",
        "workflow_hash",
        "dictionary_version",
        "started_at",
        "ended_at",
        "status",
        "warnings",
        "errors",
        "logs",
        "artifacts",
        "node_runs",
        "params_snapshot_path",
        "processed_document_count",
        "run_scope_summary",
        "recipe_id",
        "output_bundle_id",
        "output_summary",
        "experiment_id",
        "experiment_name",
        "variant_label",
        "variant_index",
        "variant_overrides",
        "run_mode",
        "incremental_scope",
        "dirty_node_ids",
        "invalidated_artifact_count",
    ]
    return {
        key: normalized[key]
        for key in allowed_keys
        if key in normalized
    }


def normalize_project_manifest(
    manifest: dict[str, Any] | None,
    corpus: list[dict[str, Any]],
    project_dir: Path,
) -> dict[str, Any]:
    payload = manifest if isinstance(manifest, dict) else {}
    name = str(payload.get("name") or project_dir.stem)
    description = str(payload.get("description") or "")
    baseline = default_project_manifest(
        name,
        description,
        project_relative_root(project_dir),
        include_dictionary_set=False,
    )
    normalized = deepcopy(baseline)
    passthrough_keys = {
        key
        for key in baseline.keys()
        if key not in {
            "settings",
            "paths",
            "import_template",
            "dictionary_set",
            "workflow_definitions",
            "active_workflow_id",
            "results",
            "run_history",
        }
    }
    for key in passthrough_keys:
        if key in payload:
            normalized[key] = payload[key]

    normalized["settings"].update(payload.get("settings", {}) if isinstance(payload.get("settings"), dict) else {})
    path_payload = payload.get("paths") if isinstance(payload.get("paths"), dict) else {}
    for key in baseline["paths"].keys():
        if key in path_payload:
            normalized["paths"][key] = path_payload[key]
    normalized["import_template"] = normalize_import_template_record(payload.get("import_template"))
    normalized["dictionary_set"] = normalize_dictionary_set_record(payload.get("dictionary_set"))
    workflow_definitions = normalize_workflow_definitions(payload.get("workflow_definitions"), default_runtime_profile())
    active_workflow_id, active_workflow = resolve_active_workflow(
        workflow_definitions,
        str(payload.get("active_workflow_id")) if payload.get("active_workflow_id") else None,
    )
    normalized["workflow_definitions"] = workflow_definitions
    normalized["active_workflow_id"], active_workflow = resolve_active_workflow(
        normalized["workflow_definitions"],
        active_workflow_id,
    )
    normalized["results"] = normalize_results_bundle(payload.get("results"))
    normalized["run_history"] = [
        normalize_run_record(run_record, active_workflow, corpus)
        for run_record in payload.get("run_history", [])
        if isinstance(run_record, dict)
    ]
    normalized["corpus_resources"] = normalize_manifest_record_list(payload.get("corpus_resources"))
    normalized["corpus_views"] = normalize_manifest_record_list(payload.get("corpus_views"))
    normalized["ingestion_specs"] = normalize_manifest_record_list(payload.get("ingestion_specs"))
    normalized["artifact_records"] = normalize_manifest_record_list(payload.get("artifact_records"))
    normalized["review_tasks"] = normalize_manifest_record_list(payload.get("review_tasks"))
    normalized["experiment_specs"] = normalize_manifest_record_list(payload.get("experiment_specs"))
    normalized["shared_resource_refs"] = normalize_manifest_record_list(payload.get("shared_resource_refs"))
    normalized["incremental_state"] = deepcopy(
        payload.get("incremental_state") if isinstance(payload.get("incremental_state"), dict) else {}
    )
    refresh_manifest_paths(normalized, project_dir)
    return normalized


def create_project(name: str, description: str) -> tuple[Path, dict[str, Any]]:
    project_dir = ensure_unique_project_dir(name)
    ensure_project_layout(project_dir)
    manifest = default_project_manifest(name, description, project_relative_root(project_dir))
    write_project_payload(project_dir, manifest, [])
    return project_dir, manifest


def build_project_template(
    manifest: dict[str, Any],
    name: str | None = None,
    description: str | None = None,
    template_id: str | None = None,
) -> dict[str, Any]:
    timestamp = utc_now_iso()
    return {
        "id": template_id or f"project-template-{uuid_suffix()}",
        "name": name or f"{manifest['name']} 模板",
        "description": description or manifest.get("description", ""),
        "source_profile": manifest["import_template"].get("source_profile", "generic"),
        "settings": deepcopy(manifest.get("settings", {})),
        "workflow_definitions": deepcopy(manifest.get("workflow_definitions", [])),
        "active_workflow_id": manifest.get("active_workflow_id"),
        "dictionary_set": serialize_dictionary_set_for_storage(manifest.get("dictionary_set")),
        "import_template": deepcopy(manifest["import_template"]),
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def create_project_from_template(
    name: str,
    description: str,
    template_payload: dict[str, Any],
) -> tuple[Path, dict[str, Any]]:
    project_dir, manifest = create_project(name, description or template_payload.get("description", ""))
    if template_payload.get("settings"):
        manifest["settings"] = deepcopy(template_payload["settings"])
    if template_payload.get("workflow_definitions"):
        manifest["workflow_definitions"] = deepcopy(template_payload["workflow_definitions"])
    if template_payload.get("active_workflow_id"):
        manifest["active_workflow_id"] = template_payload["active_workflow_id"]
    manifest["dictionary_set"] = deepcopy(template_payload["dictionary_set"])
    manifest["import_template"] = deepcopy(template_payload["import_template"])
    save_project(project_dir, manifest, [])
    return project_dir, manifest




def save_project(
    project_dir: Path,
    manifest: dict[str, Any],
    corpus: list[dict[str, Any]],
    *,
    already_normalized: bool = False,
    dirty_sections: set[str] | None = None,
) -> None:
    ensure_project_layout(project_dir)
    if not already_normalized:
        manifest = normalize_project_manifest(manifest, corpus, project_dir)
    manifest["updated_at"] = utc_now_iso()
    resolved_dirty_sections = {str(section) for section in dirty_sections} if dirty_sections is not None else None
    if resolved_dirty_sections is not None:
        resolved_dirty_sections.add("manifest")
    write_project_payload(project_dir, manifest, corpus, dirty_sections=resolved_dirty_sections)


def load_project(project_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = read_json(project_dir / PROJECT_FILENAME)
    db_path = project_dir / PROJECT_DATABASE_FILENAME
    corpus: list[dict[str, Any]] = []
    if db_path.exists():
        db = initialize_project_database(db_path)
        corpus = load_corpus_rows(db)
    elif (project_dir / CORPUS_FILENAME).exists():
        corpus = read_json(project_dir / CORPUS_FILENAME)
        db = initialize_project_database(db_path)
        migrate_corpus_from_json(db, corpus)
        (project_dir / CORPUS_FILENAME).unlink()
    if (project_dir / CORPUS_VIEWS_FILENAME).exists():
        manifest["corpus_views"] = read_json(project_dir / CORPUS_VIEWS_FILENAME)
    if (project_dir / INGESTION_SPECS_FILENAME).exists():
        manifest["ingestion_specs"] = read_json(project_dir / INGESTION_SPECS_FILENAME)
    dictionary_set_payload = load_dictionary_set_payload(project_dir, manifest)
    if dictionary_set_payload is not None:
        manifest["dictionary_set"] = dictionary_set_payload
    results_payload = load_results_payload(project_dir, manifest)
    if results_payload is not None:
        manifest["results"] = results_payload
    if db_path.exists():
        db = initialize_project_database(db_path)
        artifact_records = list_artifact_records(db)
        if artifact_records:
            manifest["artifact_records"] = artifact_records
    manifest = normalize_project_manifest(manifest, corpus, project_dir)
    return manifest, corpus


def find_project_dir(project_id: str) -> Path | None:
    for project_dir in list_project_dirs():
        manifest_path = project_dir / PROJECT_FILENAME
        if manifest_path.exists():
            manifest = read_json(manifest_path)
            if manifest.get("id") == project_id:
                return project_dir
    return None


def list_project_dirs() -> list[Path]:
    return sorted(
        [
            path
            for path in projects_root().glob("*.tfproj")
            if path.is_dir()
        ]
    )


def delete_project(project_id: str) -> dict[str, Any]:
    project_dir = find_project_dir(project_id)
    if project_dir is None:
        raise ValueError(f"Project {project_id} not found")

    deleted_path = str(project_dir)
    db_path = project_dir / PROJECT_DATABASE_FILENAME
    if db_path.exists():
        try:
            db = initialize_project_database(db_path)
            conn = db.connect()
            try:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                conn.execute("PRAGMA journal_mode=DELETE")
                conn.commit()
            finally:
                conn.close()
        except Exception:
            pass
    import gc
    gc.collect()
    for _ in range(5):
        shutil.rmtree(project_dir, ignore_errors=True)
        if not project_dir.exists():
            break
        import time
        time.sleep(0.1)
    remove_project_from_workspace(project_id)
    return {
        "project_id": project_id,
        "deleted_path": deleted_path,
    }




def build_project_summary(
    project_dir: Path,
    manifest: dict[str, Any],
    corpus: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    document_count = len(corpus) if isinstance(corpus, list) else int(manifest.get("document_count", 0) or 0)
    run_count = int(manifest.get("run_count", 0) or len(manifest.get("run_history", [])))
    return {
        "id": manifest["id"],
        "name": manifest["name"],
        "description": manifest["description"],
        "path": str(project_dir),
        "updated_at": manifest["updated_at"],
        "document_count": document_count,
        "run_count": run_count,
    }


def infer_legacy_document_count(project_dir: Path) -> int:
    db_path = project_dir / PROJECT_DATABASE_FILENAME
    if db_path.exists():
        try:
            db = initialize_project_database(db_path)
            conn = db.connect()
            try:
                cursor = conn.execute("SELECT COUNT(*) FROM corpus_documents")
                result = cursor.fetchone()
                return int(result[0]) if result else 0
            finally:
                conn.close()
        except Exception:
            pass
    corpus_path = project_dir / CORPUS_FILENAME
    if not corpus_path.exists():
        return 0
    try:
        payload = read_json(corpus_path)
    except Exception:
        return 0
    return len(payload) if isinstance(payload, list) else 0


def backfill_manifest_summary_fields(project_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    next_manifest = manifest
    changed = False

    if "document_count" not in next_manifest:
        next_manifest["document_count"] = infer_legacy_document_count(project_dir)
        changed = True

    if "run_count" not in next_manifest:
        next_manifest["run_count"] = len(next_manifest.get("run_history", []))
        changed = True

    if changed:
        write_json(project_dir / PROJECT_FILENAME, next_manifest)

    return next_manifest




def uuid_suffix() -> str:
    return uuid4().hex[:12]


def load_workspace_snapshot() -> dict[str, Any]:
    project_records: dict[str, tuple[Path, dict[str, Any]]] = {}

    for project_dir in list_project_dirs():
        manifest_path = project_dir / PROJECT_FILENAME
        if not manifest_path.exists():
            continue
        manifest = read_json(manifest_path)
        manifest = backfill_manifest_summary_fields(project_dir, manifest)
        project_id = str(manifest.get("id") or "")
        if not project_id:
            continue
        summary = build_project_summary(project_dir, manifest)
        project_records[project_id] = (project_dir, summary)

    state = forget_missing_projects(set(project_records))
    recent_projects: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for project_id in state["recent_project_ids"]:
        if project_id in project_records:
            recent_projects.append(project_records[project_id][1])
            seen_ids.add(project_id)

    remaining_summaries = [
        record[1]
        for project_id, record in project_records.items()
        if project_id not in seen_ids
    ]
    remaining_summaries.sort(key=lambda item: item["updated_at"], reverse=True)
    recent_projects.extend(remaining_summaries)

    current_project = None
    current_corpus: list[dict[str, Any]] = []
    selected_run = None
    current_project_id = state.get("current_project_id")

    if (current_project_id is None or current_project_id not in project_records) and recent_projects:
        current_project_id = recent_projects[0]["id"]
        state = remember_project(current_project_id, set_current=True)

    if current_project_id and current_project_id in project_records:
        project_dir, _summary = project_records[current_project_id]
        manifest, corpus = load_project(project_dir)
        current_project = manifest
        current_corpus = corpus
        history = manifest.get("run_history", [])
        selected_run = history[-1] if history else None

    return {
        "recent_projects": recent_projects,
        "current_project": current_project,
        "corpus": current_corpus,
        "selected_run": selected_run,
        "node_definitions": builtin_node_definitions(),
    }
