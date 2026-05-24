from __future__ import annotations

from typing import Any

from ._support import _analysis_ops, _report_node_progress, _scoped_corpus_from_inputs, _token_frame
from ._common import port, runtime


def node_definition(_runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "type": "term_document_analysis",
        "title": "词项文档分析",
        "category": "analysis",
        "description": "查看词项与文档的对应关系和文档内词频。",
        "inputs": [port("token_corpus_in", "FilteredTokenCorpus", "分析词项")],
        "outputs": [
            port(
                "term_document_table",
                "TermDocumentTable",
                "词项文档表",
                result_bundle_key="term_document_table",
            )
        ],
        "params": [],
        "runtime": runtime(
            "analysis",
            "analysis.term_document",
            cacheable=True,
            previewable=True,
            parallel_safe=True,
        ),
    }


def compile_node(context: Any, _node: dict[str, Any]) -> None:
    context.merge_section("analysis", {"include_term_document_relations": True})
    context.enable_step("analysis")


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    analysis_ops = _analysis_ops()
    corpus = _scoped_corpus_from_inputs(context, inputs)
    _report_node_progress(context, node, 0.2, "词项-文档：准备词项表")
    df_tokens = _token_frame(context, corpus)
    _report_node_progress(context, node, 0.65, f"词项-文档：已展开 {len(df_tokens)} 条词项")
    rows = analysis_ops.term_document_table(df_tokens)
    _report_node_progress(context, node, 0.92, f"词项-文档：生成 {len(rows)} 行")
    return {"term_document_table": rows}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
