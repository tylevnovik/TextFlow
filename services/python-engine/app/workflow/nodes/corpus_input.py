from __future__ import annotations

from typing import Any

from ._common import enum_param, number_param, port, runtime, node_definition_from_base, scope_compiler
from ._support import _runtime_support, _report_node_progress


_RUNTIME_PARAM_DEFAULTS = {'year_from': ('run_scope', 'year_from'), 'year_to': ('run_scope', 'year_to')}


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    base = {
        "type": "corpus_input",
        "title": "语料输入",
        "category": "input",
        "description": "选择项目语料，并在节点内圈定本次处理的文档范围。",
        "inputs": [],
        "outputs": [
            port("corpus", "CorpusTable", "语料")
        ],
        "params": [
            enum_param(
                "resource_mode",
                "资源来源",
                "project_corpus",
                [("project_corpus", "项目语料")],
                "MVP 先固定引用项目语料。",
            ),
            enum_param(
                "mode",
                "处理范围",
                "all_documents",
                [
                    ("all_documents", "全部文档"),
                    ("filtered_subset", "筛选子集"),
                    ("selected_documents", "指定文档"),
                ],
                "",
            ),
            number_param("year_from", "起始年份", None, ""),
            number_param("year_to", "结束年份", None, ""),
        ],
        "runtime": runtime(
            "scope",
            "scope.select_corpus",
            cacheable=False,
            previewable=True,
            output_node=False,
        ),
    }
    return node_definition_from_base(base, runtime_profile, _RUNTIME_PARAM_DEFAULTS)


def compile_node(context: Any, node: dict[str, Any]) -> None:
    scope_compiler(context, node)


def execute_node(context: Any, node: dict[str, Any], _inputs: dict[str, Any]) -> dict[str, Any]:
    runtime_support = _runtime_support()
    scope = runtime_support.normalize_run_scope(node.get("config") if isinstance(node.get("config"), dict) else {})
    _report_node_progress(context, node, 0.25, f"语料输入：读取 {len(context.full_corpus)} 篇文档")
    scoped = [item for item in context.full_corpus if runtime_support.document_matches_scope(item, scope)]
    context.shared["run_scope"] = scope
    context.shared["run_scope_summary"] = runtime_support.describe_run_scope(scope, len(context.full_corpus), len(scoped))
    context.shared["scoped_corpus"] = scoped
    _report_node_progress(context, node, 0.92, f"语料输入：命中 {len(scoped)} 篇文档")
    return {"corpus": scoped}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
