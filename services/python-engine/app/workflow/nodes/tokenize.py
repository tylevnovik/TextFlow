from __future__ import annotations

from typing import Any

from ._common import bool_param, enum_param, number_param, port, runtime, runtime_section_compiler
from ._support import _clone_corpus_rows, _report_corpus_progress, _scoped_corpus_from_inputs


def _text_ops():
    from ...analysis import text as text_ops_module
    return text_ops_module


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    tokenization = (runtime_profile or {}).get("tokenization") or {}
    return {
        "type": "tokenize",
        "title": "切词",
        "category": "process",
        "description": "执行中英文切词，并尽量保留短语。",
        "inputs": [
            port("corpus_in", "NormalizedCorpus", "标准化语料")
        ],
        "outputs": [
            port("token_corpus", "TokenCorpus", "Token 语料")
        ],
        "params": [
            enum_param("language_mode", "语言模式", tokenization.get("language_mode", "mixed"), [
                ("auto", "自动"),
                ("zh", "中文"),
                ("en", "英文"),
                ("mixed", "中英混合"),
            ]),
            enum_param("tokenizer_backend", "切词引擎", tokenization.get("tokenizer_backend", "default"), [
                ("default", "默认"),
            ]),
            bool_param("use_custom_lexicon", "使用自定义词典", bool(tokenization.get("use_custom_lexicon", True))),
            bool_param("use_phrase_lexicon", "使用短语词典", bool(tokenization.get("use_phrase_lexicon", True))),
            bool_param("preserve_domain_phrases", "保留领域短语", bool(tokenization.get("preserve_domain_phrases", True))),
            bool_param("split_hyphenated_terms", "拆分连字符", bool(tokenization.get("split_hyphenated_terms", True))),
            bool_param("split_slash_terms", "拆分斜杠词", bool(tokenization.get("split_slash_terms", False))),
            bool_param("normalize_camel_case", "拆分 CamelCase", bool(tokenization.get("normalize_camel_case", True))),
            bool_param("keep_original_order", "保留原始顺序", bool(tokenization.get("keep_original_order", True))),
            number_param("min_token_length_before_filter", "切词前最短长度", int(tokenization.get("min_token_length_before_filter", 1))),
            bool_param("enable_ngrams", "生成 n-gram", bool(tokenization.get("enable_ngrams", False))),
            number_param("ngram_min", "最小 n-gram", int(tokenization.get("ngram_min", 2))),
            number_param("ngram_max", "最大 n-gram", int(tokenization.get("ngram_max", 2))),
        ],
        "runtime": runtime(
            "tokenization",
            "workflow.tokenize",
            cacheable=True,
            previewable=True,
        ),
    }


_compile_runtime_section = runtime_section_compiler("tokenization", "tokenization")


def compile_node(context: Any, node: dict[str, Any]) -> None:
    _compile_runtime_section(context, node)


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    text_ops = _text_ops()
    corpus = _clone_corpus_rows(_scoped_corpus_from_inputs(context, inputs))
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    total = len(corpus)
    for index, item in enumerate(corpus, start=1):
        tokens, phrase_hits = text_ops.tokenize_text(
            str(item.get("normalized_text") or item.get("clean_text") or ""),
            context.manifest["dictionary_set"],
            params,
        )
        item["tokens"] = tokens
        item["phrase_hits"] = phrase_hits
        _report_corpus_progress(context, node, index, total, "切词")
    context.shared["token_corpus"] = corpus
    return {"token_corpus": corpus}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
