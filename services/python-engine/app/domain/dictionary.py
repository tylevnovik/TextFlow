from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from typing import Any
from uuid import uuid4

from ..builtin_dictionary_data import builtin_dictionary_table_specs

DICTIONARY_KIND_ORDER = [
    "stopwords",
    "custom_lexicon",
    "phrase_lexicon",
    "synonym_map",
    "near_synonym_map",
    "standard_terms",
    "exclusion_terms",
    "regex_rules",
]

DICTIONARY_COLLECTION_META: dict[str, dict[str, str]] = {
    "stopwords": {
        "name": "停用词",
        "description": "过滤无分析意义的虚词、常用词和套话。",
    },
    "custom_lexicon": {
        "name": "自定义词典",
        "description": "告诉切词器哪些术语和专名应该整体保留。",
    },
    "phrase_lexicon": {
        "name": "短语词典",
        "description": "把多词短语或固定表达当成一个整体处理。",
    },
    "synonym_map": {
        "name": "同义词表",
        "description": "把别名、区域说法和常见替代表达归并成统一写法。",
    },
    "near_synonym_map": {
        "name": "近义词表",
        "description": "保留可选的扩展归并资源，适合更强的术语合并。",
    },
    "standard_terms": {
        "name": "标准词库",
        "description": "用确定的一对一规则做词形和标准写法归一。",
    },
    "exclusion_terms": {
        "name": "排除词表",
        "description": "在当前课题无关时可整批排除的人名、地名或噪声词。",
    },
    "regex_rules": {
        "name": "Regex 规则",
        "description": "用于清洗和标准化的正则表达式规则。",
    },
}

def unpack_dictionary_row(row: tuple[Any, ...]) -> tuple[str, str | None, int, str | None]:
    source = str(row[0])
    target = row[1] if len(row) > 1 else None
    hits = int(row[2]) if len(row) > 2 else 0
    entry_id = str(row[3]) if len(row) > 3 and row[3] else None
    return source, target, hits, entry_id


def make_dictionary_entry(
    source: str,
    target: str | None = None,
    hits: int = 0,
    entry_id: str | None = None,
) -> dict[str, Any]:
    return {
        "id": entry_id or str(uuid4()),
        "source": source,
        "target": target,
        "tags": [],
        "enabled": True,
        "hits": hits,
        "notes": "",
    }


def make_sheet(kind: str, name: str, rows: list[tuple[Any, ...]]) -> dict[str, Any]:
    return {
        "kind": kind,
        "name": name,
        "version": "1.0.0",
        "entries": [make_dictionary_entry(*unpack_dictionary_row(row)) for row in rows],
    }


def make_dictionary_table_resource(
    kind: str,
    table_id: str,
    name: str,
    rows: list[tuple[Any, ...]],
    *,
    description: str = "",
    source_url: str | None = None,
    built_in: bool = False,
    editable: bool = True,
    enabled: bool = True,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": table_id,
        "kind": kind,
        "name": name,
        "version": "2.0.0",
        "description": description,
        "source_url": source_url,
        "built_in": built_in,
        "editable": editable,
        "enabled": enabled,
        "tags": list(tags or []),
        "entries": [make_dictionary_entry(*unpack_dictionary_row(row)) for row in rows],
    }


def make_dictionary_collection(kind: str, tables: list[dict[str, Any]]) -> dict[str, Any]:
    meta = DICTIONARY_COLLECTION_META[kind]
    return {
        "kind": kind,
        "name": meta["name"],
        "description": meta["description"],
        "tables": tables,
    }


def dictionary_entry_signature(entry: dict[str, Any], fallback_key: str) -> str:
    source = str(entry.get("source") or "").strip()
    target = str(entry.get("target") or "").strip()
    if not source:
        return fallback_key
    return f"{source.casefold()}::{target.casefold()}"


def build_dictionary_sheets_from_collections(collections: dict[str, Any]) -> dict[str, Any]:
    sheets: dict[str, Any] = {}
    for kind in DICTIONARY_KIND_ORDER:
        collection = collections.get(kind) if isinstance(collections, dict) else None
        collection_meta = DICTIONARY_COLLECTION_META[kind]
        entries: list[dict[str, Any]] = []
        seen: set[str] = set()
        if isinstance(collection, dict):
            for table in collection.get("tables", []):
                if not isinstance(table, dict) or not table.get("enabled", True):
                    continue
                for index, entry in enumerate(table.get("entries", [])):
                    if not isinstance(entry, dict) or not entry.get("enabled", True):
                        continue
                    signature = dictionary_entry_signature(entry, f"{kind}:{table.get('id') or 'table'}:{index}")
                    if signature in seen:
                        continue
                    seen.add(signature)
                    entries.append(entry)
        sheets[kind] = {
            "kind": kind,
            "name": str((collection or {}).get("name") or collection_meta["name"]),
            "version": "2.0.0",
            "entries": entries,
        }
    return sheets

@lru_cache(maxsize=1)
def default_dictionary_set_seed() -> dict[str, Any]:
    builtin_specs = builtin_dictionary_table_specs()
    collections: dict[str, Any] = {}
    for kind in DICTIONARY_KIND_ORDER:
        project_custom = make_dictionary_table_resource(
            kind,
            f"{kind}-project-custom",
            "项目自定义",
            [],
            description="项目内可直接编辑、删除、导入和新增的自定义词表资源。",
            built_in=False,
            editable=True,
            enabled=True,
        )
        builtin_tables = [
            make_dictionary_table_resource(
                kind,
                spec["id"],
                spec["name"],
                list(spec.get("rows") or []),
                description=str(spec.get("description") or ""),
                source_url=str(spec.get("source_url") or "") or None,
                built_in=bool(spec.get("built_in", True)),
                editable=bool(spec.get("editable", False)),
                enabled=bool(spec.get("enabled", True)),
                tags=list(spec.get("tags") or []),
            )
            for spec in builtin_specs.get(kind, [])
            if isinstance(spec, dict)
        ]
        collections[kind] = make_dictionary_collection(kind, [project_custom, *builtin_tables])

    dictionary_set = {
        "id": "dict-default",
        "name": "默认词表集",
        "version": "2.0.0",
        "bound_to_project": True,
        "collections": collections,
    }
    dictionary_set["sheets"] = build_dictionary_sheets_from_collections(collections)
    return dictionary_set


def default_dictionary_set() -> dict[str, Any]:
    return deepcopy(default_dictionary_set_seed())
