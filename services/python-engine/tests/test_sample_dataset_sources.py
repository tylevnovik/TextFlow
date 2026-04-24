from __future__ import annotations

import pytest

from app.sample_dataset_sources import (
    PUBLIC_SAMPLE_DATA_SOURCES,
    normalize_public_sample_row,
    source_supports_language,
)


def test_public_source_registry_contains_only_real_public_sources():
    source_ids = {source.source_id for source in PUBLIC_SAMPLE_DATA_SOURCES}
    assert {"un_parallel_en_zh", "wikimedia_enwiki", "wikimedia_zhwiki", "openalex_works"} <= source_ids
    for source in PUBLIC_SAMPLE_DATA_SOURCES:
        assert source.name
        assert source.homepage_url.startswith("https://")
        assert source.license_name
        assert source.public_access_note
        assert source.redistribution_note
        assert set(source.languages) <= {"en", "zh"}


def test_default_sources_can_supply_english_and_chinese_rows():
    assert source_supports_language("un_parallel_en_zh", "en")
    assert source_supports_language("un_parallel_en_zh", "zh")
    assert source_supports_language("wikimedia_enwiki", "en")
    assert source_supports_language("wikimedia_zhwiki", "zh")
    assert source_supports_language("openalex_works", "en")
    assert source_supports_language("openalex_works", "zh")


def test_normalized_public_row_requires_source_attribution():
    row = normalize_public_sample_row(
        {
            "doc_id": "source-1",
            "title": "真实公开来源标题",
            "raw_text": "真实公开来源文本",
            "year": 2024,
        },
        dataset_id="un_parallel_en_zh",
        language="zh",
        source_record_id="source-1",
        source_url="https://www.un.org/dgacm/en/node/5471",
    )
    assert row["language"] == "zh"
    assert row["extra_metadata"]["source_dataset_id"] == "un_parallel_en_zh"
    assert row["extra_metadata"]["source_record_id"] == "source-1"
    assert row["raw_text"] == "真实公开来源文本"


def test_normalization_rejects_missing_text():
    with pytest.raises(ValueError):
        normalize_public_sample_row({"doc_id": "bad"}, dataset_id="un_parallel_en_zh", language="en")


def test_normalization_rejects_unsupported_language():
    with pytest.raises(ValueError):
        normalize_public_sample_row({"doc_id": "bad", "raw_text": "bonjour"}, dataset_id="un_parallel_en_zh", language="fr")
