from __future__ import annotations

from typing import Any

from ._common import analysis_passthrough_compiler, enum_param, number_param, port, runtime, string_param
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
        "type": "similarity_analysis",
        "title": "相似度计算",
        "category": "analysis",
        "description": "基于词项表示计算文档间相似度，输出可审计的文档对得分。",
        "inputs": [
            port("token_corpus_in", "FilteredTokenCorpus", "分析词项")
        ],
        "outputs": [
            port("similarity_table", "AnyTable", "相似度表", result_bundle_key="similarity_table")
        ],
        "params": [
            enum_param("similarity_method", "相似度算法", analysis.get("similarity_method", "cosine"), [
                ("cosine", "Cosine"),
            ]),
            number_param("min_similarity", "最小相似度", float(analysis.get("min_similarity", 0.2))),
            number_param("similarity_top_k", "最多文档对", int(analysis.get("similarity_top_k", 200))),
            string_param("feature_term_count", "特征词数量", str(analysis.get("feature_term_count", "1000"))),
        ],
        "runtime": runtime(
            "analysis",
            "analysis.similarity",
            cacheable=True,
            previewable=True,
            parallel_safe=True,
        ),
    }


def compile_node(context: Any, node: dict[str, Any]) -> None:
    analysis_passthrough_compiler(context, node)


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    analysis_ops = _analysis_ops()
    corpus = _scoped_corpus_from_inputs(context, inputs)
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    analysis_params = _analysis_params(
        context,
        {
            "feature_term_count": params.get("feature_term_count"),
            "similarity_method": params.get("similarity_method"),
            "min_similarity": params.get("min_similarity"),
            "similarity_top_k": params.get("similarity_top_k"),
        },
    )
    _report_node_progress(context, node, 0.2, "相似度计算：准备 TF-IDF 特征")
    payload = _feature_term_payload(
        context,
        corpus,
        {"feature_term_count": analysis_params.get("feature_term_count")},
    )
    _report_node_progress(context, node, 0.62, "相似度计算：TF-IDF 特征已生成")
    rows = analysis_ops.document_similarity_rows(
        corpus,
        payload["tfidf_bundle"],
        analysis_params,
    )
    _report_node_progress(context, node, 0.92, f"相似度计算：输出 {len(rows)} 个文档对")
    return {"similarity_table": rows}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
