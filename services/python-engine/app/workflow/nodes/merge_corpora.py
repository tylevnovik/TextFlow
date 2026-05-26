from __future__ import annotations

from typing import Any

from ._common import enum_param, port, runtime, node_definition_from_base, passthrough_compiler, field, graph, slot, ui
from ._support import _report_node_progress


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    base = {
        "type": "merge_corpora",
        "title": "合并语料",
        "category": "process",
        "description": "把多路语料汇合成一路，供下游统一处理。",
        "hidden_from_toolbox": True,
        "inputs": [
            port("corpus_in", "CorpusTable", "输入语料", allow_multiple=True)
        ],
        "outputs": [
            port("corpus", "CorpusTable", "合并后语料")
        ],
        "params": [
            enum_param(
                "strategy",
                "合并策略",
                "append",
                [("append", "追加"), ("dedupe", "去重追加")],
                "",
            )
        ],
        "runtime": runtime(
            "merge",
            "graph.merge_corpora",
            cacheable=False,
            previewable=True,
            output_node=False,
        ),
        "graph": graph((300, 210), (640, 480), toolbox_order=130),
        "ui": ui(
            [
                field("select", "strategy", "合并策略"),
            ],
        ),
    }
    return node_definition_from_base(base, runtime_profile, None)


def compile_node(context: Any, node: dict[str, Any]) -> None:
    passthrough_compiler(context, node)


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    corpora = inputs.get("corpus_in") or []
    if isinstance(corpora, dict):
        corpora = [corpora]
    merged: list[dict[str, Any]] = []
    seen_doc_ids: set[str] = set()
    strategy = str((node.get("config") or {}).get("strategy") or "append")
    list_corpora = [corpus for corpus in corpora if isinstance(corpus, list)]
    total_corpora = len(list_corpora)
    for corpus_index, corpus in enumerate(list_corpora, start=1):
        if not isinstance(corpus, list):
            continue
        for item in corpus:
            if not isinstance(item, dict):
                continue
            doc_id = str(item.get("doc_id") or item.get("id") or "")
            if strategy == "dedupe" and doc_id and doc_id in seen_doc_ids:
                continue
            merged.append(item)
            if doc_id:
                seen_doc_ids.add(doc_id)
        _report_node_progress(
            context,
            node,
            0.2 + 0.7 * corpus_index / max(total_corpora, 1),
            f"合并语料：完成 {corpus_index}/{total_corpora} 路输入",
        )
    context.shared["scoped_corpus"] = merged
    _report_node_progress(context, node, 0.92, f"合并语料：输出 {len(merged)} 篇文档")
    return {"corpus": merged}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
