from __future__ import annotations

from typing import Any

from ._common import bool_param, number_param, port, runtime, runtime_section_compiler
from ._support import _clone_corpus_rows, _report_node_progress, _scoped_corpus_from_inputs


def _text_ops():
    from ...analysis import text as text_ops_module
    return text_ops_module


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    filtering = (runtime_profile or {}).get("filtering") or {}
    return {
        "type": "filter_terms",
        "title": "过滤词项",
        "category": "process",
        "description": "去掉过短、过少或不适合分析的词项。",
        "inputs": [
            port("token_corpus_in", "TokenCorpus", "Token 输入")
        ],
        "outputs": [
            port("filtered_token_corpus", "FilteredTokenCorpus", "分析词项")
        ],
        "params": [
            number_param("min_term_frequency", "最小词频", int(filtering.get("min_term_frequency", 1))),
            number_param("min_token_length", "最小词长", int(filtering.get("min_token_length", 2))),
            bool_param("filter_numeric_tokens", "过滤纯数字", bool(filtering.get("filter_numeric_tokens", False))),
            bool_param("filter_by_pos", "按词性过滤", bool(filtering.get("filter_by_pos", False))),
            bool_param("keep_single_char_important_terms", "保留关键单字词", bool(filtering.get("keep_single_char_important_terms", True))),
        ],
        "runtime": runtime(
            "filtering",
            "workflow.filter_terms",
            cacheable=True,
            previewable=True,
        ),
    }


_compile_runtime_section = runtime_section_compiler("filtering", "filtering")


def compile_node(context: Any, node: dict[str, Any]) -> None:
    _compile_runtime_section(context, node)


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    text_ops = _text_ops()
    corpus = _clone_corpus_rows(_scoped_corpus_from_inputs(context, inputs))
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    if params.get("filter_by_pos", False):
        context.warning("当前原生 DAG 运行时尚未实现词性过滤，已按关闭处理。", node)
    _report_node_progress(context, node, 0.25, f"过滤词项：读取 {len(corpus)} 篇文档")
    text_ops.filter_token_lists(corpus, params, context.manifest["dictionary_set"])
    _report_node_progress(context, node, 0.92, f"过滤词项：完成 {len(corpus)} 篇文档")
    context.shared["filtered_corpus"] = corpus
    return {"filtered_token_corpus": corpus}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
