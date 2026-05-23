from __future__ import annotations

from .support import *  # noqa: F401,F403

def _technology_ops():
    from ...analysis import technology as technology_ops_module
    return technology_ops_module


def execute_technology_indicators(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    tech_ops = _technology_ops()
    term_year_rows = _table_rows_from_inputs_or_results(context, inputs, "term_year_table_in", "term_year_table")
    graph_metric_rows = _table_rows_from_inputs_or_results(context, inputs, "graph_metric_table_in", "graph_metric_table")
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    current_year = config.get("indicator_current_year")
    if current_year is None:
        import datetime
        current_year = datetime.datetime.now().year
    _report_node_progress(context, node, 0.25, f"技术指标：读取 {len(term_year_rows)} 条年度记录")
    rows = tech_ops.technology_indicator_rows(
        term_year_rows,
        graph_metric_rows if graph_metric_rows else None,
        current_year=int(current_year),
    )
    _report_node_progress(context, node, 0.92, f"技术指标：生成 {len(rows)} 行")
    return {"technology_indicator_table": rows}


def execute_technology_classification(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
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


