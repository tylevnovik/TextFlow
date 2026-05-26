from __future__ import annotations

from typing import Any

from ._common import enum_param, string_param, port, runtime, node_definition_from_base, passthrough_compiler, field, graph, slot, ui
from ._support import (
    _clone_corpus_rows,
    _is_table_rows,
    _scoped_corpus_from_inputs,
    _control_rows_from_inputs,
    _record_matches_control_condition,
    _control_values,
    _report_node_progress,
)


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    base = {
        "type": "conditional_router",
        "title": "条件路由",
        "category": "process",
        "description": "用受控字段条件把语料或结果表拆成匹配与未匹配两路，不执行任意脚本。",
        "inputs": [
            port("corpus_in", "CorpusTable", "语料输入"),
            port("table_in", "AnyTable", "表格输入"),
        ],
        "outputs": [
            port("matched_corpus", "CorpusTable", "匹配语料"),
            port("unmatched_corpus", "CorpusTable", "未匹配语料"),
            port("matched_table", "AnyTable", "匹配表格"),
            port("unmatched_table", "AnyTable", "未匹配表格"),
            port(
                "route_summary",
                "AnyTable",
                "路由摘要",
                result_bundle_key="conditional_route_summary",
            ),
        ],
        "params": [
            enum_param(
                "source_kind",
                "条件来源",
                "corpus_metadata",
                [
                    ("corpus_metadata", "语料元数据"),
                    ("table_field", "表格字段"),
                    ("comparison_result", "比较结果字段"),
                ],
                "",
            ),
            string_param("field", "字段", "institution", ""),
            enum_param(
                "operator",
                "运算符",
                "in",
                [
                    ("in", "属于"),
                    ("not_in", "不属于"),
                    ("contains", "包含文本"),
                    ("eq", "等于"),
                    ("neq", "不等于"),
                    ("gt", "大于"),
                    ("gte", "大于等于"),
                    ("lt", "小于"),
                    ("lte", "小于等于"),
                ],
                "",
            ),
            string_param("values_text", "条件值", "OpenAI", ""),
        ],
        "runtime": runtime(
            "scope",
            "control.conditional_router",
            cacheable=True,
            previewable=True,
            output_node=False,
        ),
        "graph": graph((360, 280), (2340, 1320), toolbox_order=220),
        "ui": ui(
            [
                field("select", "source_kind", "条件来源"),
                field("text", "field", "字段"),
                field("select", "operator", "运算符"),
                field("textarea", "values_text", "条件值"),
            ],
        ),
    }
    return node_definition_from_base(base, runtime_profile, None)


def compile_node(context: Any, node: dict[str, Any]) -> None:
    passthrough_compiler(context, node)


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    corpus_input = inputs.get("corpus_in")
    corpus = _clone_corpus_rows(corpus_input) if _is_table_rows(corpus_input) else _clone_corpus_rows(_scoped_corpus_from_inputs(context, inputs))
    table_rows = _control_rows_from_inputs(inputs, "table_in", "record_table_in", "comparison_table_in")
    _report_node_progress(context, node, 0.2, f"条件分流：读取 {len(corpus) or len(table_rows)} 条记录")

    matched_corpus = [item for item in corpus if _record_matches_control_condition(item, config)] if corpus else []
    if corpus:
        _report_node_progress(context, node, 0.55, f"条件分流：命中 {len(matched_corpus)} 篇文档")
    unmatched_corpus = [item for item in corpus if not _record_matches_control_condition(item, config)] if corpus else []
    matched_table = [item for item in table_rows if _record_matches_control_condition(item, config)] if table_rows else []
    if table_rows:
        _report_node_progress(context, node, 0.55, f"条件分流：命中 {len(matched_table)} 行表记录")
    unmatched_table = [item for item in table_rows if not _record_matches_control_condition(item, config)] if table_rows else []

    if matched_corpus:
        context.shared["scoped_corpus"] = matched_corpus

    matched_count = len(matched_corpus) if corpus else len(matched_table)
    unmatched_count = len(unmatched_corpus) if corpus else len(unmatched_table)
    route_summary = [
        {
            "source_kind": str(config.get("source_kind") or "corpus_metadata"),
            "field": str(config.get("field") or ""),
            "operator": str(config.get("operator") or "in"),
            "values": [str(item) for item in _control_values(config)],
            "matched_count": matched_count,
            "unmatched_count": unmatched_count,
            "corpus_input_count": len(corpus),
            "table_input_count": len(table_rows),
        }
    ]
    _report_node_progress(context, node, 0.92, f"条件分流：输出命中 {matched_count} / 未命中 {unmatched_count}")
    return {
        "matched_corpus": matched_corpus,
        "unmatched_corpus": unmatched_corpus,
        "matched_table": matched_table,
        "unmatched_table": unmatched_table,
        "route_summary": route_summary,
    }


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
