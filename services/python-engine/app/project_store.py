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

from .defaults import (
    build_dictionary_sheets_from_collections,
    default_dictionary_set,
    default_dictionary_set_seed,
    default_import_template,
    default_runtime_profile,
    default_project_manifest,
    default_workflow_definition,
    empty_result_bundle,
    utc_now_iso,
    workflow_payload_hash,
)
from .node_registry import builtin_node_definitions
from .runtime_support import workflow_runtime_profile

PROJECT_FILENAME = "project.json"
CORPUS_FILENAME = "metadata/corpus.json"
WORKSPACE_FILENAME = "workspace.json"
WORKSPACE_ENV_VAR = "TEXTFLOW_WORKSPACE_ROOT"
PROJECT_TEMPLATES_DIRNAME = "project_templates"
IMPORT_TEMPLATES_DIRNAME = "import_templates"
PROJECT_PACKAGE_EXTENSION = ".tfproj"


def default_user_workspace_root() -> Path:
    system = platform.system().lower()
    if system == "windows":
        base = Path(os.getenv("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return base / "TextFlow Studio"
    if system == "darwin":
        return Path.home() / "Library" / "Application Support" / "TextFlow Studio"
    return Path(os.getenv("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "textflow-studio"


def workspace_root() -> Path:
    configured_root = os.getenv(WORKSPACE_ENV_VAR)
    if configured_root:
        root = Path(configured_root)
    else:
        root = default_user_workspace_root()
    root.mkdir(parents=True, exist_ok=True)
    return root


def projects_root() -> Path:
    root = workspace_root() / "projects"
    root.mkdir(parents=True, exist_ok=True)
    return root


def data_root() -> Path:
    root = workspace_root() / "data"
    root.mkdir(parents=True, exist_ok=True)
    return root


def templates_root() -> Path:
    root = workspace_root() / "templates"
    root.mkdir(parents=True, exist_ok=True)
    return root


def project_templates_root() -> Path:
    root = templates_root() / PROJECT_TEMPLATES_DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def import_templates_root() -> Path:
    root = templates_root() / IMPORT_TEMPLATES_DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def workspace_state_path() -> Path:
    return projects_root() / WORKSPACE_FILENAME


def default_workspace_state() -> dict[str, Any]:
    return {
        "version": "1.0.0",
        "current_project_id": None,
        "recent_project_ids": [],
        "bootstrap_completed": False,
    }


def normalize_workspace_state(state: dict[str, Any] | None) -> dict[str, Any]:
    normalized = default_workspace_state()
    if not state:
        return normalized

    normalized["version"] = state.get("version", normalized["version"])
    normalized["current_project_id"] = state.get("current_project_id")
    normalized["recent_project_ids"] = [
        str(project_id)
        for project_id in state.get("recent_project_ids", [])
        if project_id
    ]
    normalized["bootstrap_completed"] = bool(state.get("bootstrap_completed", False))
    return normalized


def load_workspace_state() -> dict[str, Any]:
    path = workspace_state_path()
    if not path.exists():
        return default_workspace_state()
    return normalize_workspace_state(read_json(path))


def save_workspace_state(state: dict[str, Any]) -> None:
    write_json(workspace_state_path(), normalize_workspace_state(state))


def remember_project(project_id: str, set_current: bool = False) -> dict[str, Any]:
    state = load_workspace_state()
    recent = [item for item in state["recent_project_ids"] if item != project_id]
    recent.insert(0, project_id)
    state["recent_project_ids"] = recent[:24]
    if set_current:
        state["current_project_id"] = project_id
    save_workspace_state(state)
    return state


def remove_project_from_workspace(project_id: str) -> dict[str, Any]:
    state = load_workspace_state()
    state["recent_project_ids"] = [item for item in state["recent_project_ids"] if item != project_id]
    if state["current_project_id"] == project_id:
        state["current_project_id"] = state["recent_project_ids"][0] if state["recent_project_ids"] else None
    save_workspace_state(state)
    return state


def mark_workspace_bootstrapped() -> dict[str, Any]:
    state = load_workspace_state()
    state["bootstrap_completed"] = True
    save_workspace_state(state)
    return state


def forget_missing_projects(valid_project_ids: set[str]) -> dict[str, Any]:
    state = load_workspace_state()
    state["recent_project_ids"] = [item for item in state["recent_project_ids"] if item in valid_project_ids]
    if state["current_project_id"] not in valid_project_ids:
        state["current_project_id"] = state["recent_project_ids"][0] if state["recent_project_ids"] else None
    save_workspace_state(state)
    return state


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


def write_json(path: Path, data: Any) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(data, ensure_ascii=False, indent=2)
    if path.exists():
        try:
            if path.read_text(encoding="utf-8") == serialized:
                return False
        except OSError:
            pass
    path.write_text(serialized, encoding="utf-8")
    return True


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def project_relative_root(project_dir: Path) -> str:
    return project_dir.relative_to(workspace_root()).as_posix()


def template_path(root: Path, template_id: str) -> Path:
    return root / f"{template_id}.json"


def list_templates(root: Path) -> list[dict[str, Any]]:
    templates: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        payload = read_json(path)
        if isinstance(payload, dict):
            templates.append(payload)
    templates.sort(key=lambda item: (item.get("updated_at", ""), item.get("name", "")), reverse=True)
    return templates


def load_template(root: Path, template_id: str) -> dict[str, Any]:
    path = template_path(root, template_id)
    if not path.exists():
        raise ValueError(f"Template {template_id} not found")
    payload = read_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid template payload: {path}")
    return payload


def save_template(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    record = deepcopy(payload)
    timestamp = utc_now_iso()
    record.setdefault("created_at", timestamp)
    record["updated_at"] = timestamp
    write_json(template_path(root, str(record["id"])), record)
    return record


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


def normalize_dictionary_set_record(dictionary_set: dict[str, Any] | None) -> dict[str, Any]:
    def is_hydrated_dictionary_set(
        payload: dict[str, Any],
        baseline_payload: dict[str, Any],
    ) -> bool:
        collections = payload.get("collections")
        sheets = payload.get("sheets")
        if not isinstance(collections, dict) or not isinstance(sheets, dict):
            return False
        for kind, baseline_collection in baseline_payload.get("collections", {}).items():
            collection = collections.get(kind)
            sheet = sheets.get(kind)
            if not isinstance(collection, dict) or not isinstance(sheet, dict):
                return False
            baseline_tables = baseline_collection.get("tables", [])
            tables = collection.get("tables")
            if not isinstance(tables, list) or len(tables) < len(baseline_tables):
                return False
            if not isinstance(sheet.get("entries"), list):
                return False
            for table in tables:
                if not isinstance(table, dict) or not isinstance(table.get("entries"), list):
                    return False
        return True

    def entry_signature(entry: dict[str, Any], fallback_key: str) -> str:
        source = str(entry.get("source") or "").strip()
        target = str(entry.get("target") or "").strip()
        if not source:
            return fallback_key
        return f"{source.casefold()}::{target.casefold()}"

    def merge_sheet_entries(
        baseline_entries: list[dict[str, Any]],
        provided_entries: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        merged_entries = [deepcopy(entry) for entry in baseline_entries if isinstance(entry, dict)]
        signature_to_index = {
            entry_signature(entry, f"baseline::{index}"): index
            for index, entry in enumerate(merged_entries)
        }
        for index, entry in enumerate(provided_entries):
            if not isinstance(entry, dict):
                continue
            normalized_entry = deepcopy(entry)
            signature = entry_signature(normalized_entry, f"provided::{index}")
            existing_index = signature_to_index.get(signature)
            if existing_index is None:
                signature_to_index[signature] = len(merged_entries)
                merged_entries.append(normalized_entry)
                continue
            baseline_entry = merged_entries[existing_index]
            merged_entries[existing_index] = {
                **baseline_entry,
                **normalized_entry,
                "id": normalized_entry.get("id") or baseline_entry.get("id"),
            }
        return merged_entries

    def normalize_table_payload(
        kind: str,
        payload: dict[str, Any],
        *,
        fallback_id: str,
        fallback_name: str,
    ) -> dict[str, Any]:
        table = deepcopy(payload)
        table["id"] = str(table.get("id") or fallback_id)
        table["kind"] = kind
        table["name"] = str(table.get("name") or fallback_name)
        table["version"] = str(table.get("version") or "2.0.0")
        table["description"] = str(table.get("description") or "")
        source_url = table.get("source_url")
        table["source_url"] = str(source_url) if source_url else None
        table["built_in"] = bool(table.get("built_in", False))
        table["editable"] = bool(table.get("editable", not table["built_in"]))
        table["enabled"] = bool(table.get("enabled", True))
        table["tags"] = [str(tag) for tag in table.get("tags", []) if str(tag).strip()]
        table["entries"] = merge_sheet_entries([], table.get("entries", []) if isinstance(table.get("entries"), list) else [])
        return table

    def merge_table_lists(
        kind: str,
        baseline_tables: list[dict[str, Any]],
        provided_tables: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        merged_tables = [
            normalize_table_payload(
                kind,
                table,
                fallback_id=f"{kind}-baseline-{index}",
                fallback_name=str(table.get("name") or f"{kind} {index + 1}"),
            )
            for index, table in enumerate(baseline_tables)
            if isinstance(table, dict)
        ]
        id_to_index = {str(table.get("id") or f"{kind}-baseline-{index}"): index for index, table in enumerate(merged_tables)}

        for index, payload in enumerate(provided_tables):
            if not isinstance(payload, dict):
                continue
            table_id = str(payload.get("id") or f"{kind}-imported-{index}")
            existing_index = id_to_index.get(table_id)
            if existing_index is None:
                merged_tables.append(
                    normalize_table_payload(
                        kind,
                        payload,
                        fallback_id=table_id,
                        fallback_name=str(payload.get("name") or f"{kind} 导入资源"),
                    )
                )
                id_to_index[table_id] = len(merged_tables) - 1
                continue

            baseline_table = merged_tables[existing_index]
            merged_table = {
                **baseline_table,
                **deepcopy(payload),
                "id": table_id,
                "kind": kind,
            }
            merged_table["entries"] = merge_sheet_entries(
                baseline_table.get("entries", []) if isinstance(baseline_table.get("entries"), list) else [],
                payload.get("entries", []) if isinstance(payload.get("entries"), list) else [],
            )
            merged_tables[existing_index] = normalize_table_payload(
                kind,
                merged_table,
                fallback_id=table_id,
                fallback_name=str(merged_table.get("name") or baseline_table.get("name") or f"{kind} 资源"),
            )
        return merged_tables

    def ensure_project_table(collection: dict[str, Any], kind: str) -> dict[str, Any]:
        tables = collection.setdefault("tables", [])
        if not isinstance(tables, list):
            tables = []
            collection["tables"] = tables
        for index, table in enumerate(tables):
            if not isinstance(table, dict):
                continue
            if table.get("built_in"):
                continue
            if table.get("editable", True):
                tables[index] = normalize_table_payload(
                    kind,
                    table,
                    fallback_id=f"{kind}-project-custom",
                    fallback_name="项目自定义",
                )
                return tables[index]
        project_table = normalize_table_payload(
            kind,
            {
                "id": f"{kind}-project-custom",
                "kind": kind,
                "name": "项目自定义",
                "version": "2.0.0",
                "description": "从旧版项目或手工录入迁移而来的可编辑资源。",
                "built_in": False,
                "editable": True,
                "enabled": True,
                "tags": [],
                "entries": [],
            },
            fallback_id=f"{kind}-project-custom",
            fallback_name="项目自定义",
        )
        tables.insert(0, project_table)
        return project_table

    baseline = default_dictionary_set_seed()
    if not isinstance(dictionary_set, dict):
        return baseline
    if is_hydrated_dictionary_set(dictionary_set, baseline):
        dictionary_set["id"] = str(dictionary_set.get("id") or baseline.get("id") or "dict-default")
        dictionary_set["name"] = str(dictionary_set.get("name") or baseline.get("name") or "默认词表集")
        dictionary_set["version"] = str(dictionary_set.get("version") or baseline.get("version") or "2.0.0")
        dictionary_set["bound_to_project"] = bool(dictionary_set.get("bound_to_project", baseline.get("bound_to_project", True)))
        return dictionary_set

    normalized = deepcopy(baseline)
    for key, value in dictionary_set.items():
        if key not in {"sheets", "collections"}:
            normalized[key] = value

    provided_collections = dictionary_set.get("collections", {})
    if isinstance(provided_collections, dict):
        for kind, payload in provided_collections.items():
            if kind in normalized["collections"] and isinstance(payload, dict):
                merged_collection = deepcopy(normalized["collections"][kind])
                for field, value in payload.items():
                    if field == "tables" and isinstance(value, list):
                        merged_collection["tables"] = merge_table_lists(kind, merged_collection.get("tables", []), value)
                        continue
                    merged_collection[field] = value
                normalized["collections"][kind] = merged_collection
                continue
            if isinstance(payload, dict):
                normalized["collections"][kind] = {
                    **deepcopy(payload),
                    "kind": kind,
                    "tables": merge_table_lists(kind, [], payload.get("tables", []) if isinstance(payload.get("tables"), list) else []),
                }

    provided_sheets = dictionary_set.get("sheets", {})
    if isinstance(provided_sheets, dict):
        for kind, payload in provided_sheets.items():
            if kind not in normalized["collections"] or not isinstance(payload, dict):
                continue
            collection_payload = provided_collections.get(kind) if isinstance(provided_collections, dict) else None
            if isinstance(collection_payload, dict) and isinstance(collection_payload.get("tables"), list) and collection_payload["tables"]:
                continue
            project_table = ensure_project_table(normalized["collections"][kind], kind)
            if isinstance(payload.get("entries"), list):
                project_table["entries"] = merge_sheet_entries(
                    project_table.get("entries", []) if isinstance(project_table.get("entries"), list) else [],
                    payload["entries"],
                )

    normalized["sheets"] = build_dictionary_sheets_from_collections(normalized.get("collections", {}))
    return normalized


def dictionary_entry_signature_for_storage(entry: dict[str, Any], fallback_key: str) -> str:
    source = str(entry.get("source") or "").strip()
    target = entry.get("target")
    if not source:
        return fallback_key
    normalized_target = str(target).strip().casefold() if isinstance(target, str) else ""
    return f"{source.casefold()}::{normalized_target}"


def serialize_dictionary_entry_for_storage(entry: dict[str, Any]) -> dict[str, Any]:
    tags = [str(tag) for tag in entry.get("tags", []) if str(tag).strip()]
    return {
        "id": entry.get("id"),
        "source": str(entry.get("source") or ""),
        "target": entry.get("target"),
        "tags": tags,
        "enabled": bool(entry.get("enabled", True)),
        "hits": int(entry.get("hits", 0) or 0),
        "notes": str(entry.get("notes") or ""),
    }


def serialize_builtin_entry_delta_for_storage(
    entry: dict[str, Any],
    baseline_entry: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(baseline_entry, dict):
        return serialize_dictionary_entry_for_storage(entry)

    payload = {
        "source": str(entry.get("source") or ""),
        "target": entry.get("target"),
    }
    changed = False

    for field, default in (
        ("enabled", True),
        ("hits", 0),
        ("notes", ""),
    ):
        current = entry.get(field, default)
        baseline = baseline_entry.get(field, default)
        if field == "hits":
            current = int(current or 0)
            baseline = int(baseline or 0)
        elif field == "notes":
            current = str(current or "")
            baseline = str(baseline or "")
        else:
            current = bool(current)
            baseline = bool(baseline)
        if current != baseline:
            payload[field] = current
            changed = True

    current_tags = [str(tag) for tag in entry.get("tags", []) if str(tag).strip()]
    baseline_tags = [str(tag) for tag in baseline_entry.get("tags", []) if str(tag).strip()]
    if current_tags != baseline_tags:
        payload["tags"] = current_tags
        changed = True

    entry_id = entry.get("id")
    baseline_id = baseline_entry.get("id")
    if entry_id and entry_id != baseline_id and changed:
        payload["id"] = entry_id

    return payload if changed else None


def serialize_dictionary_table_for_storage(
    table: dict[str, Any],
    baseline_table: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "id": str(table.get("id") or ""),
        "kind": str(table.get("kind") or ""),
        "name": str(table.get("name") or ""),
        "version": str(table.get("version") or "2.0.0"),
        "description": str(table.get("description") or ""),
        "source_url": str(table.get("source_url")) if table.get("source_url") else None,
        "built_in": bool(table.get("built_in", False)),
        "editable": bool(table.get("editable", not table.get("built_in", False))),
        "enabled": bool(table.get("enabled", True)),
        "tags": [str(tag) for tag in table.get("tags", []) if str(tag).strip()],
    }

    baseline_entry_lookup = {
        dictionary_entry_signature_for_storage(entry, f"baseline::{index}"): entry
        for index, entry in enumerate((baseline_table or {}).get("entries", []))
        if isinstance(entry, dict)
    }
    entries: list[dict[str, Any]] = []
    for index, entry in enumerate(table.get("entries", [])):
        if not isinstance(entry, dict):
            continue
        if payload["built_in"]:
            signature = dictionary_entry_signature_for_storage(entry, f"provided::{index}")
            compact_entry = serialize_builtin_entry_delta_for_storage(entry, baseline_entry_lookup.get(signature))
            if compact_entry is not None:
                entries.append(compact_entry)
        else:
            entries.append(serialize_dictionary_entry_for_storage(entry))
    payload["entries"] = entries
    return payload


def serialize_dictionary_collection_for_storage(
    kind: str,
    collection: dict[str, Any],
    baseline_collection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    baseline_table_lookup = {
        str(table.get("id") or f"{kind}-baseline-{index}"): table
        for index, table in enumerate((baseline_collection or {}).get("tables", []))
        if isinstance(table, dict)
    }
    tables = [
        serialize_dictionary_table_for_storage(
            table,
            baseline_table_lookup.get(str(table.get("id") or f"{kind}-table-{index}")),
        )
        for index, table in enumerate(collection.get("tables", []))
        if isinstance(table, dict)
    ]
    return {
        "kind": kind,
        "name": str(collection.get("name") or kind),
        "description": str(collection.get("description") or ""),
        "tables": tables,
    }


def serialize_dictionary_set_for_storage(dictionary_set: dict[str, Any] | None) -> dict[str, Any]:
    baseline = default_dictionary_set_seed()
    current = dictionary_set if isinstance(dictionary_set, dict) else baseline
    serialized = {
        "id": str(current.get("id") or baseline.get("id") or "dict-default"),
        "name": str(current.get("name") or baseline.get("name") or "默认词表集"),
        "version": str(current.get("version") or baseline.get("version") or "2.0.0"),
        "bound_to_project": bool(current.get("bound_to_project", baseline.get("bound_to_project", True))),
        "collections": {},
    }

    for kind, baseline_collection in baseline.get("collections", {}).items():
        current_collection = current.get("collections", {}).get(kind, baseline_collection)
        if not isinstance(current_collection, dict):
            current_collection = baseline_collection
        serialized["collections"][kind] = serialize_dictionary_collection_for_storage(
            kind,
            current_collection,
            baseline_collection,
        )

    for kind, collection in current.get("collections", {}).items():
        if kind in serialized["collections"] or not isinstance(collection, dict):
            continue
        serialized["collections"][kind] = serialize_dictionary_collection_for_storage(kind, collection)

    return serialized


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
    storage_manifest = {
        key: deepcopy(manifest[key]) if key in manifest else deepcopy(value)
        for key, value in baseline_manifest.items()
        if key != "dictionary_set"
    }
    storage_manifest["dictionary_set"] = serialize_dictionary_set_for_storage(manifest.get("dictionary_set"))
    storage_manifest["document_count"] = len(corpus)
    storage_manifest["run_count"] = len(storage_manifest.get("run_history", []))
    normalized_dirty = {str(item) for item in dirty_sections} if dirty_sections is not None else None

    if normalized_dirty is None or "manifest" in normalized_dirty:
        write_json(project_dir / PROJECT_FILENAME, storage_manifest)
    if normalized_dirty is None or "corpus" in normalized_dirty:
        write_json(project_dir / CORPUS_FILENAME, corpus)
    if normalized_dirty is None or "import_template" in normalized_dirty:
        write_json(project_dir / "metadata/import_template.json", manifest["import_template"])
    if normalized_dirty is None or "dictionary_set" in normalized_dirty:
        for kind, collection in storage_manifest["dictionary_set"].get("collections", {}).items():
            write_json(project_dir / f"dictionaries/{kind}.json", collection)


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


def save_project_template(
    manifest: dict[str, Any],
    name: str | None = None,
    description: str | None = None,
    template_id: str | None = None,
) -> dict[str, Any]:
    payload = build_project_template(manifest, name=name, description=description, template_id=template_id)
    return save_template(project_templates_root(), payload)


def list_project_templates() -> list[dict[str, Any]]:
    return list_templates(project_templates_root())


def load_project_template(template_id: str) -> dict[str, Any]:
    return load_template(project_templates_root(), template_id)


def save_import_template_record(
    import_template: dict[str, Any],
    name: str | None = None,
    description: str | None = None,
    template_id: str | None = None,
) -> dict[str, Any]:
    payload = deepcopy(import_template)
    payload["id"] = template_id or payload.get("id") or f"import-template-{uuid_suffix()}"
    if name:
        payload["name"] = name
    if description is not None:
        payload["description"] = description
    return save_template(import_templates_root(), payload)


def list_import_templates() -> list[dict[str, Any]]:
    return list_templates(import_templates_root())


def load_import_template(template_id: str) -> dict[str, Any]:
    return load_template(import_templates_root(), template_id)


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
    corpus = read_json(project_dir / CORPUS_FILENAME) if (project_dir / CORPUS_FILENAME).exists() else []
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
    shutil.rmtree(project_dir)
    remove_project_from_workspace(project_id)
    return {
        "project_id": project_id,
        "deleted_path": deleted_path,
    }


def project_package_name(manifest: dict[str, Any]) -> str:
    timestamp = str(manifest.get("updated_at") or utc_now_iso()).replace(":", "-").replace(".", "-")
    return f"{slugify(str(manifest.get('name') or manifest.get('id') or 'textflow-project'))}-{timestamp}{PROJECT_PACKAGE_EXTENSION}"


def normalize_project_package_path(path: Path) -> Path:
    if path.suffix.lower() == PROJECT_PACKAGE_EXTENSION:
        return path
    return path.with_suffix(PROJECT_PACKAGE_EXTENSION)


def find_project_root(search_root: Path) -> Path:
    direct_project = search_root / PROJECT_FILENAME
    if direct_project.exists():
        return search_root

    for manifest_path in sorted(search_root.rglob(PROJECT_FILENAME)):
        return manifest_path.parent
    raise ValueError(f"No project manifest found in {search_root}")


def _archive_members(project_dir: Path) -> list[Path]:
    members: list[Path] = []
    for path in sorted(project_dir.rglob("*")):
        if path.is_dir():
            continue
        relative_path = path.relative_to(project_dir)
        if relative_path.parts[:2] == ("exports", "backups"):
            continue
        members.append(path)
    return members


def export_project_package(project_dir: Path, output_path: Path | None = None) -> Path:
    manifest, _corpus = load_project(project_dir)
    if output_path is None:
        backup_dir = project_dir / "exports" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        output_path = backup_dir / project_package_name(manifest)
    output_path = normalize_project_package_path(output_path.expanduser().resolve())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_output_path = output_path.with_name(f"{output_path.stem}-{uuid_suffix()}{output_path.suffix}.tmp")
    if temp_output_path.exists():
        temp_output_path.unlink()

    try:
        with zipfile.ZipFile(temp_output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in _archive_members(project_dir):
                relative_path = path.relative_to(project_dir)
                archive.write(path, arcname=str(Path(project_dir.name) / relative_path))
        temp_output_path.replace(output_path)
    finally:
        if temp_output_path.exists():
            temp_output_path.unlink()

    return output_path


def import_project_package(package_path: Path) -> tuple[Path, dict[str, Any], list[dict[str, Any]]]:
    package_path = package_path.expanduser().resolve()
    if not package_path.exists():
        raise FileNotFoundError(f"Project package not found: {package_path}")

    temp_root = projects_root() / f".import-{uuid_suffix()}"
    if temp_root.exists():
        shutil.rmtree(temp_root)
    temp_root.mkdir(parents=True, exist_ok=True)

    try:
        shutil.unpack_archive(str(package_path), str(temp_root), format="zip")
        source_project_dir = find_project_root(temp_root)
        manifest = read_json(source_project_dir / PROJECT_FILENAME)
        corpus = read_json(source_project_dir / CORPUS_FILENAME) if (source_project_dir / CORPUS_FILENAME).exists() else []
        existing_dir = find_project_dir(str(manifest.get("id")))
        target_dir = ensure_unique_project_dir(str(manifest.get("name") or source_project_dir.stem))
        shutil.copytree(source_project_dir, target_dir)
        manifest, corpus = load_project(target_dir)

        if existing_dir is not None:
            timestamp = utc_now_iso()
            manifest["id"] = f"project-{uuid_suffix()}"
            manifest["name"] = f"{manifest['name']} 导入副本"
            manifest["created_at"] = timestamp
            manifest["updated_at"] = timestamp
            for run in manifest.get("run_history", []):
                run["project_id"] = manifest["id"]

        save_project(target_dir, manifest, corpus, already_normalized=True)
        return target_dir, manifest, corpus
    finally:
        if temp_root.exists():
            shutil.rmtree(temp_root, ignore_errors=True)


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


def duplicate_project(project_id: str, duplicated_name: str | None = None) -> tuple[Path, dict[str, Any], list[dict[str, Any]]]:
    source_dir = find_project_dir(project_id)
    if source_dir is None:
        raise ValueError(f"Project {project_id} not found")

    source_manifest, _ = load_project(source_dir)
    target_name = duplicated_name or f"{source_manifest['name']} 副本"
    target_dir = ensure_unique_project_dir(target_name)
    shutil.copytree(source_dir, target_dir)

    manifest, corpus = load_project(target_dir)
    timestamp = utc_now_iso()
    manifest["id"] = f"project-{uuid_suffix()}"
    manifest["name"] = target_name
    manifest["created_at"] = timestamp
    manifest["updated_at"] = timestamp
    refresh_manifest_paths(manifest, target_dir)

    for run in manifest.get("run_history", []):
        run["project_id"] = manifest["id"]

    save_project(target_dir, manifest, corpus, already_normalized=True)
    return target_dir, manifest, corpus


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
