from __future__ import annotations

from typing import Any

from ._common import analysis_passthrough_compiler, enum_param, port, runtime, string_param
from ._support import (
    _analysis_ops,
    _join_keys,
    _report_node_progress,
    _table_rows_from_inputs_or_results,
)


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "type": "join_results",
        "title": "连接结果表",
        "category": "analysis",
        "description": "按命名键连接两张结果表，支持内连接与外连接等受控模式。",
        "inputs": [
            port("left_table_in", "AnyTable", "左表"),
            port("right_table_in", "AnyTable", "右表"),
        ],
        "outputs": [
            port("joined_table", "AnyTable", "连接结果表", result_bundle_key="joined_table")
        ],
        "params": [
            string_param("left_artifact", "左侧结果键", "frequency_table"),
            string_param("right_artifact", "右侧结果键", "keyness_table"),
            string_param("join_keys_text", "连接键", "term"),
            enum_param("join_type", "连接方式", "inner", [
                ("inner", "内连接"),
                ("left", "左连接"),
                ("right", "右连接"),
                ("outer", "全连接"),
            ]),
        ],
        "runtime": runtime(
            "analysis",
            "analysis.join_results",
            cacheable=True,
            previewable=True,
            parallel_safe=True,
        ),
    }


def compile_node(context: Any, node: dict[str, Any]) -> None:
    analysis_passthrough_compiler(context, node)


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    analysis_ops = _analysis_ops()
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    left_rows = _table_rows_from_inputs_or_results(context, inputs, "left_table_in", str(config.get("left_artifact") or ""))
    right_rows = _table_rows_from_inputs_or_results(context, inputs, "right_table_in", str(config.get("right_artifact") or ""))
    _report_node_progress(context, node, 0.25, f"合并结果表：读取左表 {len(left_rows)} 行 / 右表 {len(right_rows)} 行")
    joined_rows = analysis_ops.join_table_rows(
        left_rows,
        right_rows,
        _join_keys(config),
        join_type=str(config.get("join_type") or "inner"),
    )
    _report_node_progress(context, node, 0.92, f"合并结果表：生成 {len(joined_rows)} 行")
    return {"joined_table": joined_rows}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
