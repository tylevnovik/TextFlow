from __future__ import annotations

from typing import Any

from ._support import _analysis_ops, _report_node_progress, _scoped_corpus_from_inputs, _token_frame
from ._common import port, runtime, field, graph, slot, ui


def node_definition(_runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "type": "term_year_analysis",
        "title": "词项年份分析",
        "category": "analysis",
        "description": "分析词项按年份的变化趋势。",
        "inputs": [port("token_corpus_in", "FilteredTokenCorpus", "分析词项")],
        "outputs": [
            port(
                "term_year_table",
                "TermYearTable",
                "词项年份表",
                result_bundle_key="term_year_table",
            )
        ],
        "params": [],
        "runtime": runtime(
            "analysis",
            "analysis.term_year",
            cacheable=True,
            previewable=True,
            parallel_safe=True,
        ),
        "graph": graph((280, 210), (3660, 680), toolbox_order=310),
        "ui": ui([]),
    }


def compile_node(context: Any, _node: dict[str, Any]) -> None:
    context.merge_section("analysis", {"include_term_year_relations": True})
    context.enable_step("analysis")


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    analysis_ops = _analysis_ops()
    corpus = _scoped_corpus_from_inputs(context, inputs)
    _report_node_progress(context, node, 0.2, "词项-年份：准备词项表")
    df_tokens = _token_frame(context, corpus)
    _report_node_progress(context, node, 0.65, f"词项-年份：已展开 {len(df_tokens)} 条词项")
    rows = analysis_ops.term_year_table(df_tokens)
    _report_node_progress(context, node, 0.92, f"词项-年份：生成 {len(rows)} 行")
    return {"term_year_table": rows}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
