from __future__ import annotations

from copy import deepcopy
from typing import Any

from ._support import _feature_term_payload, _report_node_progress, _scoped_corpus_from_inputs
from ._common import enum_param, port, runtime


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    analysis = deepcopy((runtime_profile or {}).get("analysis") or {})
    return {
        "type": "feature_term_selection",
        "title": "特征词筛选",
        "category": "analysis",
        "description": "从语料中筛出进入后续聚类和主题建模的特征词。",
        "inputs": [port("token_corpus_in", "FilteredTokenCorpus", "分析词项")],
        "outputs": [
            port(
                "feature_term_table",
                "FeatureTermTable",
                "特征词表",
                result_bundle_key="selected_feature_terms",
            )
        ],
        "params": [
            enum_param(
                "feature_term_count",
                "特征词规模",
                str(analysis.get("feature_term_count", 1000)),
                [("100", "Top 100"), ("500", "Top 500"), ("1000", "Top 1000"), ("all", "全部")],
            ),
        ],
        "runtime": runtime(
            "analysis",
            "analysis.feature_terms",
            cacheable=True,
            previewable=True,
            parallel_safe=True,
        ),
    }


def compile_node(context: Any, node: dict[str, Any]) -> None:
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    raw_value = config.get("feature_term_count")
    analysis = context.compiled.get("analysis") if isinstance(context.compiled.get("analysis"), dict) else {}
    feature_term_count = "all" if str(raw_value) == "all" else int(raw_value or analysis.get("feature_term_count", 1000))
    context.merge_section(
        "analysis",
        {
            "include_feature_term_selection": True,
            "feature_term_count": feature_term_count,
        },
    )
    context.enable_step("analysis")


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    corpus = _scoped_corpus_from_inputs(context, inputs)
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    _report_node_progress(context, node, 0.25, "特征词筛选：准备 TF-IDF 特征")
    payload = _feature_term_payload(context, corpus, {"feature_term_count": params.get("feature_term_count")})
    _report_node_progress(context, node, 0.92, f"特征词筛选：输出 {len(payload['feature_rows'])} 个候选词")
    return {"feature_term_table": payload["feature_rows"]}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
