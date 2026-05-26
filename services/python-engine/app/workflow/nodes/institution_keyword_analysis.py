from __future__ import annotations

from typing import Any

from ._support import _analysis_ops, _report_node_progress, _scoped_corpus_from_inputs
from ._common import port, runtime, field, graph, slot, ui


def node_definition(_runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "type": "institution_keyword_analysis",
        "title": "机构关键词分析",
        "category": "analysis",
        "description": "分析不同机构在关键词层面的出现与共现强度。",
        "inputs": [port("keyword_table_in", "KeywordTable", "关键词输入")],
        "outputs": [
            port(
                "institution_keyword_table",
                "InstitutionKeywordTable",
                "机构关键词表",
                result_bundle_key="institution_keyword_cooccurrence",
            )
        ],
        "params": [],
        "runtime": runtime(
            "analysis",
            "analysis.institution_keyword",
            cacheable=True,
            previewable=True,
            parallel_safe=True,
        ),
        "graph": graph((320, 210), (4080, 1320), toolbox_order=390),
        "ui": ui([]),
    }


def compile_node(context: Any, _node: dict[str, Any]) -> None:
    context.merge_section(
        "analysis",
        {
            "include_institution_keyword_analysis": True,
            "include_keyword_extraction": True,
        },
    )
    context.enable_step("analysis")


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    analysis_ops = _analysis_ops()
    keyword_rows = inputs.get("keyword_table_in") or []
    if not isinstance(keyword_rows, list):
        keyword_rows = [keyword_rows]
    corpus = _scoped_corpus_from_inputs(context, inputs)
    _report_node_progress(context, node, 0.35, f"机构-关键词：读取 {len(keyword_rows)} 个关键词")
    institution_keyword_rows, _ = analysis_ops.institution_keyword_and_topic(
        corpus,
        keyword_rows,
        {},
        {},
    )
    _report_node_progress(context, node, 0.92, f"机构-关键词：生成 {len(institution_keyword_rows)} 行")
    return {"institution_keyword_table": institution_keyword_rows}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
