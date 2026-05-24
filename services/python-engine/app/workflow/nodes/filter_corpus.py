from __future__ import annotations

from typing import Any

from ._common import port, runtime, node_definition_from_base, scope_compiler
from ._support import _runtime_support, _scoped_corpus_from_inputs, _report_node_progress


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    base = {
        "type": "filter_corpus",
        "title": "筛选处理对象",
        "category": "legacy",
        "description": "旧版兼容节点：已并入语料输入节点。",
        "hidden_from_toolbox": True,
        "inputs": [
            port("project_corpus_in", "ProjectCorpus", "项目语料")
        ],
        "outputs": [
            port("scoped_corpus", "ScopedCorpus", "筛选后语料")
        ],
        "params": [],
        "runtime": runtime(
            "scope",
            "legacy.filter_corpus",
            cacheable=False,
            previewable=False,
            output_node=False,
        ),
    }
    return node_definition_from_base(base, runtime_profile, None)


def compile_node(context: Any, node: dict[str, Any]) -> None:
    scope_compiler(context, node)


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    runtime_support = _runtime_support()
    scope = runtime_support.normalize_run_scope(node.get("config") if isinstance(node.get("config"), dict) else {})
    corpus = _scoped_corpus_from_inputs(context, inputs)
    _report_node_progress(context, node, 0.25, f"筛选语料：读取 {len(corpus)} 篇文档")
    scoped = [item for item in corpus if runtime_support.document_matches_scope(item, scope)]
    context.shared["run_scope"] = scope
    context.shared["run_scope_summary"] = runtime_support.describe_run_scope(scope, len(context.full_corpus), len(scoped))
    context.shared["scoped_corpus"] = scoped
    _report_node_progress(context, node, 0.92, f"筛选语料：命中 {len(scoped)} 篇文档")
    return {"corpus": scoped}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
