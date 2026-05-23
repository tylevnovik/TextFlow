from __future__ import annotations

import itertools
import math
import os
import re
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from multiprocessing import get_context
from typing import Any, Callable

import numpy as np
import yake
from sklearn.feature_extraction.text import TfidfVectorizer

from .core import CJK_PATTERN, build_analysis_text, normalize_keyword_candidate

YAKE_PARALLEL_MIN_DOCS = 80
YAKE_PARALLEL_MIN_TOKENS = 20000
YAKE_MAX_WORKERS = 8
YAKE_TARGET_DOCS_PER_WORKER = 200
YAKE_TARGET_CHUNKS_PER_WORKER = 3

_YAKE_EXTRACTOR_CACHE: dict[tuple[str, int], Any] = {}


@dataclass
class TfidfAnalysisBundle:
    doc_ids: list[str]
    terms: list[str]
    matrix: Any | None

    @property
    def empty(self) -> bool:
        return self.matrix is None or not self.doc_ids or not self.terms


def yake_language(text: str) -> str:
    cjk_chars = sum(len(match.group(0)) for match in CJK_PATTERN.finditer(text))
    latin_chars = len(re.findall(r"[A-Za-z]", text))
    return "zh" if cjk_chars >= latin_chars else "en"


def fallback_keywords(tokens: list[str], top_k: int) -> list[tuple[str, float]]:
    rows: list[tuple[str, float]] = []
    for term, count in Counter(tokens).most_common(top_k):
        normalized = normalize_keyword_candidate(term)
        if not normalized:
            continue
        rows.append((normalized, float(count)))
    return rows


def _append_ranked_keyword_rows(
    doc_keyword_rows: list[dict[str, Any]],
    project_scores: dict[str, dict[str, float | str | int]],
    *,
    doc_id: str,
    ranked: list[tuple[str, float]],
    top_k_doc: int,
) -> None:
    doc_seen: set[str] = set()
    for rank, (keyword, score) in enumerate(ranked[:top_k_doc], start=1):
        doc_keyword_rows.append(
            {
                "scope": "doc",
                "doc_id": doc_id,
                "keyword": keyword,
                "score": float(score),
                "rank": rank,
            }
        )
        payload = project_scores.setdefault(
            keyword,
            {"keyword": keyword, "score_total": 0.0, "doc_count": 0, "best_score": 0.0},
        )
        payload["score_total"] = float(payload["score_total"]) + float(score)
        payload["best_score"] = max(float(payload["best_score"]), float(score))
        if keyword not in doc_seen:
            payload["doc_count"] = int(payload["doc_count"]) + 1
            doc_seen.add(keyword)


def _project_keyword_rows(
    project_scores: dict[str, dict[str, float | str | int]],
    top_k_project: int,
) -> list[dict[str, Any]]:
    project_keyword_rows: list[dict[str, Any]] = []
    ranked_project_keywords = sorted(
        project_scores.values(),
        key=lambda item: (
            (float(item["score_total"]) / max(int(item["doc_count"]), 1)) * (1.0 + math.log(int(item["doc_count"]) + 1)),
            int(item["doc_count"]),
            float(item["best_score"]),
        ),
        reverse=True,
    )
    for rank, item in enumerate(ranked_project_keywords[:top_k_project], start=1):
        mean_score = float(item["score_total"]) / max(int(item["doc_count"]), 1)
        project_keyword_rows.append(
            {
                "scope": "project",
                "keyword": str(item["keyword"]),
                "score": round(mean_score * (1.0 + math.log(int(item["doc_count"]) + 1)), 6),
                "rank": rank,
            }
        )
    return project_keyword_rows


def _yake_extractor(language: str, top_k_doc: int) -> Any:
    top_limit = max(top_k_doc * 3, top_k_doc)
    cache_key = (language, top_limit)
    extractor = _YAKE_EXTRACTOR_CACHE.get(cache_key)
    if extractor is None:
        extractor = yake.KeywordExtractor(
            lan=language,
            n=3,
            dedupLim=0.85,
            dedupFunc="seqm",
            windowsSize=2,
            top=top_limit,
        )
        _YAKE_EXTRACTOR_CACHE[cache_key] = extractor
    return extractor


def _ranked_yake_keywords(item: dict[str, Any], top_k_doc: int) -> list[tuple[str, float]]:
    text = build_analysis_text(item)
    ranked: list[tuple[str, float]] = []
    if text:
        extractor = _yake_extractor(yake_language(text), top_k_doc)
        seen: set[str] = set()
        for candidate, raw_score in extractor.extract_keywords(text):
            normalized = normalize_keyword_candidate(candidate)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            ranked.append((normalized, round(1.0 / (1.0 + max(float(raw_score), 0.0)), 6)))
            if len(ranked) >= top_k_doc:
                break

    if ranked:
        return ranked
    return fallback_keywords(item.get("filtered_tokens", []), top_k_doc)


def _keyword_parallel_payload(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": str(item.get("title") or ""),
        "filtered_tokens": list(item.get("filtered_tokens") or []),
        "keyword_field": str(item.get("keyword_field") or ""),
    }


def _ranked_yake_keywords_chunk(items: list[dict[str, Any]], top_k_doc: int) -> list[list[tuple[str, float]]]:
    return [_ranked_yake_keywords(item, top_k_doc) for item in items]


def _chunked_items(items: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def parallel_yake_worker_count(corpus: list[dict[str, Any]]) -> int:
    if os.environ.get("TEXTFLOW_DISABLE_PARALLEL_YAKE") == "1":
        return 1

    forced = os.environ.get("TEXTFLOW_YAKE_WORKERS")
    if forced:
        try:
            requested = int(forced)
        except ValueError:
            requested = 1
        return max(1, min(requested, len(corpus), YAKE_MAX_WORKERS, os.cpu_count() or 1))

    if len(corpus) < YAKE_PARALLEL_MIN_DOCS:
        return 1

    token_count = sum(len(item.get("filtered_tokens") or []) for item in corpus)
    if token_count < YAKE_PARALLEL_MIN_TOKENS:
        return 1

    cpu_total = os.cpu_count() or 1
    cpu_budget = max(1, min(YAKE_MAX_WORKERS, cpu_total - 1 if cpu_total > 2 else cpu_total))
    worker_target = max(1, math.ceil(len(corpus) / YAKE_TARGET_DOCS_PER_WORKER))
    return max(1, min(cpu_budget, worker_target, len(corpus)))


def _yake_keyword_rows_serial(
    corpus: list[dict[str, Any]],
    top_k_doc: int,
    top_k_project: int,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[dict[str, Any]]:
    doc_keyword_rows: list[dict[str, Any]] = []
    project_scores: dict[str, dict[str, float | str | int]] = {}
    total = len(corpus)

    for index, item in enumerate(corpus, start=1):
        ranked = _ranked_yake_keywords(item, top_k_doc)
        _append_ranked_keyword_rows(
            doc_keyword_rows,
            project_scores,
            doc_id=str(item["doc_id"]),
            ranked=ranked,
            top_k_doc=top_k_doc,
        )
        if progress_callback is not None and (index == 1 or index == total or index % 100 == 0):
            progress_callback(index, total)

    return [*doc_keyword_rows, *_project_keyword_rows(project_scores, top_k_project)]


def _yake_keyword_rows_parallel(
    corpus: list[dict[str, Any]],
    top_k_doc: int,
    top_k_project: int,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[dict[str, Any]]:
    workers = parallel_yake_worker_count(corpus)
    if workers <= 1:
        return _yake_keyword_rows_serial(corpus, top_k_doc, top_k_project, progress_callback)

    payloads = [_keyword_parallel_payload(item) for item in corpus]
    chunk_size = max(12, math.ceil(len(payloads) / max(workers * YAKE_TARGET_CHUNKS_PER_WORKER, 1)))
    chunks = _chunked_items(payloads, chunk_size)
    doc_keyword_rows: list[dict[str, Any]] = []
    project_scores: dict[str, dict[str, float | str | int]] = {}
    completed = 0

    try:
        with ProcessPoolExecutor(max_workers=workers, mp_context=get_context("spawn")) as executor:
            results = executor.map(
                _ranked_yake_keywords_chunk,
                chunks,
                itertools.repeat(top_k_doc),
                chunksize=1,
            )
            base_index = 0
            for chunk, ranked_chunk in zip(chunks, results, strict=False):
                for item, ranked in zip(corpus[base_index : base_index + len(chunk)], ranked_chunk, strict=False):
                    _append_ranked_keyword_rows(
                        doc_keyword_rows,
                        project_scores,
                        doc_id=str(item["doc_id"]),
                        ranked=ranked,
                        top_k_doc=top_k_doc,
                    )
                base_index += len(chunk)
                completed += len(chunk)
                if progress_callback is not None:
                    progress_callback(min(completed, len(corpus)), len(corpus))
    except Exception:
        return _yake_keyword_rows_serial(corpus, top_k_doc, top_k_project, progress_callback)

    return [*doc_keyword_rows, *_project_keyword_rows(project_scores, top_k_project)]


def yake_keyword_rows(
    corpus: list[dict[str, Any]],
    analysis_params: dict[str, Any],
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[dict[str, Any]]:
    top_k_doc = max(1, int(analysis_params.get("top_k_per_doc", 10)))
    top_k_project = max(1, int(analysis_params.get("top_k_project", 100)))
    return _yake_keyword_rows_parallel(corpus, top_k_doc, top_k_project, progress_callback)


def should_use_fast_keyword_extraction(corpus: list[dict[str, Any]]) -> bool:
    if len(corpus) >= 2000:
        return True
    token_count = sum(len(item.get("filtered_tokens") or []) for item in corpus)
    return token_count >= 150000


def tfidf_keyword_rows(
    corpus: list[dict[str, Any]],
    tfidf_bundle: TfidfAnalysisBundle,
    analysis_params: dict[str, Any],
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[dict[str, Any]]:
    if tfidf_bundle.empty:
        return []

    top_k_doc = max(1, int(analysis_params.get("top_k_per_doc", 10)))
    top_k_project = max(1, int(analysis_params.get("top_k_project", 100)))
    doc_keyword_rows: list[dict[str, Any]] = []
    project_scores: dict[str, dict[str, float | str | int]] = {}
    matrix = tfidf_bundle.matrix.tocsr() if hasattr(tfidf_bundle.matrix, "tocsr") else tfidf_bundle.matrix
    terms = list(tfidf_bundle.terms)
    total = len(corpus)

    for index, item in enumerate(corpus, start=1):
        ranked: list[tuple[str, float]] = []
        row = matrix.getrow(index - 1) if hasattr(matrix, "getrow") else matrix[index - 1]
        indices = getattr(row, "indices", [])
        values = getattr(row, "data", [])

        if len(indices):
            ranking = np.argsort(values)[::-1]
            seen: set[str] = set()
            for position in ranking:
                term = terms[int(indices[position])]
                keyword = normalize_keyword_candidate(term)
                if not keyword or keyword in seen:
                    continue
                seen.add(keyword)
                ranked.append((keyword, round(float(values[position]), 6)))
                if len(ranked) >= top_k_doc:
                    break

        if not ranked:
            ranked = fallback_keywords(item.get("filtered_tokens", []), top_k_doc)

        _append_ranked_keyword_rows(
            doc_keyword_rows,
            project_scores,
            doc_id=str(item["doc_id"]),
            ranked=ranked,
            top_k_doc=top_k_doc,
        )

        if progress_callback is not None and (index == 1 or index == total or index % 250 == 0):
            progress_callback(index, total)

    return [*doc_keyword_rows, *_project_keyword_rows(project_scores, top_k_project)]


def extract_keyword_rows(
    corpus: list[dict[str, Any]],
    analysis_params: dict[str, Any],
    tfidf_bundle: TfidfAnalysisBundle | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[dict[str, Any]]:
    if should_use_fast_keyword_extraction(corpus) and tfidf_bundle is not None and not tfidf_bundle.empty:
        return tfidf_keyword_rows(corpus, tfidf_bundle, analysis_params, progress_callback)
    return yake_keyword_rows(corpus, analysis_params, progress_callback)


def tfidf_feature_bundle(
    corpus: list[dict[str, Any]],
    analysis_params: dict[str, Any],
) -> tuple[list[dict[str, Any]], TfidfAnalysisBundle]:
    documents = [" ".join(item["filtered_tokens"]) for item in corpus]
    if not any(documents):
        return [], TfidfAnalysisBundle(doc_ids=[], terms=[], matrix=None)

    vectorizer = TfidfVectorizer(tokenizer=str.split, preprocessor=None, token_pattern=None, lowercase=False)
    matrix = vectorizer.fit_transform(documents)
    terms = vectorizer.get_feature_names_out()
    term_scores = np.asarray(matrix.sum(axis=0)).ravel()
    ranking = np.argsort(term_scores)[::-1]
    selected_count = analysis_params.get("feature_term_count", "all")
    if selected_count in (None, ""):
        selected_count = "all"
    selected_limit = len(ranking) if selected_count == "all" else min(int(selected_count), len(ranking))

    feature_rows: list[dict[str, Any]] = []
    for position, index in enumerate(ranking):
        feature_rows.append(
            {
                "term": terms[index],
                "score": float(term_scores[index]),
                "selected": position < selected_limit,
                "source": "auto",
                "rank": position + 1,
            }
        )

    selected_indices = [int(index) for index in ranking[:selected_limit]]
    selected_terms = [str(terms[index]) for index in selected_indices]
    selected_matrix = matrix[:, selected_indices] if selected_indices else None
    tfidf_bundle = TfidfAnalysisBundle(
        doc_ids=[str(item["doc_id"]) for item in corpus],
        terms=selected_terms,
        matrix=selected_matrix,
    )
    return feature_rows, tfidf_bundle


def tfidf_analysis(
    corpus: list[dict[str, Any]],
    analysis_params: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], TfidfAnalysisBundle]:
    feature_rows, tfidf_bundle = tfidf_feature_bundle(corpus, analysis_params)
    keyword_rows = extract_keyword_rows(corpus, analysis_params, tfidf_bundle)
    return feature_rows, keyword_rows, tfidf_bundle
