from __future__ import annotations

from typing import Any

from ._common import bool_param, enum_param, port, runtime, runtime_section_compiler, field, graph, slot, ui
from ._support import (
    _active_dictionary_set,
    _clone_corpus_rows,
    _report_corpus_progress,
    _scoped_corpus_from_inputs,
    _shared_get,
    _shared_set,
)


def _text_ops():
    from ...analysis import text as text_ops_module
    return text_ops_module


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    dictionary = (runtime_profile or {}).get("dictionary") or {}
    return {
        "type": "apply_dictionary_rules",
        "title": "套用词表",
        "category": "process",
        "description": "按停用词、同义词、标准词和排除词重写 token。",
        "inputs": [
            port("token_corpus_in", "TokenCorpus", "Token 输入"),
            port("dictionary_set_in", "DictionarySet", "词表输入"),
        ],
        "outputs": [
            port("token_corpus", "TokenCorpus", "规则处理后 Token"),
            port("audit_table", "AuditTable", "审计表", result_bundle_key="audit_table", include_in_html_audit=True),
        ],
        "params": [
            bool_param("apply_standard_terms", "应用标准词", bool(dictionary.get("apply_standard_terms", True))),
            bool_param("apply_synonym_map", "应用同义词", bool(dictionary.get("apply_synonym_map", True))),
            bool_param("apply_near_synonym_map", "应用近义词", bool(dictionary.get("apply_near_synonym_map", True))),
            bool_param("apply_stopwords", "应用停用词", bool(dictionary.get("apply_stopwords", True))),
            bool_param("apply_exclusion_terms", "应用排除词", bool(dictionary.get("apply_exclusion_terms", True))),
            enum_param("conflict_resolution", "冲突处理", dictionary.get("conflict_resolution", "priority"), [
                ("priority", "按词表优先级"),
                ("first_match", "命中首条后停止"),
            ]),
        ],
        "runtime": runtime(
            "dictionary_application",
            "workflow.apply_dictionary_rules",
            cacheable=True,
            previewable=True,
        ),
        "graph": graph((340, 240), (2760, 480), toolbox_order=230),
        "ui": ui(
            [
                field("switch", "apply_standard_terms", "应用标准词"),
                field("switch", "apply_synonym_map", "应用同义词"),
                field("switch", "apply_near_synonym_map", "应用近义词"),
                field("switch", "apply_stopwords", "应用停用词"),
                field("switch", "apply_exclusion_terms", "应用排除词"),
                field("select", "conflict_resolution", "冲突处理"),
            ],
        ),
    }


_compile_runtime_section = runtime_section_compiler("dictionary", "dictionary_application")


def compile_node(context: Any, node: dict[str, Any]) -> None:
    _compile_runtime_section(context, node)


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    text_ops = _text_ops()
    corpus = _clone_corpus_rows(_scoped_corpus_from_inputs(context, inputs))
    dictionary_set = _active_dictionary_set(context, inputs)
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    node_audits: list[dict[str, Any]] = []
    runtime_state = _shared_get(context, "dictionary_runtime_state")
    if runtime_state is None or _shared_get(context, "dictionary_runtime_state_source_id") != id(dictionary_set):
        runtime_state = text_ops.build_dictionary_runtime_state(dictionary_set)
        _shared_set(context, "dictionary_runtime_state", runtime_state)
        _shared_set(context, "dictionary_runtime_state_source_id", id(dictionary_set))
    total = len(corpus)
    for index, item in enumerate(corpus, start=1):
        mapped_tokens, audits = text_ops.apply_dictionary(
            item["doc_id"],
            list(item.get("tokens") or []),
            dictionary_set,
            params,
            runtime_state=runtime_state,
            collect_audit=bool(getattr(context, "audit_enabled", True)),
        )
        item["tokens"] = mapped_tokens
        node_audits.extend(audits)
        _report_corpus_progress(context, node, index, total, "套用词表")
    context.add_audits(node_audits)
    context.shared["dictionary_corpus"] = corpus
    return {"token_corpus": corpus, "audit_table": node_audits}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
