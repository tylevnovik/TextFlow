from __future__ import annotations

from typing import Any

from ._common import analysis_passthrough_compiler, number_param, port, runtime, field, graph, slot, ui
from ._support import _report_node_progress, _table_rows_from_inputs_or_results


def _technology_ops():
    from ...analysis import technology as technology_ops_module
    return technology_ops_module


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "type": "technology_classification",
        "title": "技术分类",
        "category": "analysis",
        "description": "根据技术指标将词项分类为新兴、颠覆性、核心或衰退。",
        "inputs": [
            port("technology_indicator_table_in", "TechnologyIndicatorTable", "技术指标表输入")
        ],
        "outputs": [
            port("technology_classification_table", "TechnologyClassificationTable", "技术分类表", result_bundle_key="technology_classification_table")
        ],
        "params": [
            number_param("threshold_emerging_novelty", "新兴-新颖度阈值", 0.65),
            number_param("threshold_emerging_growth", "新兴-增长率阈值", 1.5),
            number_param("threshold_disruptive", "颠覆-颠覆度阈值", 0.65),
            number_param("threshold_core", "核心-成熟度阈值", 0.65),
            number_param("threshold_declining_growth", "衰退-增长率阈值", 0.75),
            number_param("threshold_declining_maturity", "衰退-成熟度阈值", 0.4),
        ],
        "runtime": runtime(
            "analysis",
            "analysis.technology_classification",
            cacheable=True,
            previewable=True,
            parallel_safe=True,
        ),
        "graph": graph((380, 280), (4920, 1000), toolbox_order=500),
        "ui": ui(
            [
                field("number", "threshold_emerging_novelty", "新兴-新颖度阈值", step=1),
                field("number", "threshold_emerging_growth", "新兴-增长率阈值", step=1),
                field("number", "threshold_disruptive", "颠覆-颠覆度阈值", step=1),
                field("number", "threshold_core", "核心-成熟度阈值", step=1),
                field("number", "threshold_declining_growth", "衰退-增长率阈值", step=1),
                field("number", "threshold_declining_maturity", "衰退-成熟度阈值", step=1),
            ],
        ),
    }


def compile_node(context: Any, node: dict[str, Any]) -> None:
    analysis_passthrough_compiler(context, node)


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    tech_ops = _technology_ops()
    indicator_rows = _table_rows_from_inputs_or_results(context, inputs, "technology_indicator_table_in", "technology_indicator_table")
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    thresholds = {
        "emerging_novelty": config.get("threshold_emerging_novelty", 0.65),
        "emerging_growth": config.get("threshold_emerging_growth", 1.5),
        "disruptive_disruption": config.get("threshold_disruptive", 0.65),
        "core_maturity": config.get("threshold_core", 0.65),
        "declining_growth": config.get("threshold_declining_growth", 0.75),
        "declining_maturity": config.get("threshold_declining_maturity", 0.4),
    }
    _report_node_progress(context, node, 0.25, f"技术分类：读取 {len(indicator_rows)} 条指标")
    rows = tech_ops.technology_classification_rows(indicator_rows, thresholds)
    _report_node_progress(context, node, 0.92, f"技术分类：生成 {len(rows)} 行")
    return {"technology_classification_table": rows}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
