from __future__ import annotations

from copy import deepcopy
from typing import Any

from ._support import (
    _topic_lookup_from_cluster_rows,
    _analysis_ops,
    _analysis_params,
    _feature_term_payload,
    _report_node_progress,
    _scoped_corpus_from_inputs,
)
from ._common import number_param, port, runtime


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    analysis = deepcopy((runtime_profile or {}).get("analysis") or {})
    return {
        "type": "institution_topic_analysis",
        "title": "机构主题分析",
        "category": "analysis",
        "description": "分析机构与主题的关系分布。",
        "inputs": [port("keyword_cluster_table_in", "KeywordClusterTable", "主题输入")],
        "outputs": [
            port(
                "institution_topic_table",
                "InstitutionTopicTable",
                "机构主题表",
                result_bundle_key="institution_topic_cooccurrence",
                png_chart_ids=["institution_topic_heatmap"],
            )
        ],
        "params": [
            number_param("topic_model_k", "主题数量", int(analysis.get("topic_model_k", 4))),
        ],
        "runtime": runtime(
            "analysis",
            "analysis.institution_topic",
            cacheable=True,
            previewable=True,
            parallel_safe=True,
        ),
    }


def compile_node(context: Any, node: dict[str, Any]) -> None:
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    analysis = context.compiled.get("analysis") if isinstance(context.compiled.get("analysis"), dict) else {}
    context.merge_section(
        "analysis",
        {
            "include_institution_topic_analysis": True,
            "include_feature_term_selection": True,
            "include_keyword_clustering": True,
            "topic_model_k": int(config.get("topic_model_k") or analysis.get("topic_model_k", 4)),
        },
    )
    context.enable_step("analysis")


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    analysis_ops = _analysis_ops()
    cluster_rows = inputs.get("keyword_cluster_table_in") or []
    if not isinstance(cluster_rows, list):
        cluster_rows = [cluster_rows]
    corpus = _scoped_corpus_from_inputs(context, inputs)
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    topic_feature_count = len(
        {
            str(row.get("term") or "")
            for row in cluster_rows
            if isinstance(row, dict) and str(row.get("term") or "")
        }
    )
    _report_node_progress(context, node, 0.2, "机构-主题：准备主题特征")
    payload = _feature_term_payload(
        context,
        corpus,
        {"feature_term_count": topic_feature_count or _analysis_params(context).get("feature_term_count")},
    )
    _report_node_progress(context, node, 0.52, "机构-主题：主题特征已生成")
    _, doc_topics = analysis_ops.nmf_topic_model(
        corpus,
        payload["tfidf_bundle"],
        _analysis_params(context, {"topic_model_k": params.get("topic_model_k")}),
    )
    _report_node_progress(context, node, 0.78, "机构-主题：文档主题已计算")
    topic_lookup = _topic_lookup_from_cluster_rows(cluster_rows)
    _, institution_topic_rows = analysis_ops.institution_keyword_and_topic(
        corpus,
        [],
        doc_topics,
        topic_lookup,
    )
    _report_node_progress(context, node, 0.92, f"机构-主题：生成 {len(institution_topic_rows)} 行")
    return {"institution_topic_table": institution_topic_rows}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
