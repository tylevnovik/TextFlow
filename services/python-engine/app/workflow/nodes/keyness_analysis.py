from __future__ import annotations

import math
from typing import Any

from ._common import analysis_passthrough_compiler, number_param, port, runtime, string_param, field, graph, slot, ui
from ._support import (
    _clone_corpus_rows,
    _group_term_statistics,
    _report_node_progress,
    _scoped_corpus_from_inputs,
)


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "type": "keyness_analysis",
        "title": "关键性分析",
        "category": "analysis",
        "description": "计算目标分组相对基准分组的 LLR 和相对比率，识别区分性词项。",
        "inputs": [
            port("token_corpus_in", "FilteredTokenCorpus", "分析词项")
        ],
        "outputs": [
            port("keyness_table", "AnyTable", "关键性结果表", result_bundle_key="keyness_table")
        ],
        "params": [
            string_param("group_field", "分组字段", "institution"),
            string_param("baseline_group", "基准分组", "OpenAI"),
            string_param("comparison_group", "目标分组", "Anthropic"),
            number_param("min_frequency", "最小词频", 2),
        ],
        "runtime": runtime(
            "analysis",
            "analysis.keyness",
            cacheable=True,
            previewable=True,
            parallel_safe=True,
        ),
        "graph": graph((360, 260), (4080, 1640), toolbox_order=400),
        "ui": ui(
            [
                field("text", "group_field", "分组字段"),
                field("text", "baseline_group", "基准分组"),
                field("text", "comparison_group", "目标分组"),
                field("number", "min_frequency", "最小词频", step=1),
            ],
        ),
    }


def compile_node(context: Any, node: dict[str, Any]) -> None:
    analysis_passthrough_compiler(context, node)


def _xlogx(value: float) -> float:
    return 0.0 if value <= 0 else value * math.log(value)


def _log_likelihood_ratio(comparison_term_count: int, comparison_total: int, baseline_term_count: int, baseline_total: int) -> float:
    k11 = float(comparison_term_count)
    k12 = float(baseline_term_count)
    k21 = float(max(comparison_total - comparison_term_count, 0))
    k22 = float(max(baseline_total - baseline_term_count, 0))
    row_sum_1 = k11 + k12
    row_sum_2 = k21 + k22
    total = float(comparison_total + baseline_total)
    return max(
        0.0,
        2.0
        * (
            _xlogx(k11)
            + _xlogx(k12)
            + _xlogx(k21)
            + _xlogx(k22)
            + _xlogx(total)
            - _xlogx(float(comparison_total))
            - _xlogx(float(baseline_total))
            - _xlogx(row_sum_1)
            - _xlogx(row_sum_2)
        ),
    )


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    corpus = _clone_corpus_rows(_scoped_corpus_from_inputs(context, inputs))
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    group_field = str(config.get("group_field") or "institution").strip()
    baseline_group = str(config.get("baseline_group") or "").strip()
    comparison_group = str(config.get("comparison_group") or "").strip()
    min_frequency = int(config.get("min_frequency", 2) or 2)
    _report_node_progress(context, node, 0.18, "关键性分析：统计分组词频")
    group_totals, term_counts, doc_sets, terms = _group_term_statistics(corpus, group_field)
    comparison_total = group_totals.get(comparison_group, 0)
    baseline_total = group_totals.get(baseline_group, 0)
    if not comparison_total or not baseline_total:
        _report_node_progress(context, node, 0.92, "关键性分析：缺少基准组或比较组")
        return {"keyness_table": []}
    _report_node_progress(context, node, 0.45, f"关键性分析：准备比较 {len(terms)} 个词项")
    rows: list[dict[str, Any]] = []
    sorted_terms = sorted(terms)
    for term_index, term in enumerate(sorted_terms, start=1):
        comparison_term_count = term_counts.get((comparison_group, term), 0)
        baseline_term_count = term_counts.get((baseline_group, term), 0)
        if comparison_term_count + baseline_term_count < min_frequency:
            continue
        comparison_ratio = comparison_term_count / comparison_total if comparison_total else 0.0
        baseline_ratio = baseline_term_count / baseline_total if baseline_total else 0.0
        rows.append(
            {
                "group_field": group_field,
                "comparison_group": comparison_group,
                "baseline_group": baseline_group,
                "term": term,
                "comparison_term_count": comparison_term_count,
                "baseline_term_count": baseline_term_count,
                "comparison_document_count": len(doc_sets.get((comparison_group, term), set())),
                "baseline_document_count": len(doc_sets.get((baseline_group, term), set())),
                "comparison_normalized_frequency": round(comparison_ratio, 6),
                "baseline_normalized_frequency": round(baseline_ratio, 6),
                "relative_ratio": round((comparison_ratio + 1e-9) / (baseline_ratio + 1e-9), 6),
                "llr": round(
                    _log_likelihood_ratio(
                        comparison_term_count,
                        comparison_total,
                        baseline_term_count,
                        baseline_total,
                    ),
                    6,
                ),
            }
        )
        if term_index == len(sorted_terms) or term_index % 250 == 0:
            _report_node_progress(
                context,
                node,
                0.45 + 0.42 * term_index / max(len(sorted_terms), 1),
                f"关键性分析：完成 {term_index}/{len(sorted_terms)} 个词项",
            )
    rows.sort(key=lambda item: (-float(item["llr"]), -float(item["relative_ratio"]), str(item["term"])))
    _report_node_progress(context, node, 0.92, f"关键性分析：生成 {len(rows)} 行")
    return {"keyness_table": rows}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
