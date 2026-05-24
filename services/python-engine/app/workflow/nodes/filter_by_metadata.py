from __future__ import annotations

from typing import Any

from ._common import enum_param, string_param, port, runtime, node_definition_from_base, passthrough_compiler
from ._support import (
    _clone_corpus_rows,
    _scoped_corpus_from_inputs,
    _report_node_progress,
    _report_corpus_progress,
    _document_field_value,
)


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    base = {
        "type": "filter_by_metadata",
        "title": "按元数据筛选",
        "category": "process",
        "description": "按机构、来源、年份或扩展元数据字段筛选当前语料。",
        "inputs": [
            port("corpus_in", "CorpusTable", "语料输入")
        ],
        "outputs": [
            port("filtered_corpus", "CorpusTable", "筛选后语料")
        ],
        "params": [
            string_param("field", "筛选字段", "institution", ""),
            enum_param(
                "operator",
                "运算符",
                "in",
                [
                    ("in", "包含"),
                    ("not_in", "排除"),
                    ("contains", "包含文本"),
                    ("eq", "等于"),
                ],
                "",
            ),
            string_param("values_text", "筛选值", "OpenAI", ""),
        ],
        "runtime": runtime(
            "scope",
            "scope.filter_by_metadata",
            cacheable=True,
            previewable=True,
            output_node=False,
            parallel_safe=True,
        ),
    }
    return node_definition_from_base(base, runtime_profile, None)


def compile_node(context: Any, node: dict[str, Any]) -> None:
    passthrough_compiler(context, node)


def _metadata_filter_conditions(config: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(config.get("conditions"), list):
        conditions = [item for item in config.get("conditions", []) if isinstance(item, dict)]
        if conditions:
            return conditions
    field = str(config.get("field") or "").strip()
    if not field:
        return []
    values = config.get("values")
    if isinstance(values, list):
        normalized_values = [str(item) for item in values if str(item).strip()]
    else:
        values_text = str(config.get("values_text") or "")
        normalized_values = [item.strip() for item in values_text.split(",") if item.strip()]
    return [{
        "field": field,
        "operator": str(config.get("operator") or "in"),
        "values": normalized_values,
    }]


def _document_matches_condition(document: dict[str, Any], condition: dict[str, Any]) -> bool:
    field = str(condition.get("field") or "").strip()
    operator = str(condition.get("operator") or "in")
    values = [str(item) for item in condition.get("values", []) if str(item).strip()]
    value = _document_field_value(document, field)
    value_text = str(value or "")
    if operator == "not_in":
        return value_text not in set(values)
    if operator == "contains":
        return any(item in value_text for item in values)
    if operator == "eq":
        return value_text == (values[0] if values else "")
    return value_text in set(values)


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    corpus = _clone_corpus_rows(_scoped_corpus_from_inputs(context, inputs))
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    conditions = _metadata_filter_conditions(config)
    _report_node_progress(context, node, 0.2, f"元数据过滤：读取 {len(corpus)} 篇文档")
    if not conditions:
        context.shared["scoped_corpus"] = corpus
        _report_node_progress(context, node, 0.92, "元数据过滤：未配置条件，沿用全部文档")
        return {"filtered_corpus": corpus}
    filtered: list[dict[str, Any]] = []
    total = len(corpus)
    for index, item in enumerate(corpus, start=1):
        if all(_document_matches_condition(item, condition) for condition in conditions):
            filtered.append(item)
        _report_corpus_progress(context, node, index, total, "元数据过滤")
    context.shared["scoped_corpus"] = filtered
    _report_node_progress(context, node, 0.92, f"元数据过滤：命中 {len(filtered)} 篇文档")
    return {"filtered_corpus": filtered}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
