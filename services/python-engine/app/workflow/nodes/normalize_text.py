from __future__ import annotations

from typing import Any

from ._common import bool_param, enum_param, port, runtime, runtime_section_compiler, field, graph, slot, ui
from ._support import _clone_corpus_rows, _report_corpus_progress, _scoped_corpus_from_inputs


def _text_ops():
    from ...analysis import text as text_ops_module
    return text_ops_module


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    normalization = (runtime_profile or {}).get("normalization") or {}
    return {
        "type": "normalize_text",
        "title": "统一写法",
        "category": "process",
        "description": "统一时间、数字与正则替换后的文本表达。",
        "inputs": [
            port("corpus_in", "CleanCorpus", "清洗后语料")
        ],
        "outputs": [
            port("normalized_corpus", "NormalizedCorpus", "标准化语料")
        ],
        "params": [
            bool_param("convert_traditional_to_simplified", "繁转简", bool(normalization.get("convert_traditional_to_simplified", False))),
            bool_param("normalize_numbers", "数字归一", bool(normalization.get("normalize_numbers", False))),
            bool_param("normalize_time_expr", "时间表达归一", bool(normalization.get("normalize_time_expr", False))),
            bool_param("apply_regex_rules", "应用 Regex 规则", bool(normalization.get("apply_regex_rules", True))),
            enum_param("regex_rule_priority", "Regex 优先策略", normalization.get("regex_rule_priority", "rule_order"), [
                ("rule_order", "按规则顺序"),
                ("first_match", "命中首条后停止"),
            ]),
        ],
        "runtime": runtime(
            "normalization",
            "workflow.normalize_text",
            cacheable=True,
            previewable=True,
        ),
        "graph": graph((330, 240), (1920, 480), toolbox_order=200),
        "ui": ui(
            [
                field("switch", "convert_traditional_to_simplified", "繁转简"),
                field("switch", "normalize_numbers", "数字归一"),
                field("switch", "normalize_time_expr", "时间表达归一"),
                field("switch", "apply_regex_rules", "应用 Regex 规则"),
                field("select", "regex_rule_priority", "Regex 优先策略"),
            ],
        ),
    }


_compile_runtime_section = runtime_section_compiler("normalization", "normalization")


def compile_node(context: Any, node: dict[str, Any]) -> None:
    _compile_runtime_section(context, node)


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    text_ops = _text_ops()
    corpus = _clone_corpus_rows(_scoped_corpus_from_inputs(context, inputs))
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    total = len(corpus)
    for index, item in enumerate(corpus, start=1):
        normalized, audit_rows = text_ops.apply_normalization(
            str(item.get("clean_text") or ""),
            context.manifest["dictionary_set"],
            params,
            collect_audit=bool(getattr(context, "audit_enabled", True)),
        )
        item["normalized_text"] = normalized
        for audit in audit_rows:
            audit["doc_id"] = item["doc_id"]
        context.add_audits(audit_rows)
        _report_corpus_progress(context, node, index, total, "统一写法")
    context.shared["normalized_corpus"] = corpus
    return {"normalized_corpus": corpus}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
