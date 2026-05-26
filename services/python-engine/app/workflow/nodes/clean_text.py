from __future__ import annotations

from typing import Any

from ._common import bool_param, port, runtime, runtime_section_compiler, field, graph, slot, ui
from ._support import _clone_corpus_rows, _report_corpus_progress, _scoped_corpus_from_inputs


def _text_ops():
    from ...analysis import text as text_ops_module
    return text_ops_module


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    cleaning = (runtime_profile or {}).get("cleaning") or {}
    return {
        "type": "clean_text",
        "title": "基础清洗",
        "category": "process",
        "description": "去噪、清理空白并处理 HTML 与 URL。",
        "inputs": [
            port("corpus_in", "CorpusTable", "语料输入")
        ],
        "outputs": [
            port("clean_corpus", "CleanCorpus", "清洗后语料")
        ],
        "params": [
            bool_param("strip_html", "去 HTML", bool(cleaning.get("strip_html", True))),
            bool_param("strip_urls", "去 URL", bool(cleaning.get("strip_urls", True))),
            bool_param("strip_email", "去邮箱", bool(cleaning.get("strip_email", False))),
            bool_param("strip_phone", "去手机号", bool(cleaning.get("strip_phone", False))),
            bool_param("normalize_whitespace", "统一空白", bool(cleaning.get("normalize_whitespace", True))),
            bool_param("normalize_punctuation", "统一标点", bool(cleaning.get("normalize_punctuation", True))),
            bool_param("full_half_width_normalize", "全半角归一", bool(cleaning.get("full_half_width_normalize", True))),
            bool_param("lowercase_english", "英文小写", bool(cleaning.get("lowercase_english", True))),
            bool_param("remove_emoji", "去表情", bool(cleaning.get("remove_emoji", False))),
            bool_param("remove_special_chars", "去特殊字符", bool(cleaning.get("remove_special_chars", False))),
        ],
        "runtime": runtime(
            "cleaning",
            "workflow.clean_text",
            cacheable=True,
            previewable=True,
        ),
        "graph": graph((320, 230), (1500, 480), toolbox_order=190),
        "ui": ui(
            [
                field("switch", "strip_html", "去 HTML"),
                field("switch", "strip_urls", "去 URL"),
                field("switch", "strip_email", "去邮箱"),
                field("switch", "strip_phone", "去手机号"),
                field("switch", "normalize_whitespace", "统一空白"),
                field("switch", "normalize_punctuation", "统一标点"),
                field("switch", "full_half_width_normalize", "全半角归一"),
                field("switch", "lowercase_english", "英文小写"),
                field("switch", "remove_emoji", "去表情"),
                field("switch", "remove_special_chars", "去特殊字符"),
            ],
        ),
    }


_compile_runtime_section = runtime_section_compiler("cleaning", "cleaning")


def compile_node(context: Any, node: dict[str, Any]) -> None:
    _compile_runtime_section(context, node)


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    text_ops = _text_ops()
    corpus = _clone_corpus_rows(_scoped_corpus_from_inputs(context, inputs))
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    total = len(corpus)
    for index, item in enumerate(corpus, start=1):
        cleaned, flags = text_ops.apply_cleaning(str(item.get("raw_text") or ""), params)
        item["clean_text"] = cleaned
        if flags:
            context.log(node, f"{item['doc_id']} 命中清洗规则：{', '.join(flags)}")
        if not cleaned:
            item["status"] = "warning"
            context.warning(f"{item['doc_id']} 在清洗后为空。", node)
        _report_corpus_progress(context, node, index, total, "基础清洗")
    context.shared["clean_corpus"] = corpus
    return {"clean_corpus": corpus}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
