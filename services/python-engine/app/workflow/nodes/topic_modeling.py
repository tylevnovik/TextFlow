from __future__ import annotations

from typing import Any

from ._common import analysis_passthrough_compiler, enum_param, number_param, port, runtime, field, graph, slot, ui
from ._support import (
    _analysis_ops,
    _analysis_params,
    _feature_term_payload,
    _report_node_progress,
    _scoped_corpus_from_inputs,
)


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    analysis = (runtime_profile or {}).get("analysis") or {}
    return {
        "type": "topic_modeling",
        "title": "主题建模",
        "category": "analysis",
        "description": "使用 NMF 或 LDA 对语料做轻量主题建模，输出主题词项、文档主题和主题摘要。",
        "inputs": [
            port("token_corpus_in", "FilteredTokenCorpus", "分析词项")
        ],
        "outputs": [
            port("topic_term_table", "AnyTable", "主题词项表", result_bundle_key="topic_term_table"),
            port("document_topic_table", "AnyTable", "文档主题表", result_bundle_key="document_topic_table"),
            port("topic_summary_table", "AnyTable", "主题摘要表", result_bundle_key="topic_summary_table"),
        ],
        "params": [
            enum_param("topic_algorithm", "主题算法", analysis.get("topic_algorithm", "nmf"), [
                ("nmf", "NMF"),
                ("lda", "LDA"),
            ]),
            number_param("topic_model_k", "主题数量", int(analysis.get("topic_model_k", 4))),
            number_param("top_terms_per_topic", "每主题词项数", 5),
        ],
        "runtime": runtime(
            "analysis",
            "analysis.topic_modeling",
            cacheable=True,
            previewable=True,
            parallel_safe=True,
        ),
        "graph": graph((360, 260), (4080, 1000), toolbox_order=380),
        "ui": ui(
            [
                field("select", "topic_algorithm", "主题算法"),
                field("number", "topic_model_k", "主题数量", step=1),
                field("number", "top_terms_per_topic", "每主题词项数", step=1),
            ],
        ),
    }


def compile_node(context: Any, node: dict[str, Any]) -> None:
    analysis_passthrough_compiler(context, node)


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    analysis_ops = _analysis_ops()
    corpus = _scoped_corpus_from_inputs(context, inputs)
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    analysis_params = _analysis_params(
        context,
        {
            "topic_algorithm": config.get("topic_algorithm"),
            "topic_model_k": config.get("topic_model_k"),
            "feature_term_count": config.get("feature_term_count"),
        },
    )
    _report_node_progress(context, node, 0.18, "主题模型：准备 TF-IDF 特征")
    payload = _feature_term_payload(
        context,
        corpus,
        {"feature_term_count": analysis_params.get("feature_term_count")},
    )
    _report_node_progress(context, node, 0.55, "主题模型：TF-IDF 特征已生成")
    topic_term_rows, document_topic_rows, topic_summary_rows = analysis_ops.topic_model_tables(
        corpus,
        payload["tfidf_bundle"],
        analysis_params,
        top_terms_per_topic=int(config.get("top_terms_per_topic", 5) or 5),
    )
    _report_node_progress(context, node, 0.92, f"主题模型：生成 {len(topic_summary_rows)} 个主题")
    return {
        "topic_term_table": topic_term_rows,
        "document_topic_table": document_topic_rows,
        "topic_summary_table": topic_summary_rows,
    }


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
