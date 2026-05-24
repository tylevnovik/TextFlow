from __future__ import annotations

from typing import Any

from ._common import analysis_passthrough_compiler, port, runtime
from ._support import _analysis_ops, _report_node_progress


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "type": "cluster_evaluation",
        "title": "聚类评估",
        "category": "analysis",
        "description": "基于现有聚类结果计算轮廓系数、Davies-Bouldin 指标和簇规模分布。",
        "inputs": [
            port("document_cluster_table_in", "DocumentClusterTable", "文档聚类输入")
        ],
        "outputs": [
            port("cluster_evaluation_table", "AnyTable", "聚类评估表", result_bundle_key="cluster_evaluation_table")
        ],
        "params": [],
        "runtime": runtime(
            "analysis",
            "analysis.cluster_evaluation",
            cacheable=True,
            previewable=True,
            parallel_safe=True,
        ),
    }


def compile_node(context: Any, node: dict[str, Any]) -> None:
    analysis_passthrough_compiler(context, node)


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    analysis_ops = _analysis_ops()
    cluster_rows = inputs.get("document_cluster_table_in") or []
    if not isinstance(cluster_rows, list):
        cluster_rows = [cluster_rows] if isinstance(cluster_rows, dict) else []
    _report_node_progress(context, node, 0.35, f"聚类评估：读取 {len(cluster_rows)} 条聚类结果")
    rows = analysis_ops.cluster_evaluation_rows(cluster_rows)
    _report_node_progress(context, node, 0.92, f"聚类评估：生成 {len(rows)} 行")
    return {"cluster_evaluation_table": rows}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
