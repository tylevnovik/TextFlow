from __future__ import annotations

from copy import deepcopy
from typing import Any

from ._support import _analysis_ops, _feature_term_payload, _report_node_progress, _scoped_corpus_from_inputs
from ._common import number_param, port, runtime, field, graph, slot, ui


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    analysis = deepcopy((runtime_profile or {}).get("analysis") or {})
    return {
        "type": "document_clustering",
        "title": "文档聚类",
        "category": "analysis",
        "description": "对文档做向量聚类，生成散点结果与簇标签。",
        "inputs": [port("token_corpus_in", "FilteredTokenCorpus", "分析词项")],
        "outputs": [
            port(
                "document_cluster_table",
                "DocumentClusterTable",
                "文档聚类表",
                result_bundle_key="clustering_result",
                png_chart_ids=["document_clusters"],
            )
        ],
        "params": [
            number_param("document_cluster_k", "文档聚类数", int(analysis.get("document_cluster_k", 4))),
        ],
        "runtime": runtime(
            "analysis",
            "analysis.document_clustering",
            cacheable=True,
            previewable=True,
            parallel_safe=True,
        ),
        "graph": graph((300, 210), (4500, 360), toolbox_order=420),
        "ui": ui(
            [
                field("number", "document_cluster_k", "文档聚类数", step=1),
            ],
        ),
    }


def compile_node(context: Any, node: dict[str, Any]) -> None:
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    analysis = context.compiled.get("analysis") if isinstance(context.compiled.get("analysis"), dict) else {}
    context.merge_section(
        "analysis",
        {
            "include_document_clustering": True,
            "document_cluster_k": int(config.get("document_cluster_k") or analysis.get("document_cluster_k", 4)),
        },
    )
    context.enable_step("analysis")


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    analysis_ops = _analysis_ops()
    corpus = _scoped_corpus_from_inputs(context, inputs)
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    _report_node_progress(context, node, 0.25, "文档聚类：准备文档向量")
    payload = _feature_term_payload(context, corpus)
    _report_node_progress(context, node, 0.62, "文档聚类：文档向量已生成")
    rows = analysis_ops.document_clusters(
        corpus,
        payload["tfidf_bundle"],
        int(params.get("document_cluster_k", 4) or 4),
    )
    _report_node_progress(context, node, 0.92, f"文档聚类：生成 {len(rows)} 行")
    return {"document_cluster_table": rows}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
