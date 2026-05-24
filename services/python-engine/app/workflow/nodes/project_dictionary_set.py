from __future__ import annotations

from copy import deepcopy
from typing import Any

from ._common import port, runtime, node_definition_from_base, passthrough_compiler
from ._support import _report_node_progress, _set_active_dictionary_set


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    base = {
        "type": "project_dictionary_set",
        "title": "项目词表",
        "category": "legacy",
        "description": "旧版兼容节点：已由词表输入替代。",
        "hidden_from_toolbox": True,
        "inputs": [],
        "outputs": [
            port("dictionary_set", "DictionarySet", "词表")
        ],
        "params": [],
        "runtime": runtime(
            "resource",
            "legacy.project_dictionary_set",
            cacheable=False,
            previewable=False,
            output_node=False,
        ),
    }
    return node_definition_from_base(base, runtime_profile, None)


def compile_node(context: Any, node: dict[str, Any]) -> None:
    passthrough_compiler(context, node)


def execute_node(context: Any, node: dict[str, Any], _inputs: dict[str, Any]) -> dict[str, Any]:
    _report_node_progress(context, node, 0.35, "词表输入：读取项目词表")
    dictionary_set = deepcopy(context.manifest["dictionary_set"])
    active_dictionary_set = _set_active_dictionary_set(context, dictionary_set)
    entry_count = sum(
        len(sheet.get("entries") or [])
        for sheet in (active_dictionary_set.get("sheets") or {}).values()
        if isinstance(sheet, dict)
    )
    _report_node_progress(context, node, 0.92, f"词表输入：启用 {entry_count} 条词表规则")
    return {"dictionary_set": active_dictionary_set}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
