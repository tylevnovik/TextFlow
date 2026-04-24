from __future__ import annotations

import gzip
import json
import math
import os
from itertools import zip_longest
from pathlib import Path
from typing import Any, Iterable

from .sample_dataset_sources import PUBLIC_SAMPLE_DATA_SOURCE_BY_ID

CACHE_ROOT_ENV_VAR = "TEXTFLOW_PUBLIC_SAMPLE_CACHE_ROOT"
DEFAULT_CACHE_DIRNAME = "public_sample_cache"


def sample_data_cache_root() -> Path:
    configured_root = os.getenv(CACHE_ROOT_ENV_VAR)
    if configured_root:
        root = Path(configured_root)
    else:
        root = Path(__file__).resolve().parent / DEFAULT_CACHE_DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def _validate_dataset_id(dataset_id: str) -> None:
    if dataset_id not in PUBLIC_SAMPLE_DATA_SOURCE_BY_ID:
        raise ValueError(f"Unknown public sample dataset: {dataset_id}")


def normalized_cache_path(cache_root: Path, dataset_id: str) -> Path:
    _validate_dataset_id(dataset_id)
    return cache_root / f"{dataset_id}.jsonl.gz"


def write_normalized_sample_cache(cache_root: Path, dataset_id: str, rows: list[dict[str, Any]]) -> Path:
    cache_root.mkdir(parents=True, exist_ok=True)
    cache_path = normalized_cache_path(cache_root, dataset_id)
    with gzip.open(cache_path, "wt", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
    return cache_path


def _row_matches_selector(row: dict[str, Any], selector: str | None) -> bool:
    if not selector:
        return True
    extra_metadata = row.get("extra_metadata") if isinstance(row.get("extra_metadata"), dict) else {}
    selectors = extra_metadata.get("selectors")
    if isinstance(selectors, list) and selectors:
        return selector in {str(item) for item in selectors}
    single_selector = extra_metadata.get("selector")
    if isinstance(single_selector, str) and single_selector:
        return single_selector == selector
    return True


def read_normalized_sample_cache(
    cache_root: Path,
    dataset_id: str,
    *,
    limit: int | None = None,
    selector: str | None = None,
) -> list[dict[str, Any]]:
    cache_path = normalized_cache_path(cache_root, dataset_id)
    if not cache_path.exists():
        raise FileNotFoundError(f"Missing normalized public sample cache: {cache_path}")

    rows: list[dict[str, Any]] = []
    with gzip.open(cache_path, "rt", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            if not _row_matches_selector(payload, selector):
                continue
            rows.append(payload)
            if limit is not None and len(rows) >= limit:
                break
    return rows


def _allocate_counts(sources: list[dict[str, Any]], target_total: int) -> list[int]:
    if target_total == 0:
        return [0 for _ in sources]

    ratios = [max(float(source.get("ratio", 0.0) or 0.0), 0.0) for source in sources]
    ratio_total = sum(ratios)
    if ratio_total <= 0:
        ratios = [1.0 for _ in sources]
        ratio_total = float(len(sources))

    exact_counts = [(target_total * ratio) / ratio_total for ratio in ratios]
    counts = [math.floor(value) for value in exact_counts]
    remainder = target_total - sum(counts)
    ranked = sorted(
        enumerate(exact_counts),
        key=lambda item: (item[1] - math.floor(item[1]), -item[0]),
        reverse=True,
    )
    for index, _value in ranked[:remainder]:
        counts[index] += 1
    return counts


def _interleave_language_rows(rows_by_language: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    combined: list[dict[str, Any]] = []
    languages = ["en", "zh"]
    for row_group in zip_longest(*(rows_by_language.get(language, []) for language in languages), fillvalue=None):
        for row in row_group:
            if row is not None:
                combined.append(row)
    return combined


def read_language_balanced_sample_rows(
    cache_root: Path,
    sources: list[dict[str, Any]],
    *,
    total_count: int,
) -> list[dict[str, Any]]:
    if total_count < 2 or total_count % 2:
        raise ValueError("Language-balanced public samples require an even total_count of at least 2")

    grouped_sources: dict[str, list[dict[str, Any]]] = {}
    for source in sources:
        language = str(source.get("language") or "")
        grouped_sources.setdefault(language, []).append(source)

    if set(grouped_sources) != {"en", "zh"}:
        raise ValueError("Language-balanced public samples require exactly en and zh source groups")

    per_language_target = total_count // 2
    rows_by_language: dict[str, list[dict[str, Any]]] = {}
    for language in ("en", "zh"):
        language_sources = grouped_sources[language]
        allocations = _allocate_counts(language_sources, per_language_target)
        selected_rows: list[dict[str, Any]] = []
        for source, requested_count in zip(language_sources, allocations, strict=True):
            if requested_count == 0:
                continue
            dataset_id = str(source.get("dataset_id") or "")
            selector = str(source.get("selector") or "") or None
            rows = read_normalized_sample_cache(cache_root, dataset_id, selector=selector)
            if len(rows) < requested_count:
                raise ValueError(
                    f"Not enough real public sample rows for dataset={dataset_id} language={language}: "
                    f"requested={requested_count} available={len(rows)}"
                )
            selected_rows.extend(rows[:requested_count])
        if len(selected_rows) != per_language_target:
            raise ValueError(
                f"Language group {language} did not reach the required balanced quota: "
                f"requested={per_language_target} actual={len(selected_rows)}"
            )
        rows_by_language[language] = selected_rows

    return _interleave_language_rows(rows_by_language)


def ensure_public_sample_cache_available(required_dataset_ids: Iterable[str]) -> None:
    cache_root = sample_data_cache_root()
    missing = [
        dataset_id
        for dataset_id in required_dataset_ids
        if not normalized_cache_path(cache_root, dataset_id).exists()
    ]
    if missing:
        joined = ", ".join(sorted(missing))
        raise FileNotFoundError(
            f"Missing normalized public sample cache datasets: {joined}. "
            f"Expected cache root: {cache_root}"
        )
