from __future__ import annotations

from copy import deepcopy
from typing import Any

from ._support import _analysis_ops, _report_node_progress, _scoped_corpus_from_inputs, _token_frame
from ._common import number_param, port, runtime, field, graph, slot, ui


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    analysis = deepcopy((runtime_profile or {}).get("analysis") or {})
    return {
        "type": "frequency_statistics",
        "title": "词频统计",
        "category": "analysis",
        "description": "生成高频词、文档频次和占比统计。",
        "inputs": [port("token_corpus_in", "FilteredTokenCorpus", "分析词项")],
        "outputs": [
            port(
                "frequency_table",
                "FrequencyTable",
                "词频表",
                result_bundle_key="frequency_table",
                png_chart_ids=["frequency_top_terms"],
            )
        ],
        "params": [
            number_param("top_n", "Top N", int(analysis.get("top_n", 200))),
        ],
        "runtime": runtime(
            "analysis",
            "analysis.frequency_statistics",
            cacheable=True,
            previewable=True,
            parallel_safe=True,
        ),
        "graph": graph((280, 210), (3660, 40), toolbox_order=290),
        "ui": ui(
            [
                field("number", "top_n", "Top N", step=1),
            ],
        ),
    }


def compile_node(context: Any, node: dict[str, Any]) -> None:
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    analysis = context.compiled.get("analysis") if isinstance(context.compiled.get("analysis"), dict) else {}
    context.merge_section(
        "analysis",
        {
            "include_frequency_statistics": True,
            "top_n": int(config.get("top_n") or analysis.get("top_n", 200)),
        },
    )
    context.enable_step("analysis")


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    analysis_ops = _analysis_ops()
    corpus = _scoped_corpus_from_inputs(context, inputs)
    _report_node_progress(context, node, 0.2, "词频统计：准备词项表")
    df_tokens = _token_frame(context, corpus)
    _report_node_progress(context, node, 0.65, f"词频统计：已展开 {len(df_tokens)} 条词项")
    rows = analysis_ops.frequency_table(df_tokens)
    _report_node_progress(context, node, 0.92, f"词频统计：生成 {len(rows)} 行")
    return {"frequency_table": rows}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
