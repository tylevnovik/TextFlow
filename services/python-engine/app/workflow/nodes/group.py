from __future__ import annotations

from typing import Any

from ._common import empty_executor, field, graph, noop_compiler, runtime, string_param, ui


def node_definition(_runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "type": "group",
        "title": "分组",
        "category": "utility",
        "description": "用于整理节点区域和视觉分组。",
        "inputs": [],
        "outputs": [],
        "params": [string_param("title", "分组标题", "分组")],
        "runtime": runtime("utility", "ui.group", cacheable=False, previewable=False),
        "graph": graph((280, 180), (5760, 360), toolbox_order=910),
        "ui": ui(
            [field("text", "title", "分组标题")],
            summary_template="{title}",
        ),
    }


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=noop_compiler,
        executor=empty_executor,
    )
