from __future__ import annotations

from typing import Any

from ._common import enum_param, number_param, string_param, port, runtime, node_definition_from_base, analysis_passthrough_compiler, field, graph, slot, ui
from ._support import (
    _control_rows_from_inputs,
    _compare_control_value,
    _report_node_progress,
    _shared_get,
    _control_rows_from_value,
    _record_field_value,
)


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    base = {
        "type": "result_gate",
        "title": "结果门禁",
        "category": "analysis",
        "description": "根据上游结果表中的摘要指标决定是否放行下游表格。",
        "inputs": [
            port("metric_table_in", "AnyTable", "指标表"),
            port("payload_in", "AnyTable", "待放行表格"),
        ],
        "outputs": [
            port("passed_table", "AnyTable", "放行表格"),
            port("blocked_table", "AnyTable", "拦截表格"),
            port(
                "gate_summary",
                "AnyTable",
                "门禁摘要",
                result_bundle_key="result_gate_summary",
            ),
        ],
        "params": [
            string_param("metric_artifact", "指标产物", "cluster_evaluation_table", ""),
            string_param("metric_name", "指标名", "silhouette_score", ""),
            string_param("metric_name_field", "指标名字段", "metric", ""),
            string_param("metric_field", "指标值字段", "value", ""),
            enum_param(
                "operator",
                "判断条件",
                "gte",
                [
                    ("gte", "大于等于"),
                    ("gt", "大于"),
                    ("lte", "小于等于"),
                    ("lt", "小于"),
                    ("eq", "等于"),
                    ("neq", "不等于"),
                ],
                "",
            ),
            number_param("threshold", "阈值", 0.5, ""),
        ],
        "runtime": runtime(
            "analysis",
            "control.result_gate",
            cacheable=True,
            previewable=True,
            output_node=False,
        ),
        "graph": graph((360, 280), (4920, 1320), toolbox_order=520),
        "ui": ui(
            [
                slot("threshold_gate_editor"),
            ],
        ),
    }
    return node_definition_from_base(base, runtime_profile, None)


def compile_node(context: Any, node: dict[str, Any]) -> None:
    analysis_passthrough_compiler(context, node)


def _metric_rows_from_context(context: Any, config: dict[str, Any]) -> list[dict[str, Any]]:
    artifact_key = str(config.get("metric_artifact") or "").strip()
    if not artifact_key:
        return []
    bundle = getattr(context, "result_bundle", {})
    if isinstance(bundle, dict):
        rows = _control_rows_from_value(bundle.get(artifact_key))
        if rows:
            return rows
    return _control_rows_from_value(_shared_get(context, artifact_key))


def _select_metric_row(rows: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    metric_name = str(config.get("metric_name") or "").strip()
    metric_name_field = str(config.get("metric_name_field") or "metric").strip()
    if metric_name:
        for row in rows:
            if str(_record_field_value(row, metric_name_field) or "") == metric_name:
                return row
        for row in rows:
            if metric_name in row:
                return row
    for row in rows:
        if str(row.get("row_type") or "").lower() == "overall":
            return row
    return rows[0] if rows else {}


def _metric_observed_value(row: dict[str, Any], config: dict[str, Any]) -> Any:
    metric_field = str(config.get("metric_field") or "value").strip()
    metric_name = str(config.get("metric_name") or "").strip()
    value = _record_field_value(row, metric_field)
    if value is None and metric_name:
        value = _record_field_value(row, metric_name)
    return value


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    metric_rows = _control_rows_from_inputs(inputs, "metric_table_in", "table_in") or _metric_rows_from_context(context, config)
    payload_rows = _control_rows_from_inputs(inputs, "payload_in") or metric_rows
    _report_node_progress(context, node, 0.25, f"结果闸门：读取 {len(metric_rows)} 条指标")
    metric_row = _select_metric_row(metric_rows, config)
    observed_value = _metric_observed_value(metric_row, config)
    threshold = config.get("threshold")
    passed = _compare_control_value(observed_value, str(config.get("operator") or "gte"), [threshold])
    _report_node_progress(context, node, 0.72, f"结果闸门：判定 {'通过' if passed else '阻断'}")
    metric_name = str(config.get("metric_name") or config.get("metric_field") or "metric")
    gate_summary = [
        {
            "metric": metric_name,
            "metric_field": str(config.get("metric_field") or "value"),
            "operator": str(config.get("operator") or "gte"),
            "threshold": threshold,
            "observed_value": observed_value,
            "passed": passed,
            "input_count": len(payload_rows),
        }
    ]
    return {
        "passed": passed,
        "passed_table": payload_rows if passed else [],
        "blocked_table": [] if passed else payload_rows,
        "gate_summary": gate_summary,
    }


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
