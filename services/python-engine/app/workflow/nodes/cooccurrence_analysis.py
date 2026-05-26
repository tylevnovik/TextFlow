from __future__ import annotations

from copy import deepcopy
from typing import Any

from ._support import _analysis_ops, _report_node_progress, _scoped_corpus_from_inputs
from ._common import number_param, port, runtime, field, graph, slot, ui


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    analysis = deepcopy((runtime_profile or {}).get("analysis") or {})
    return {
        "type": "cooccurrence_analysis",
        "title": "共现分析",
        "category": "analysis",
        "description": "统计词项在窗口内的共现关系。",
        "inputs": [port("token_corpus_in", "FilteredTokenCorpus", "分析词项")],
        "outputs": [
            port(
                "cooccurrence_table",
                "CooccurrenceTable",
                "共现表",
                result_bundle_key="cooccurrence_table",
            )
        ],
        "params": [
            number_param("cooccurrence_window", "共现窗口", int(analysis.get("cooccurrence_window", 5))),
            number_param("min_cooccurrence", "最小共现次数", int(analysis.get("min_cooccurrence", 2))),
        ],
        "runtime": runtime(
            "analysis",
            "analysis.cooccurrence",
            cacheable=True,
            previewable=True,
            parallel_safe=True,
        ),
        "graph": graph((320, 230), (3660, 1000), toolbox_order=320),
        "ui": ui(
            [
                field("number", "cooccurrence_window", "共现窗口", step=1),
                field("number", "min_cooccurrence", "最小共现次数", step=1),
            ],
        ),
    }


def compile_node(context: Any, node: dict[str, Any]) -> None:
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    analysis = context.compiled.get("analysis") if isinstance(context.compiled.get("analysis"), dict) else {}
    context.merge_section(
        "analysis",
        {
            "include_cooccurrence_analysis": True,
            "cooccurrence_window": int(config.get("cooccurrence_window") or analysis.get("cooccurrence_window", 5)),
            "min_cooccurrence": int(config.get("min_cooccurrence") or analysis.get("min_cooccurrence", 2)),
        },
    )
    context.enable_step("analysis")


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    analysis_ops = _analysis_ops()
    corpus = _scoped_corpus_from_inputs(context, inputs)
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    _report_node_progress(context, node, 0.15, f"共现分析：读取 {len(corpus)} 篇文档")
    rows = analysis_ops.cooccurrence_table(
        corpus,
        int(params.get("cooccurrence_window", 5) or 5),
        int(params.get("min_cooccurrence", 2) or 2),
        progress_callback=lambda current, total: _report_node_progress(
            context,
            node,
            0.15 + 0.72 * current / max(total, 1),
            f"共现分析：处理 {current}/{total} 篇文档",
        ),
    )
    _report_node_progress(context, node, 0.92, f"共现分析：生成 {len(rows)} 行")
    return {"cooccurrence_table": rows}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
