from __future__ import annotations

from copy import deepcopy
from typing import Any

from ._support import _keyword_payload, _report_node_progress, _scoped_corpus_from_inputs
from ._common import number_param, port, runtime, field, graph, slot, ui


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    analysis = deepcopy((runtime_profile or {}).get("analysis") or {})
    return {
        "type": "keyword_extraction",
        "title": "关键词提取",
        "category": "analysis",
        "description": "从语料中抽取项目级和文档级关键词。",
        "inputs": [port("token_corpus_in", "FilteredTokenCorpus", "分析词项")],
        "outputs": [
            port(
                "keyword_table",
                "KeywordTable",
                "关键词表",
                result_bundle_key="keyword_result",
                png_chart_ids=["project_keywords", "keyword_wordcloud"],
            )
        ],
        "params": [
            number_param("top_k_per_doc", "每文档关键词数", int(analysis.get("top_k_per_doc", 10))),
            number_param("top_k_project", "项目关键词数", int(analysis.get("top_k_project", 100))),
        ],
        "runtime": runtime(
            "analysis",
            "analysis.keyword_extraction",
            cacheable=True,
            previewable=True,
            parallel_safe=True,
        ),
        "graph": graph((320, 220), (4080, 360), toolbox_order=360),
        "ui": ui(
            [
                field("number", "top_k_per_doc", "每文档关键词数", step=1),
                field("number", "top_k_project", "项目关键词数", step=1),
            ],
        ),
    }


def compile_node(context: Any, node: dict[str, Any]) -> None:
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    analysis = context.compiled.get("analysis") if isinstance(context.compiled.get("analysis"), dict) else {}
    context.merge_section(
        "analysis",
        {
            "include_keyword_extraction": True,
            "top_k_per_doc": int(config.get("top_k_per_doc") or analysis.get("top_k_per_doc", 10)),
            "top_k_project": int(config.get("top_k_project") or analysis.get("top_k_project", 100)),
        },
    )
    context.enable_step("analysis")


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    corpus = _scoped_corpus_from_inputs(context, inputs)
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    _report_node_progress(context, node, 0.2, f"关键词提取：读取 {len(corpus)} 篇文档")
    payload = _keyword_payload(
        context,
        node,
        corpus,
        {
            "top_k_per_doc": params.get("top_k_per_doc"),
            "top_k_project": params.get("top_k_project"),
        },
    )
    _report_node_progress(context, node, 0.92, f"关键词提取：生成 {len(payload['keyword_rows'])} 行")
    return {"keyword_table": payload["keyword_rows"]}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
