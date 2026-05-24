from __future__ import annotations

from typing import Any

from ._common import enum_param, string_param, port, runtime, node_definition_from_base, passthrough_compiler
from ._support import (
    _clone_corpus_rows,
    _scoped_corpus_from_inputs,
    _report_node_progress,
    _report_corpus_progress,
    _document_field_value,
)


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    base = {
        "type": "deduplicate_documents",
        "title": "文档去重",
        "category": "process",
        "description": "按指定字段组合移除重复文档，保持结果可复现。",
        "inputs": [
            port("corpus_in", "CorpusTable", "语料输入")
        ],
        "outputs": [
            port("deduped_corpus", "CorpusTable", "去重后语料")
        ],
        "params": [
            string_param("dedupe_keys_text", "去重字段", "title,year", ""),
            enum_param(
                "strategy",
                "保留策略",
                "keep_first",
                [("keep_first", "保留首条")],
                "",
            ),
        ],
        "runtime": runtime(
            "scope",
            "scope.deduplicate_documents",
            cacheable=True,
            previewable=True,
            output_node=False,
            parallel_safe=True,
        ),
    }
    return node_definition_from_base(base, runtime_profile, None)


def compile_node(context: Any, node: dict[str, Any]) -> None:
    passthrough_compiler(context, node)


def _dedupe_signature(item: dict[str, Any], keys: list[str]) -> tuple[Any, ...]:
    return tuple(_document_field_value(item, key) for key in keys)


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    corpus = _clone_corpus_rows(_scoped_corpus_from_inputs(context, inputs))
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    dedupe_keys = config.get("dedupe_keys")
    if isinstance(dedupe_keys, list):
        keys = [str(item) for item in dedupe_keys if str(item).strip()]
    else:
        keys = [item.strip() for item in str(config.get("dedupe_keys_text") or "title,year").split(",") if item.strip()]
    _report_node_progress(context, node, 0.2, f"去重文档：读取 {len(corpus)} 篇文档")
    if not keys:
        context.shared["scoped_corpus"] = corpus
        _report_node_progress(context, node, 0.92, "去重文档：未配置键，沿用全部文档")
        return {"deduped_corpus": corpus}
    seen: set[tuple[Any, ...]] = set()
    deduped: list[dict[str, Any]] = []
    total = len(corpus)
    for index, item in enumerate(corpus, start=1):
        signature = _dedupe_signature(item, keys)
        if signature in seen:
            _report_corpus_progress(context, node, index, total, "去重文档")
            continue
        seen.add(signature)
        deduped.append(item)
        _report_corpus_progress(context, node, index, total, "去重文档")
    context.shared["scoped_corpus"] = deduped
    _report_node_progress(context, node, 0.92, f"去重文档：保留 {len(deduped)} / {len(corpus)} 篇")
    return {"deduped_corpus": deduped}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
