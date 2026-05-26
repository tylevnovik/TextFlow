from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from ..domain.dictionary import build_dictionary_sheets_from_collections, default_dictionary_set_seed
from .constants import PROJECT_DATABASE_FILENAME
from .database import initialize_project_database, load_dictionary_set
from .io import read_json

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
        def normalize_entry_payload(
            payload: dict[str, Any],
            *,
            baseline_entry: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            baseline = baseline_entry if isinstance(baseline_entry, dict) else {}
            raw_tags = payload.get("tags") if "tags" in payload else baseline.get("tags", [])
            notes_value = payload.get("notes") if "notes" in payload else baseline.get("notes", "")
            return {
                "id": payload.get("id") or baseline.get("id"),
                "source": str(payload.get("source") or baseline.get("source") or ""),
                "target": payload["target"] if "target" in payload else baseline.get("target"),
                "tags": [str(tag) for tag in raw_tags if str(tag).strip()],
                "enabled": bool(payload.get("enabled", baseline.get("enabled", True))),
                "hits": int(payload.get("hits", baseline.get("hits", 0)) or 0),
                "notes": str(notes_value or ""),
            }

        merged_entries = [normalize_entry_payload(entry) for entry in baseline_entries if isinstance(entry, dict)]
        signature_to_index = {
            entry_signature(entry, f"baseline::{index}"): index
            for index, entry in enumerate(merged_entries)
        }
        for index, entry in enumerate(provided_entries):
            if not isinstance(entry, dict):
                continue
            normalized_entry = normalize_entry_payload(entry)
            signature = entry_signature(normalized_entry, f"provided::{index}")
            existing_index = signature_to_index.get(signature)
            if existing_index is None:
                signature_to_index[signature] = len(merged_entries)
                merged_entries.append(normalized_entry)
                continue
            merged_entries[existing_index] = normalize_entry_payload(
                entry,
                baseline_entry=merged_entries[existing_index],
            )
        return merged_entries

    def normalize_table_payload(
        kind: str,
        payload: dict[str, Any],
        *,
        fallback_id: str,
        fallback_name: str,
        baseline_table: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        baseline = baseline_table if isinstance(baseline_table, dict) else {}
        table: dict[str, Any] = {}
        table["id"] = str(payload.get("id") or baseline.get("id") or fallback_id)
        table["kind"] = kind
        table["name"] = str(payload.get("name") or baseline.get("name") or fallback_name)
        table["version"] = str(payload.get("version") or baseline.get("version") or "2.0.0")
        table["description"] = str(payload.get("description") or baseline.get("description") or "")
        source_url = payload.get("source_url") if "source_url" in payload else baseline.get("source_url")
        table["source_url"] = str(source_url) if source_url else None
        table["built_in"] = bool(payload.get("built_in", baseline.get("built_in", False)))
        table["editable"] = bool(payload.get("editable", baseline.get("editable", not table["built_in"])))
        table["enabled"] = bool(payload.get("enabled", baseline.get("enabled", True)))
        raw_tags = payload.get("tags") if "tags" in payload else baseline.get("tags", [])
        table["tags"] = [str(tag) for tag in raw_tags if str(tag).strip()]
        provided_entries = payload.get("entries", []) if isinstance(payload.get("entries"), list) else []
        baseline_entries = baseline.get("entries", []) if isinstance(baseline.get("entries"), list) else []
        table["entries"] = merge_sheet_entries(baseline_entries, provided_entries)
        return table

    def merge_table_lists(
        kind: str,
        baseline_tables: list[dict[str, Any]],
        provided_tables: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        merged_tables = [
            normalize_table_payload(
                kind,
                {},
                fallback_id=f"{kind}-baseline-{index}",
                fallback_name=str(table.get("name") or f"{kind} {index + 1}"),
                baseline_table=table,
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
            merged_tables[existing_index] = normalize_table_payload(
                kind,
                payload,
                fallback_id=table_id,
                fallback_name=str(payload.get("name") or baseline_table.get("name") or f"{kind} 资源"),
                baseline_table=baseline_table,
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
                "description": "从项目内词表或手工录入整理而来的可编辑资源。",
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
    normalized = {
        "id": str(dictionary_set.get("id") or baseline.get("id") or "dict-default"),
        "name": str(dictionary_set.get("name") or baseline.get("name") or "默认词表集"),
        "version": str(dictionary_set.get("version") or baseline.get("version") or "2.0.0"),
        "bound_to_project": bool(dictionary_set.get("bound_to_project", baseline.get("bound_to_project", True))),
        "collections": {},
    }
    for key, value in dictionary_set.items():
        if key not in {"id", "name", "version", "bound_to_project", "sheets", "collections"}:
            normalized[key] = deepcopy(value)

    provided_collections = dictionary_set.get("collections", {})
    baseline_collections = baseline.get("collections", {}) if isinstance(baseline.get("collections"), dict) else {}
    for kind, baseline_collection in baseline_collections.items():
        payload = provided_collections.get(kind) if isinstance(provided_collections, dict) else None
        merged_collection = {
            "kind": kind,
            "name": str((payload or {}).get("name") or baseline_collection.get("name") or ""),
            "description": str((payload or {}).get("description") or baseline_collection.get("description") or ""),
            "tables": merge_table_lists(
                kind,
                baseline_collection.get("tables", []) if isinstance(baseline_collection.get("tables"), list) else [],
                payload.get("tables", []) if isinstance(payload, dict) and isinstance(payload.get("tables"), list) else [],
            ),
        }
        if isinstance(payload, dict):
            for field, value in payload.items():
                if field in {"kind", "name", "description", "tables"}:
                    continue
                merged_collection[field] = deepcopy(value)
        normalized["collections"][kind] = merged_collection

    if isinstance(provided_collections, dict):
        for kind, payload in provided_collections.items():
            if kind in normalized["collections"] or not isinstance(payload, dict):
                continue
            normalized["collections"][kind] = {
                **{field: deepcopy(value) for field, value in payload.items() if field != "tables"},
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


def dictionary_set_manifest_reference(dictionary_set: dict[str, Any]) -> dict[str, Any]:
    collections: dict[str, Any] = {}
    for kind, collection in dictionary_set.get("collections", {}).items():
        if not isinstance(collection, dict):
            continue
        tables = collection.get("tables", []) if isinstance(collection.get("tables"), list) else []
        entry_delta_count = 0
        for table in tables:
            if isinstance(table, dict) and isinstance(table.get("entries"), list):
                entry_delta_count += len(table["entries"])
        collections[kind] = {
            "kind": str(collection.get("kind") or kind),
            "name": str(collection.get("name") or kind),
            "description": str(collection.get("description") or ""),
            "table_count": len(tables),
            "entry_count": entry_delta_count,
        }
    return {
        "id": str(dictionary_set.get("id") or "dict-default"),
        "name": str(dictionary_set.get("name") or "默认词表集"),
        "version": str(dictionary_set.get("version") or "2.0.0"),
        "bound_to_project": bool(dictionary_set.get("bound_to_project", True)),
        "storage": "project.db",
        "table": "dictionary_tables",
        "collections": collections,
    }


def load_dictionary_set_from_database(project_dir: Path) -> dict[str, Any] | None:
    db_path = project_dir / PROJECT_DATABASE_FILENAME
    if not db_path.exists():
        return None
    db = initialize_project_database(db_path)
    return load_dictionary_set(db)


def load_dictionary_set_payload(project_dir: Path, manifest: dict[str, Any]) -> dict[str, Any] | None:
    db_dictionary_set = load_dictionary_set_from_database(project_dir)
    if db_dictionary_set is not None:
        return db_dictionary_set

    manifest_dictionary_set = manifest.get("dictionary_set")
    payload = deepcopy(manifest_dictionary_set) if isinstance(manifest_dictionary_set, dict) else {}
    collections: dict[str, Any] = {}
    manifest_collections = payload.get("collections") if isinstance(payload.get("collections"), dict) else {}
    baseline_collections = default_dictionary_set_seed().get("collections", {})
    collection_kinds = [
        *[kind for kind in baseline_collections.keys()],
        *[kind for kind in manifest_collections.keys() if kind not in baseline_collections],
    ]

    for kind in collection_kinds:
        manifest_collection = manifest_collections.get(kind) if isinstance(manifest_collections, dict) else None
        relative_path = (
            str(manifest_collection.get("path"))
            if isinstance(manifest_collection, dict) and manifest_collection.get("path")
            else f"dictionaries/{kind}.json"
        )
        collection_path = project_dir / relative_path
        if collection_path.exists():
            loaded_collection = read_json(collection_path)
            if isinstance(loaded_collection, dict):
                collections[kind] = loaded_collection
                continue
        if isinstance(manifest_collection, dict) and isinstance(manifest_collection.get("tables"), list):
            collections[kind] = manifest_collection

    if collections:
        payload["collections"] = collections
        payload.pop("storage", None)
        payload.pop("table", None)
        return payload
    return manifest_dictionary_set if isinstance(manifest_dictionary_set, dict) else None

def editable_dictionary_table_for_kind(dictionary_set: dict[str, Any], kind: str) -> dict[str, Any]:
    collection = dictionary_set.get("collections", {}).get(kind)
    if not isinstance(collection, dict):
        raise ValueError(f"Dictionary collection {kind} not found")

    for table in collection.get("tables", []):
        if isinstance(table, dict) and bool(table.get("editable", False)):
            return table
    raise ValueError(f"Editable dictionary table for {kind} not found")
