from __future__ import annotations

from app.public_sample_data_builder import (
    normalize_wikimedia_page,
    normalize_wikimedia_dump_page,
    parse_un_tei_document,
    reconstruct_openalex_abstract,
    strip_wikimedia_markup,
)


def test_reconstruct_openalex_abstract_preserves_word_order():
    abstract = reconstruct_openalex_abstract(
        {
            "analysis": [2],
            "TextFlow": [0],
            "supports": [1],
            "workflows": [3],
        }
    )
    assert abstract == "TextFlow supports analysis workflows"


def test_normalize_wikimedia_page_builds_real_public_row():
    row = normalize_wikimedia_page(
        "wikimedia_enwiki",
        {
            "pageid": 42,
            "title": "Natural language processing",
            "extract": (
                "Natural language processing is a subfield of computer science and linguistics focused on computational "
                "processing of human language. It includes rule-based systems, statistical learning, representation "
                "learning, and practical applications such as search, tagging, extraction, translation, and dialogue."
            ),
            "touched": "2026-04-01T00:00:00Z",
            "canonicalurl": "https://en.wikipedia.org/wiki/Natural_language_processing",
        },
    )
    assert row is not None
    assert row["language"] == "en"
    assert row["title"] == "Natural language processing"
    assert row["extra_metadata"]["source_dataset_id"] == "wikimedia_enwiki"
    assert row["extra_metadata"]["source_record_id"] == "42"


def test_parse_un_tei_document_extracts_title_symbol_and_body():
    parsed = parse_un_tei_document(
        """<?xml version="1.0" encoding="utf-8"?>
<TEI.2>
  <teiHeader>
    <fileDesc>
      <titleStmt>
        <title>United Nations document title</title>
      </titleStmt>
      <publicationStmt>
        <publisher>United Nations DGACM</publisher>
        <date>20020801</date>
        <idno type="symbol">UNCTAD/ITCD/TSB/MISC.72</idno>
      </publicationStmt>
    </fileDesc>
  </teiHeader>
  <text>
    <body>
      <p id="1"><s id="1:1" lang="en">This is the first real public sentence.</s></p>
      <p id="2"><s id="2:1" lang="en">This is the second real public sentence with enough length to keep the document meaningful for cache building.</s></p>
      <p id="3"><s id="3:1" lang="en">This is the third real public sentence and it helps keep the TEI document above the minimum text threshold used by the builder.</s></p>
    </body>
  </text>
</TEI.2>"""
    )
    assert parsed is not None
    assert parsed["title"] == "United Nations document title"
    assert parsed["year"] == 2002
    assert parsed["source_record_id"] == "UNCTAD/ITCD/TSB/MISC.72"
    assert "third real public sentence" in parsed["raw_text"]


def test_strip_wikimedia_markup_keeps_readable_text():
    text = strip_wikimedia_markup(
        "'''Natural language processing''' uses [[machine learning|ML]] and <ref>citation</ref> [https://example.com links]."
    )
    assert "Natural language processing" in text
    assert "ML" in text
    assert "citation" not in text
    assert "https://example.com" not in text


def test_normalize_wikimedia_dump_page_builds_real_public_row():
    row = normalize_wikimedia_dump_page(
        "wikimedia_zhwiki",
        {
            "pageid": "123",
            "title": "自然语言处理",
            "timestamp": "2026-04-01T00:00:00Z",
            "raw_text": (
                "'''自然语言处理'''是[[计算机科学]]的重要分支，研究人类语言的自动处理与分析。"
                "它涵盖文本分类、信息抽取、机器翻译、问答系统和对话系统，"
                "并结合统计学习、规则方法与神经网络模型来处理真实语料。"
                "现代自然语言处理还涉及词向量表示、预训练语言模型、长文本理解、知识增强和多语言迁移，"
                "因此常被用于搜索、推荐、舆情分析、学术挖掘与企业文档处理。"
                "在实际系统中，研究者还会结合分词、词性标注、句法分析、实体识别、关系抽取、"
                "情感分析、摘要生成与问答评测等任务，持续验证模型在不同领域和不同语料上的表现。"
                "这些方法也推动了教育、医疗、政务与科研知识服务的发展。"
            ),
        },
    )
    assert row is not None
    assert row["language"] == "zh"
    assert row["extra_metadata"]["source_dataset_id"] == "wikimedia_zhwiki"
    assert row["extra_metadata"]["source_record_id"] == "123"
