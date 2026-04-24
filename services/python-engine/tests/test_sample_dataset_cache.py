from __future__ import annotations

from collections import Counter
from typing import Any

import pytest

from app.sample_dataset_cache import (
    read_language_balanced_sample_rows,
    read_normalized_sample_cache,
    write_normalized_sample_cache,
)
from app.sample_dataset_sources import normalize_public_sample_row


def _row(language: str, idx: int) -> dict[str, Any]:
    return normalize_public_sample_row(
        {
            "doc_id": f"{language}-{idx}",
            "title": f"Real {language} source title {idx}",
            "raw_text": "Real public source text" if language == "en" else "真实公开来源文本",
            "year": 2024,
        },
        dataset_id="wikimedia_enwiki" if language == "en" else "wikimedia_zhwiki",
        language=language,
        source_record_id=f"{language}-{idx}",
        source_url="https://dumps.wikimedia.org/",
    )


def test_cache_loader_reads_real_rows_with_attribution(tmp_path):
    cache_dir = tmp_path / "public-sample-cache"
    write_normalized_sample_cache(
        cache_dir,
        "un_parallel_en_zh",
        [
            normalize_public_sample_row(
                {"doc_id": "un-en-1", "title": "A real UN document", "raw_text": "Real English UN text", "year": 2014},
                dataset_id="un_parallel_en_zh",
                language="en",
                source_record_id="un-en-1",
                source_url="https://www.un.org/dgacm/en/node/5471",
            ),
            normalize_public_sample_row(
                {"doc_id": "un-zh-1", "title": "真实联合国文件", "raw_text": "真实中文联合国文本", "year": 2014},
                dataset_id="un_parallel_en_zh",
                language="zh",
                source_record_id="un-zh-1",
                source_url="https://www.un.org/dgacm/en/node/5471",
            ),
        ],
    )
    rows = read_normalized_sample_cache(cache_dir, "un_parallel_en_zh", limit=2)
    assert {row["language"] for row in rows} == {"en", "zh"}
    assert rows[0]["extra_metadata"]["source_dataset_id"] == "un_parallel_en_zh"


def test_cache_loader_reads_language_balanced_rows(tmp_path):
    cache_dir = tmp_path / "public-sample-cache"
    write_normalized_sample_cache(cache_dir, "wikimedia_enwiki", [_row("en", idx) for idx in range(4)])
    write_normalized_sample_cache(cache_dir, "wikimedia_zhwiki", [_row("zh", idx) for idx in range(4)])
    rows = read_language_balanced_sample_rows(
        cache_dir,
        [
            {"dataset_id": "wikimedia_enwiki", "language": "en", "selector": "sample_01_basic", "ratio": 0.5},
            {"dataset_id": "wikimedia_zhwiki", "language": "zh", "selector": "sample_01_basic", "ratio": 0.5},
        ],
        total_count=6,
    )
    assert Counter(row["language"] for row in rows) == {"en": 3, "zh": 3}


def test_cache_loader_fails_when_real_rows_are_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_normalized_sample_cache(tmp_path, "un_parallel_en_zh", limit=10)


def test_language_balanced_loader_rejects_odd_row_counts(tmp_path):
    with pytest.raises(ValueError):
        read_language_balanced_sample_rows(tmp_path, [], total_count=101)
