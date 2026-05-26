from __future__ import annotations

from typing import Any

from ._common import empty_executor, field, graph, noop_compiler, runtime, string_param, ui


def node_definition(_runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "type": "note",
        "title": "注释",
        "category": "utility",
        "description": "给画布上的某段流程添加说明。",
        "inputs": [],
        "outputs": [],
        "params": [string_param("text", "注释内容", "备注")],
        "runtime": runtime("utility", "ui.note", cacheable=False, previewable=False),
        "graph": graph((260, 160), (5760, 40), toolbox_order=900),
        "ui": ui(
            [field("textarea", "text", "注释内容")],
            summary_template="{text}",
        ),
    }


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=noop_compiler,
        executor=empty_executor,
    )
