from __future__ import annotations

from typing import Any

from ._common import enum_param, string_param, port, runtime, node_definition_from_base, analysis_passthrough_compiler
from ._support import (
    _clone_corpus_rows,
    _scoped_corpus_from_inputs,
    _report_node_progress,
    _document_field_value,
    _report_corpus_progress,
)


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    base = {
        "type": "bucket_by_time",
        "title": "时间分桶",
        "category": "analysis",
        "description": "把年份或时间字段映射到可复用的时间桶，便于后续比较。",
        "inputs": [
            port("corpus_in", "CorpusTable", "语料输入")
        ],
        "outputs": [
            port(
                "time_bucket_table",
                "AnyTable",
                "时间分桶表",
                result_bundle_key="time_bucket_assignments",
            )
        ],
        "params": [
            string_param("field", "时间字段", "year", ""),
            enum_param(
                "granularity",
                "分桶粒度",
                "year",
                [
                    ("year", "按年"),
                    ("5_year", "五年"),
                    ("decade", "十年"),
                ],
                "",
            ),
        ],
        "runtime": runtime(
            "analysis",
            "analysis.bucket_by_time",
            cacheable=True,
            previewable=True,
            output_node=False,
            parallel_safe=True,
        ),
    }
    return node_definition_from_base(base, runtime_profile, None)


def compile_node(context: Any, node: dict[str, Any]) -> None:
    analysis_passthrough_compiler(context, node)


def _bucket_label(year: int, granularity: str) -> str:
    if granularity == "5_year":
        bucket_start = year - ((year - 1) % 5)
        return f"{bucket_start}-{bucket_start + 4}"
    if granularity == "decade":
        bucket_start = year - (year % 10)
        return f"{bucket_start}s"
    return str(year)


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    corpus = _clone_corpus_rows(_scoped_corpus_from_inputs(context, inputs))
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    field = str(config.get("field") or "year")
    granularity = str(config.get("granularity") or "year")
    _report_node_progress(context, node, 0.2, f"时间分桶：读取 {len(corpus)} 篇文档")
    assignments: list[dict[str, Any]] = []
    total = len(corpus)
    for index, item in enumerate(corpus, start=1):
        value = _document_field_value(item, field)
        try:
            year = int(value)
        except (TypeError, ValueError):
            _report_corpus_progress(context, node, index, total, "时间分桶")
            continue
        assignments.append(
            {
                "doc_id": item.get("doc_id"),
                "title": item.get("title"),
                "year": year,
                "time_bucket": _bucket_label(year, granularity),
            }
        )
        _report_corpus_progress(context, node, index, total, "时间分桶")
    _report_node_progress(context, node, 0.92, f"时间分桶：生成 {len(assignments)} 条分桶")
    return {"time_bucket_table": assignments}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
