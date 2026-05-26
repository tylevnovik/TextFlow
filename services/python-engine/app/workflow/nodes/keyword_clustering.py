from __future__ import annotations

from copy import deepcopy
from typing import Any

from ._support import (
    _analysis_ops,
    _feature_term_payload,
    _report_node_progress,
    _scoped_corpus_from_inputs,
)
from ._common import number_param, port, runtime, field, graph, slot, ui


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    analysis = deepcopy((runtime_profile or {}).get("analysis") or {})
    return {
        "type": "keyword_clustering",
        "title": "关键词聚类",
        "category": "analysis",
        "description": "把关键词聚成主题簇，生成标签和代表词。",
        "inputs": [port("feature_term_table_in", "FeatureTermTable", "特征词输入")],
        "outputs": [
            port(
                "keyword_cluster_table",
                "KeywordClusterTable",
                "关键词聚类表",
                result_bundle_key="keyword_cluster_result",
            )
        ],
        "params": [
            number_param("keyword_cluster_k", "关键词聚类数", int(analysis.get("keyword_cluster_k", 4))),
            number_param("topic_model_k", "主题数量", int(analysis.get("topic_model_k", 4))),
        ],
        "runtime": runtime(
            "analysis",
            "analysis.keyword_clustering",
            cacheable=True,
            previewable=True,
            parallel_safe=True,
        ),
        "graph": graph((320, 220), (4080, 680), toolbox_order=370),
        "ui": ui(
            [
                field("number", "keyword_cluster_k", "关键词聚类数", step=1),
                field("number", "topic_model_k", "主题数量", step=1),
            ],
        ),
    }


def compile_node(context: Any, node: dict[str, Any]) -> None:
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    analysis = context.compiled.get("analysis") if isinstance(context.compiled.get("analysis"), dict) else {}
    context.merge_section(
        "analysis",
        {
            "include_keyword_clustering": True,
            "include_feature_term_selection": True,
            "keyword_cluster_k": int(config.get("keyword_cluster_k") or analysis.get("keyword_cluster_k", 4)),
            "topic_model_k": int(config.get("topic_model_k") or analysis.get("topic_model_k", 4)),
        },
    )
    context.enable_step("analysis")


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    analysis_ops = _analysis_ops()
    feature_rows = inputs.get("feature_term_table_in") or []
    if not isinstance(feature_rows, list):
        feature_rows = [feature_rows]
    corpus = _scoped_corpus_from_inputs(context, inputs)
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    selected_count = sum(1 for row in feature_rows if isinstance(row, dict) and row.get("selected"))
    _report_node_progress(context, node, 0.25, "关键词聚类：准备特征向量")
    payload = _feature_term_payload(context, corpus, {"feature_term_count": selected_count or "all"})
    _report_node_progress(context, node, 0.62, "关键词聚类：特征向量已生成")
    cluster_rows, topic_lookup = analysis_ops.keyword_clusters(
        feature_rows,
        payload["tfidf_bundle"],
        int(params.get("keyword_cluster_k", 4) or 4),
    )
    _report_node_progress(context, node, 0.92, f"关键词聚类：生成 {len(cluster_rows)} 行")
    if hasattr(context, "set_shared_value"):
        context.set_shared_value("topic_lookup", topic_lookup)
    else:
        context.shared["topic_lookup"] = topic_lookup
    return {"keyword_cluster_table": cluster_rows}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
