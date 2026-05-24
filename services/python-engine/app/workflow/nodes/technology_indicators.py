from __future__ import annotations

import datetime
from typing import Any

from ._common import analysis_passthrough_compiler, number_param, port, runtime
from ._support import _report_node_progress, _table_rows_from_inputs_or_results


def _technology_ops():
    from ...analysis import technology as technology_ops_module
    return technology_ops_module


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "type": "technology_indicators",
        "title": "技术指标",
        "category": "analysis",
        "description": "基于词项年份趋势和网络指标计算新颖度、颠覆度和成熟度。",
        "inputs": [
            port("term_year_table_in", "TermYearTable", "词项年份表输入"),
            port("graph_metric_table_in", "GraphMetricTable", "网络指标输入"),
        ],
        "outputs": [
            port("technology_indicator_table", "TechnologyIndicatorTable", "技术指标表", result_bundle_key="technology_indicator_table")
        ],
        "params": [
            number_param("indicator_current_year", "当前年份", None),
        ],
        "runtime": runtime(
            "analysis",
            "analysis.technology_indicators",
            cacheable=True,
            previewable=True,
            parallel_safe=True,
        ),
    }


def compile_node(context: Any, node: dict[str, Any]) -> None:
    analysis_passthrough_compiler(context, node)


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    tech_ops = _technology_ops()
    term_year_rows = _table_rows_from_inputs_or_results(context, inputs, "term_year_table_in", "term_year_table")
    graph_metric_rows = _table_rows_from_inputs_or_results(context, inputs, "graph_metric_table_in", "graph_metric_table")
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    current_year = config.get("indicator_current_year")
    if current_year is None:
        current_year = datetime.datetime.now().year
    _report_node_progress(context, node, 0.25, f"技术指标：读取 {len(term_year_rows)} 条年度记录")
    rows = tech_ops.technology_indicator_rows(
        term_year_rows,
        graph_metric_rows if graph_metric_rows else None,
        current_year=int(current_year),
    )
    _report_node_progress(context, node, 0.92, f"技术指标：生成 {len(rows)} 行")
    return {"technology_indicator_table": rows}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
