from __future__ import annotations

import random
from typing import Any

from ._common import enum_param, number_param, port, runtime, node_definition_from_base, passthrough_compiler, field, graph, slot, ui
from ._support import (
    _clone_corpus_rows,
    _scoped_corpus_from_inputs,
    _report_node_progress,
)


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    base = {
        "type": "sample_corpus",
        "title": "语料抽样",
        "category": "process",
        "description": "按固定随机种子抽取样本，支持数量或比例模式。",
        "inputs": [
            port("corpus_in", "CorpusTable", "语料输入")
        ],
        "outputs": [
            port("sampled_corpus", "CorpusTable", "抽样后语料")
        ],
        "params": [
            enum_param(
                "sample_mode",
                "抽样方式",
                "random",
                [("random", "随机抽样")],
                "",
            ),
            number_param("sample_size", "样本数量", 200, ""),
            number_param("sample_ratio", "抽样比例", None, ""),
            number_param("seed", "随机种子", 42, ""),
        ],
        "runtime": runtime(
            "scope",
            "scope.sample_corpus",
            cacheable=True,
            previewable=True,
            output_node=False,
            parallel_safe=True,
        ),
        "graph": graph((320, 240), (1080, 820), toolbox_order=180),
        "ui": ui(
            [
                field("select", "sample_mode", "抽样方式"),
                field("number", "sample_size", "样本数量", step=1),
                field("number", "sample_ratio", "抽样比例", step=1),
                field("number", "seed", "随机种子", step=1),
            ],
        ),
    }
    return node_definition_from_base(base, runtime_profile, None)


def compile_node(context: Any, node: dict[str, Any]) -> None:
    passthrough_compiler(context, node)


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    corpus = _clone_corpus_rows(_scoped_corpus_from_inputs(context, inputs))
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    _report_node_progress(context, node, 0.2, f"抽样语料：读取 {len(corpus)} 篇文档")
    if not corpus:
        _report_node_progress(context, node, 0.92, "抽样语料：无文档可抽样")
        return {"sampled_corpus": []}
    seed = int(config.get("seed", 42) or 42)
    sample_ratio = config.get("sample_ratio")
    sample_size = config.get("sample_size")
    if sample_ratio not in (None, ""):
        requested = max(0, min(len(corpus), round(len(corpus) * float(sample_ratio))))
    else:
        requested = max(0, min(len(corpus), int(sample_size or len(corpus))))
    _report_node_progress(context, node, 0.55, f"抽样语料：目标 {requested} 篇")
    if requested >= len(corpus):
        sampled = corpus
    else:
        rng = random.Random(seed)
        sampled = [corpus[index] for index in sorted(rng.sample(range(len(corpus)), requested))]
    context.shared["scoped_corpus"] = sampled
    _report_node_progress(context, node, 0.92, f"抽样语料：输出 {len(sampled)} 篇")
    return {"sampled_corpus": sampled}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
