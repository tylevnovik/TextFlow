from __future__ import annotations

import random
from typing import Any

from ._common import enum_param, number_param, string_param, port, runtime, node_definition_from_base, analysis_passthrough_compiler
from ._support import (
    _clone_corpus_rows,
    _scoped_corpus_from_inputs,
    _report_node_progress,
)


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    base = {
        "type": "split_corpus",
        "title": "语料切分",
        "category": "analysis",
        "description": "按命名分组输出语料切分分配表，而不是复制多份全文数据。",
        "inputs": [
            port("corpus_in", "CorpusTable", "语料输入")
        ],
        "outputs": [
            port(
                "split_assignment_table",
                "AnyTable",
                "切分分配表",
                result_bundle_key="split_assignments",
            )
        ],
        "params": [
            enum_param(
                "split_strategy",
                "切分方式",
                "ratio",
                [("ratio", "按比例")],
                "",
            ),
            string_param("splits_text", "切分定义", "train:0.7\ntest:0.3", ""),
            number_param("seed", "随机种子", 42, ""),
        ],
        "runtime": runtime(
            "analysis",
            "analysis.split_corpus",
            cacheable=True,
            previewable=True,
            output_node=False,
            parallel_safe=True,
        ),
    }
    return node_definition_from_base(base, runtime_profile, None)


def compile_node(context: Any, node: dict[str, Any]) -> None:
    analysis_passthrough_compiler(context, node)


def _normalize_split_definitions(config: dict[str, Any]) -> list[tuple[str, float]]:
    raw_splits = config.get("splits")
    if isinstance(raw_splits, list):
        normalized = [
            (str(item.get("name") or ""), float(item.get("ratio") or 0))
            for item in raw_splits
            if isinstance(item, dict) and str(item.get("name") or "").strip()
        ]
        if normalized:
            return normalized
    splits_text = str(config.get("splits_text") or "train:0.7\ntest:0.3")
    splits: list[tuple[str, float]] = []
    for line in splits_text.splitlines():
        if ":" not in line:
            continue
        name, raw_ratio = line.split(":", 1)
        name = name.strip()
        if not name:
            continue
        try:
            ratio = float(raw_ratio.strip())
        except ValueError:
            continue
        splits.append((name, ratio))
    return splits


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    corpus = _clone_corpus_rows(_scoped_corpus_from_inputs(context, inputs))
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    splits = _normalize_split_definitions(config)
    _report_node_progress(context, node, 0.2, f"划分语料：读取 {len(corpus)} 篇文档")
    if not corpus or not splits:
        _report_node_progress(context, node, 0.92, "划分语料：无可用划分")
        return {"split_assignment_table": []}
    seed = int(config.get("seed", 42) or 42)
    rng = random.Random(seed)
    ordered_indices = list(range(len(corpus)))
    rng.shuffle(ordered_indices)
    total_ratio = sum(max(ratio, 0.0) for _, ratio in splits) or float(len(splits))
    assignments: list[dict[str, Any]] = []
    offset = 0
    for index, (name, ratio) in enumerate(splits):
        if index == len(splits) - 1:
            bucket_indices = ordered_indices[offset:]
        else:
            bucket_size = round(len(corpus) * (max(ratio, 0.0) / total_ratio))
            bucket_indices = ordered_indices[offset : offset + bucket_size]
        for item_index in bucket_indices:
            item = corpus[item_index]
            assignments.append(
                {
                    "doc_id": item.get("doc_id"),
                    "title": item.get("title"),
                    "split_name": name,
                }
            )
        offset += len(bucket_indices)
        _report_node_progress(
            context,
            node,
            0.25 + 0.62 * (index + 1) / max(len(splits), 1),
            f"划分语料：完成 {index + 1}/{len(splits)} 个集合",
        )
    assignments.sort(key=lambda item: str(item.get("doc_id") or ""))
    _report_node_progress(context, node, 0.92, f"划分语料：生成 {len(assignments)} 条分配")
    return {"split_assignment_table": assignments}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
