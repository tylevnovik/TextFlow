from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from ._common import string_param, port, runtime, node_definition_from_base, passthrough_compiler
from ._support import (
    _active_dictionary_set,
    _set_active_dictionary_set,
    _rebuild_dictionary_sheets,
    _report_node_progress,
)


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    base = {
        "type": "select_dictionary_tables",
        "title": "选择词表分表",
        "category": "process",
        "description": "只激活当前运行所需的词表分表，不改动项目默认词表。",
        "inputs": [
            port("dictionary_set_in", "DictionarySet", "词表输入")
        ],
        "outputs": [
            port("dictionary_set", "DictionarySet", "已筛选词表")
        ],
        "params": [
            string_param("selected_table_ids_text", "启用分表 ID / 类型", "standard-project,synonym_map", "")
        ],
        "runtime": runtime(
            "resource",
            "resource.select_dictionary_tables",
            cacheable=True,
            previewable=True,
            output_node=False,
            parallel_safe=True,
        ),
    }
    return node_definition_from_base(base, runtime_profile, None)


def compile_node(context: Any, node: dict[str, Any]) -> None:
    passthrough_compiler(context, node)


def _selected_table_ids(config: dict[str, Any]) -> list[str]:
    raw_ids = config.get("selected_table_ids")
    if isinstance(raw_ids, list):
        selected = [str(item).strip() for item in raw_ids if str(item).strip()]
        if selected:
            return selected
    return [
        item.strip()
        for item in re.split(r"[\r\n,]+", str(config.get("selected_table_ids_text") or ""))
        if item.strip()
    ]


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    dictionary_set = deepcopy(_active_dictionary_set(context, inputs))
    selected_tokens = {
        item.casefold()
        for item in _selected_table_ids(node.get("config") if isinstance(node.get("config"), dict) else {})
    }
    _report_node_progress(context, node, 0.25, f"选择词表分表：读取 {len(selected_tokens)} 个选择条件")
    if not selected_tokens:
        active_dictionary_set = _set_active_dictionary_set(context, dictionary_set)
        _report_node_progress(context, node, 0.92, "选择词表分表：沿用全部词表")
        return {"dictionary_set": active_dictionary_set}
    collections = dictionary_set.get("collections") if isinstance(dictionary_set.get("collections"), dict) else {}
    collection_items = list(collections.items())
    for index, (kind, collection) in enumerate(collection_items, start=1):
        if not isinstance(collection, dict):
            continue
        tables = collection.get("tables")
        if isinstance(tables, list):
            collection["tables"] = [
                deepcopy(table)
                for table in tables
                if isinstance(table, dict)
                and (
                    str(table.get("id") or "").strip().casefold() in selected_tokens
                    or str(table.get("kind") or kind).strip().casefold() in selected_tokens
                )
            ]
        _report_node_progress(
            context,
            node,
            0.25 + 0.55 * index / max(len(collection_items), 1),
            f"选择词表分表：处理 {index}/{len(collection_items)} 类词表",
        )
    active_dictionary_set = _set_active_dictionary_set(context, _rebuild_dictionary_sheets(dictionary_set))
    active_table_count = sum(
        len(collection.get("tables") or [])
        for collection in (active_dictionary_set.get("collections") or {}).values()
        if isinstance(collection, dict)
    )
    _report_node_progress(context, node, 0.92, f"选择词表分表：启用 {active_table_count} 张表")
    return {"dictionary_set": active_dictionary_set}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
