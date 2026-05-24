from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
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
        "type": "overlay_dictionary_rules",
        "title": "叠加临时词表规则",
        "category": "process",
        "description": "按本次运行临时追加词表规则，不写回项目默认词表。",
        "inputs": [
            port("dictionary_set_in", "DictionarySet", "词表输入")
        ],
        "outputs": [
            port("dictionary_set", "DictionarySet", "叠加后词表")
        ],
        "params": [
            string_param("overlay_rows_text", "临时规则", "standard_terms|llm|large language model|true", "")
        ],
        "runtime": runtime(
            "resource",
            "resource.overlay_dictionary_rules",
            cacheable=True,
            previewable=True,
            output_node=False,
            parallel_safe=True,
        ),
    }
    return node_definition_from_base(base, runtime_profile, None)


def compile_node(context: Any, node: dict[str, Any]) -> None:
    passthrough_compiler(context, node)


def _overlay_rows(config: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(config.get("overlay_rows"), list):
        rows = [item for item in config.get("overlay_rows", []) if isinstance(item, dict)]
        if rows:
            return rows
    rows: list[dict[str, Any]] = []
    for line in str(config.get("overlay_rows_text") or "").splitlines():
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 3 or not parts[0] or not parts[1]:
            continue
        rows.append(
            {
                "kind": parts[0],
                "source": parts[1],
                "target": parts[2] or None,
                "enabled": parts[3].lower() != "false" if len(parts) > 3 else True,
            }
        )
    return rows


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    dictionary_set = deepcopy(_active_dictionary_set(context, inputs))
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    rows = _overlay_rows(config)
    _report_node_progress(context, node, 0.25, f"叠加临时词表规则：读取 {len(rows)} 条规则")
    if not rows:
        active_dictionary_set = _set_active_dictionary_set(context, dictionary_set)
        _report_node_progress(context, node, 0.92, "叠加临时词表规则：无临时规则")
        return {"dictionary_set": active_dictionary_set}
    collections = dictionary_set.get("collections") if isinstance(dictionary_set.get("collections"), dict) else {}
    grouped_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for index, row in enumerate(rows, start=1):
        kind = str(row.get("kind") or "").strip()
        source = str(row.get("source") or "").strip()
        if not kind or not source or kind not in collections:
            continue
        grouped_rows[kind].append(
            {
                "id": f"runtime-{kind}-{index}",
                "source": source,
                "target": row.get("target"),
                "enabled": bool(row.get("enabled", True)),
                "hits": 0,
                "tags": ["runtime-overlay"],
                "notes": "Runtime overlay node",
            }
        )
        if index == len(rows) or index % 250 == 0:
            _report_node_progress(
                context,
                node,
                0.25 + 0.5 * index / max(len(rows), 1),
                f"叠加临时词表规则：整理 {index}/{len(rows)} 条规则",
            )
    for kind, entries in grouped_rows.items():
        collection = collections.get(kind)
        if not isinstance(collection, dict):
            continue
        tables = collection.get("tables") if isinstance(collection.get("tables"), list) else []
        tables.append(
            {
                "id": f"runtime-overlay-{kind}",
                "kind": kind,
                "name": "运行时叠加",
                "version": "2.0.0",
                "description": "Runtime-only dictionary overlay",
                "source_url": None,
                "built_in": False,
                "editable": False,
                "enabled": True,
                "tags": ["runtime-overlay"],
                "entries": entries,
            }
        )
        collection["tables"] = tables
    active_dictionary_set = _set_active_dictionary_set(context, _rebuild_dictionary_sheets(dictionary_set))
    _report_node_progress(context, node, 0.92, f"叠加临时词表规则：写入 {sum(len(entries) for entries in grouped_rows.values())} 条临时规则")
    return {"dictionary_set": active_dictionary_set}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
