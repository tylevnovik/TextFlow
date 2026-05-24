from __future__ import annotations

from copy import deepcopy
from typing import Any

from ._common import bool_param, enum_param, string_param, port, runtime, node_definition_from_base, dictionary_input_compiler
from ._support import _report_node_progress, _set_active_dictionary_set


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    base = {
        "type": "dictionary_input",
        "title": "词表输入",
        "category": "input",
        "description": "引用当前项目绑定的词表资源。",
        "inputs": [],
        "outputs": [
            port("dictionary_set", "DictionarySet", "词表")
        ],
        "params": [
            enum_param(
                "resource_mode",
                "资源来源",
                "project_dictionary",
                [("project_dictionary", "项目词表")],
                "",
            ),
            string_param("resource_id", "资源 ID", "project:dictionary_set", ""),
            bool_param("use_custom_lexicon", "使用自定义词典", True, ""),
            bool_param("use_phrase_lexicon", "使用短语词典", True, ""),
            bool_param("apply_regex_rules", "启用 Regex 规则", True, ""),
            bool_param("apply_standard_terms", "启用标准词", True, ""),
            bool_param("apply_synonym_map", "启用同义词", True, ""),
            bool_param("apply_near_synonym_map", "启用近义词", True, ""),
            bool_param("apply_stopwords", "启用停用词", True, ""),
            bool_param("apply_exclusion_terms", "启用排除词", True, ""),
        ],
        "runtime": runtime(
            "resource",
            "resource.load_dictionary",
            cacheable=True,
            previewable=True,
            output_node=False,
        ),
    }
    return node_definition_from_base(base, runtime_profile, None)


def compile_node(context: Any, node: dict[str, Any]) -> None:
    dictionary_input_compiler(context, node)


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
