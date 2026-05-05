from __future__ import annotations

from pathlib import Path

from app.sample_dataset_cache import read_normalized_sample_cache, write_normalized_sample_cache
from app.sample_dataset_sources import normalize_public_sample_row

TEST_SAMPLE_ROW_LIMIT = 120
TEST_PUBLIC_SAMPLE_CACHE_ROW_COUNT = 240


def bundled_public_sample_cache_root() -> Path:
    return Path(__file__).resolve().parents[1] / "app" / "public_sample_cache"


def placeholder_row(dataset_id: str, language: str, idx: int) -> dict[str, object]:
    source_url_map = {
        "un_parallel_en_zh": "https://www.un.org/dgacm/en/node/5471",
        "wikimedia_enwiki": "https://dumps.wikimedia.org/enwiki/latest/",
        "wikimedia_zhwiki": "https://dumps.wikimedia.org/zhwiki/latest/",
        "openalex_works": "https://api.openalex.org/works",
    }
    category = "policy" if idx % 2 == 0 else "technology"
    institution = (
        ["OpenAI Research", "Example Institute", "Policy Lab"][idx % 3]
        if language == "en"
        else ["清华大学", "复旦大学", "政策研究院"][idx % 3]
    )
    raw_text = (
        f"Public {dataset_id} document {idx} discusses {category} strategy, topic clustering, keyword extraction, and language balance."
        if language == "en"
        else f"公开数据 {dataset_id} 文档 {idx} 讨论 {category} 策略、主题聚类、关键词提取和语言平衡。"
    )
    return normalize_public_sample_row(
        {
            "doc_id": f"{dataset_id}-{language}-{idx}",
            "title": f"{dataset_id} {language} title {idx}",
            "raw_text": raw_text,
            "year": 2018 + (idx % 6),
            "source": dataset_id,
            "institution": institution,
            "category_or_tag": category,
            "keyword_field": "topic modeling; keyword extraction" if language == "en" else "主题建模; 关键词提取",
        },
        dataset_id=dataset_id,
        language=language,
        source_record_id=f"{dataset_id}-{language}-{idx}",
        source_url=source_url_map[dataset_id],
        source_profile="literature" if dataset_id == "openalex_works" else "generic",
    )


def copy_bundled_real_cache_rows(
    cache_root: Path,
    dataset_id: str,
    *,
    row_count_by_language: dict[str, int],
) -> None:
    source_rows = read_normalized_sample_cache(bundled_public_sample_cache_root(), dataset_id)
    selected_rows: list[dict[str, object]] = []
    for language, requested_count in row_count_by_language.items():
        language_rows = [
            row
            for row in source_rows
            if str(row.get("language") or "") == language
        ]
        if len(language_rows) < requested_count:
            raise AssertionError(
                f"Bundled real cache does not have enough rows for dataset={dataset_id} language={language}: "
                f"requested={requested_count} available={len(language_rows)}"
            )
        selected_rows.extend(language_rows[:requested_count])
    write_normalized_sample_cache(cache_root, dataset_id, selected_rows)


def populate_public_sample_cache(
    cache_root: Path,
    *,
    row_count: int = TEST_PUBLIC_SAMPLE_CACHE_ROW_COUNT,
) -> Path:
    cache_root.mkdir(parents=True, exist_ok=True)
    copy_bundled_real_cache_rows(
        cache_root,
        "un_parallel_en_zh",
        row_count_by_language={"en": row_count, "zh": row_count},
    )
    copy_bundled_real_cache_rows(
        cache_root,
        "wikimedia_enwiki",
        row_count_by_language={"en": row_count},
    )
    copy_bundled_real_cache_rows(
        cache_root,
        "wikimedia_zhwiki",
        row_count_by_language={"zh": row_count},
    )
    copy_bundled_real_cache_rows(
        cache_root,
        "openalex_works",
        row_count_by_language={"en": row_count, "zh": row_count},
    )
    return cache_root
