from __future__ import annotations

from typing import Any

from ._common import analysis_passthrough_compiler, number_param, port, runtime, string_param, field, graph, slot, ui
from ._support import (
    _clone_corpus_rows,
    _comparison_groups,
    _group_term_statistics,
    _report_node_progress,
    _scoped_corpus_from_inputs,
)


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "type": "group_compare",
        "title": "分组比较",
        "category": "analysis",
        "description": "按指定分组字段比较词项在不同群组中的频次、文档覆盖和归一化占比。",
        "inputs": [
            port("token_corpus_in", "FilteredTokenCorpus", "分析词项")
        ],
        "outputs": [
            port("group_metric_table", "AnyTable", "分组比较表", result_bundle_key="group_compare_table")
        ],
        "params": [
            string_param("group_field", "分组字段", "institution"),
            string_param("baseline_group", "基准分组", "OpenAI"),
            string_param("comparison_groups_text", "对比分组", "Anthropic,Google"),
            number_param("min_frequency", "最小词频", 1),
        ],
        "runtime": runtime(
            "analysis",
            "analysis.group_compare",
            cacheable=True,
            previewable=True,
            parallel_safe=True,
        ),
        "graph": graph((360, 280), (3660, 1640), toolbox_order=340),
        "ui": ui(
            [
                field("text", "group_field", "分组字段"),
                field("text", "baseline_group", "基准分组"),
                field("textarea", "comparison_groups_text", "对比分组"),
                field("number", "min_frequency", "最小词频", step=1),
            ],
        ),
    }


def compile_node(context: Any, node: dict[str, Any]) -> None:
    analysis_passthrough_compiler(context, node)


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    corpus = _clone_corpus_rows(_scoped_corpus_from_inputs(context, inputs))
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    group_field = str(config.get("group_field") or "institution").strip()
    baseline_group = str(config.get("baseline_group") or "").strip()
    min_frequency = int(config.get("min_frequency", 1) or 1)
    _report_node_progress(context, node, 0.15, "分组比较：统计分组词频")
    group_totals, term_counts, doc_sets, terms = _group_term_statistics(corpus, group_field)
    if not group_totals:
        _report_node_progress(context, node, 0.92, "分组比较：无可比较分组")
        return {"group_metric_table": []}
    _report_node_progress(context, node, 0.45, f"分组比较：识别 {len(group_totals)} 个分组")
    comparison_groups = _comparison_groups(config, baseline_group, set(group_totals))
    selected_groups = [group for group in [baseline_group, *comparison_groups] if group and group in group_totals]
    if not selected_groups:
        selected_groups = sorted(group_totals)
    rows: list[dict[str, Any]] = []
    total_groups = len(selected_groups)
    for group_index, group_value in enumerate(selected_groups, start=1):
        total_terms = group_totals.get(group_value, 0)
        if not total_terms:
            continue
        for term in sorted(terms):
            term_count = term_counts.get((group_value, term), 0)
            baseline_term_count = term_counts.get((baseline_group, term), 0)
            if term_count + baseline_term_count < min_frequency:
                continue
            baseline_total = group_totals.get(baseline_group, 0)
            normalized_frequency = term_count / total_terms if total_terms else 0.0
            baseline_normalized_frequency = baseline_term_count / baseline_total if baseline_total else 0.0
            rows.append(
                {
                    "group_field": group_field,
                    "group_value": group_value,
                    "baseline_group": baseline_group,
                    "term": term,
                    "term_count": term_count,
                    "document_count": len(doc_sets.get((group_value, term), set())),
                    "total_terms": total_terms,
                    "normalized_frequency": round(normalized_frequency, 6),
                    "baseline_term_count": baseline_term_count,
                    "baseline_document_count": len(doc_sets.get((baseline_group, term), set())),
                    "baseline_total_terms": baseline_total,
                    "baseline_normalized_frequency": round(baseline_normalized_frequency, 6),
                    "ratio_vs_baseline": round((normalized_frequency + 1e-9) / (baseline_normalized_frequency + 1e-9), 6),
                }
            )
        _report_node_progress(
            context,
            node,
            0.45 + 0.42 * group_index / max(total_groups, 1),
            f"分组比较：完成 {group_index}/{total_groups} 个分组",
        )
    rows.sort(key=lambda item: (str(item["group_value"]), -int(item["term_count"]), str(item["term"])))
    _report_node_progress(context, node, 0.92, f"分组比较：生成 {len(rows)} 行")
    return {"group_metric_table": rows}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
