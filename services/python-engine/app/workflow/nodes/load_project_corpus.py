from __future__ import annotations

from typing import Any

from ._common import port, runtime, node_definition_from_base, passthrough_compiler
from .corpus_input import execute_node as _execute_node


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    base = {
        "type": "load_project_corpus",
        "title": "读取项目语料",
        "category": "legacy",
        "description": "旧版兼容节点：已由语料输入替代。",
        "hidden_from_toolbox": True,
        "inputs": [],
        "outputs": [
            port("project_corpus", "ProjectCorpus", "项目语料")
        ],
        "params": [],
        "runtime": runtime(
            "resource",
            "legacy.load_project_corpus",
            cacheable=False,
            previewable=False,
            output_node=False,
        ),
    }
    return node_definition_from_base(base, runtime_profile, None)


def compile_node(context: Any, node: dict[str, Any]) -> None:
    passthrough_compiler(context, node)


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    return _execute_node(context, node, inputs)


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
