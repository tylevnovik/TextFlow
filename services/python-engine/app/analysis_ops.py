from __future__ import annotations

import itertools
import math
import os
import re
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from multiprocessing import get_context
from typing import Any, Callable

os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")

import numpy as np
import pandas as pd
import yake
from sklearn.cluster import MiniBatchKMeans
from sklearn.decomposition import NMF, TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import davies_bouldin_score, silhouette_score

CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]+")

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


def explode_tokens(corpus: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for item in corpus:
        for token in item["filtered_tokens"]:
            rows.append(
                {
                    "doc_id": item["doc_id"],
                    "title": item["title"],
                    "term": token,
                    "year": item.get("year"),
                    "source": item.get("source"),
                    "institution": item.get("institution"),
                }
            )
    return pd.DataFrame(rows)


def frequency_table(df_tokens: pd.DataFrame) -> list[dict[str, Any]]:
    if df_tokens.empty:
        return []

    total_terms = len(df_tokens)
    df = df_tokens.groupby("term").agg(tf=("term", "size"), df=("doc_id", pd.Series.nunique))
    years = (
        df_tokens.dropna(subset=["year"])
        .groupby("term")["year"]
        .agg(["min", "max"])
        .rename(columns={"min": "first_year", "max": "last_year"})
    )
    df = df.join(years, how="left")
    df["ratio"] = df["tf"] / total_terms
    df["word_length"] = df.index.str.len()
    df["avg_per_doc"] = df["tf"] / df["df"]
    df = df.reset_index().sort_values(["tf", "df"], ascending=[False, False])
    return df.fillna("").to_dict(orient="records")


def term_document_table(df_tokens: pd.DataFrame) -> list[dict[str, Any]]:
    if df_tokens.empty:
        return []
    grouped = (
        df_tokens.groupby(["term", "doc_id", "title", "year", "source"])
        .size()
        .reset_index(name="term_count_in_doc")
        .sort_values("term_count_in_doc", ascending=False)
    )
    return grouped.to_dict(orient="records")


def term_year_table(df_tokens: pd.DataFrame) -> list[dict[str, Any]]:
    if df_tokens.empty:
        return []
    filtered = df_tokens.dropna(subset=["year"])
    if filtered.empty:
        return []
    year_totals = filtered.groupby("year").size()
    grouped = (
        filtered.groupby(["term", "year"])
        .agg(tf_in_year=("term", "size"), df_in_year=("doc_id", pd.Series.nunique))
        .reset_index()
    )
    grouped["ratio_in_year"] = grouped["tf_in_year"] / grouped["year"].map(year_totals).fillna(1)
    return grouped.sort_values(["tf_in_year", "df_in_year"], ascending=False).to_dict(orient="records")


def cooccurrence_table(
    corpus: list[dict[str, Any]],
    window_size: int,
    min_cooccurrence: int,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[dict[str, Any]]:
    counter: Counter[tuple[int, int]] = Counter()
    term_to_id: dict[str, int] = {}
    id_to_term: list[str] = []

    def _term_id(term: str) -> int:
        cached = term_to_id.get(term)
        if cached is not None:
            return cached
        next_id = len(id_to_term)
        term_to_id[term] = next_id
        id_to_term.append(term)
        return next_id

    total = len(corpus)
    for index, item in enumerate(corpus, start=1):
        token_ids = [_term_id(str(token)) for token in item["filtered_tokens"]]
        for start in range(len(token_ids)):
            window = token_ids[start : start + window_size]
            unique_window = sorted(set(window))
            for a, b in itertools.combinations(unique_window, 2):
                counter[(a, b)] += 1
        if progress_callback is not None and (index == total or index % 250 == 0):
            progress_callback(index, total)

    rows = [
        {
            "term_a": id_to_term[a],
            "term_b": id_to_term[b],
            "cooccurrence_count": count,
            "score": round(math.log(count + 1), 4),
        }
        for (a, b), count in counter.items()
        if count >= min_cooccurrence
    ]
    return sorted(rows, key=lambda row: row["cooccurrence_count"], reverse=True)


def humanize_term(term: str) -> str:
    return re.sub(r"\s+", " ", str(term).replace("_", " ")).strip()


def normalize_keyword_candidate(keyword: str) -> str | None:
    normalized = humanize_term(keyword)
    normalized = re.sub(r"[^\w\s\u4e00-\u9fff/-]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip(" -_/")
    if not normalized or normalized.isdigit():
        return None
    parts = [part for part in normalized.split(" ") if part]
    if not parts:
        return None
    if len(parts) == 1 and not re.search(r"[\u4e00-\u9fff]", parts[0]) and len(parts[0]) < 2:
        return None
    lowered = " ".join(part.lower() if not re.search(r"[\u4e00-\u9fff]", part) else part for part in parts)
    return lowered


def yake_language(text: str) -> str:
    cjk_chars = sum(len(match.group(0)) for match in CJK_PATTERN.finditer(text))
    latin_chars = len(re.findall(r"[A-Za-z]", text))
    return "zh" if cjk_chars >= latin_chars else "en"


def build_analysis_text(item: dict[str, Any]) -> str:
    sections = [
        str(item.get("title") or ""),
        " ".join(item.get("filtered_tokens", [])),
        str(item.get("keyword_field") or ""),
    ]
    return "\n".join(section for section in sections if section).strip()


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
        if progress_callback is not None and (index == total or index % 100 == 0):
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

        if progress_callback is not None and (index == total or index % 250 == 0):
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


def _reduced_cluster_matrix(matrix: Any, cluster_count: int, *, max_components: int) -> np.ndarray:
    if matrix is None or not hasattr(matrix, "shape"):
        dense = np.asarray(matrix if matrix is not None else [])
        if dense.ndim == 1:
            dense = dense.reshape(-1, 1)
        return dense

    rows, cols = matrix.shape
    if rows <= 0 or cols <= 0:
        return np.empty((rows, 0))

    upper_bound = min(rows - 1, cols - 1, max_components)
    target_components = min(
        max_components,
        max(2, cluster_count * 4),
        cols,
    )
    if upper_bound >= 2 and target_components >= 2:
        try:
            return TruncatedSVD(
                n_components=min(target_components, upper_bound),
                random_state=42,
            ).fit_transform(matrix)
        except Exception:
            pass

    dense = matrix.toarray() if hasattr(matrix, "toarray") else np.asarray(matrix)
    if dense.ndim == 1:
        dense = dense.reshape(-1, 1)
    return dense


def nmf_topic_model(
    corpus: list[dict[str, Any]],
    tfidf_bundle: TfidfAnalysisBundle,
    analysis_params: dict[str, Any],
) -> tuple[dict[int, dict[str, Any]], dict[str, dict[str, Any]]]:
    model, doc_topic_matrix, topic_lookup = _fit_nmf_topic_model(tfidf_bundle, analysis_params)
    if model is None or doc_topic_matrix is None:
        return {}, {}

    doc_topics: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(corpus):
        topic_weights = doc_topic_matrix[index]
        if topic_weights.size == 0 or float(topic_weights.max()) <= 0:
            continue
        topic_id = int(topic_weights.argmax())
        doc_topics[item["doc_id"]] = {
            "topic_id": topic_id,
            "score": float(topic_weights[topic_id]),
        }

    return topic_lookup, doc_topics


def _fit_nmf_topic_model(
    tfidf_bundle: TfidfAnalysisBundle,
    analysis_params: dict[str, Any],
) -> tuple[NMF | None, np.ndarray | None, dict[int, dict[str, Any]]]:
    if tfidf_bundle.empty:
        return None, None, {}

    document_matrix = tfidf_bundle.matrix
    if document_matrix.size == 0:
        return None, None, {}

    requested_topics = int(analysis_params.get("topic_model_k", analysis_params.get("keyword_cluster_k", 4)))
    topic_count = max(1, min(requested_topics, document_matrix.shape[0], document_matrix.shape[1]))
    init = "nndsvda" if topic_count <= min(document_matrix.shape) else "random"
    model = NMF(n_components=topic_count, init=init, random_state=42, max_iter=400)
    doc_topic_matrix = model.fit_transform(document_matrix)

    topic_lookup: dict[int, dict[str, Any]] = {}
    terms = tfidf_bundle.terms
    for topic_id, weights in enumerate(model.components_):
        ranking = np.argsort(weights)[::-1]
        top_terms = [humanize_term(terms[index]) for index in ranking if weights[index] > 0][:5]
        label_terms = top_terms[:3] or [humanize_term(terms[ranking[0]])]
        topic_lookup[topic_id] = {
            "label": " / ".join(label_terms),
            "terms": top_terms,
        }

    return model, doc_topic_matrix, topic_lookup


def topic_model_tables(
    corpus: list[dict[str, Any]],
    tfidf_bundle: TfidfAnalysisBundle,
    analysis_params: dict[str, Any],
    *,
    top_terms_per_topic: int = 5,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    model, doc_topic_matrix, topic_lookup = _fit_nmf_topic_model(tfidf_bundle, analysis_params)
    if model is None or doc_topic_matrix is None:
        return [], [], []

    topic_term_rows: list[dict[str, Any]] = []
    document_topic_rows: list[dict[str, Any]] = []
    topic_document_counts: Counter[int] = Counter()
    topic_score_totals: dict[int, float] = defaultdict(float)
    terms = list(tfidf_bundle.terms)

    for topic_id, weights in enumerate(model.components_):
        ranking = np.argsort(weights)[::-1]
        ranked_terms = [(terms[index], float(weights[index])) for index in ranking if weights[index] > 0][:top_terms_per_topic]
        for rank, (term, weight) in enumerate(ranked_terms, start=1):
            topic_term_rows.append(
                {
                    "topic_id": topic_id,
                    "topic_label": topic_lookup[topic_id]["label"],
                    "term": humanize_term(term),
                    "weight": round(weight, 6),
                    "rank": rank,
                }
            )

    for index, item in enumerate(corpus):
        topic_weights = doc_topic_matrix[index]
        if topic_weights.size == 0 or float(topic_weights.max()) <= 0:
            continue
        topic_id = int(topic_weights.argmax())
        score = float(topic_weights[topic_id])
        topic_document_counts[topic_id] += 1
        topic_score_totals[topic_id] += score
        document_topic_rows.append(
            {
                "doc_id": str(item.get("doc_id") or item.get("id") or ""),
                "title": str(item.get("title") or ""),
                "year": item.get("year"),
                "source": item.get("source"),
                "institution": item.get("institution"),
                "topic_id": topic_id,
                "topic_label": topic_lookup[topic_id]["label"],
                "topic_score": round(score, 6),
            }
        )

    topic_summary_rows = [
        {
            "topic_id": topic_id,
            "topic_label": payload["label"],
            "document_count": int(topic_document_counts.get(topic_id, 0)),
            "average_topic_score": round(
                float(topic_score_totals.get(topic_id, 0.0)) / max(int(topic_document_counts.get(topic_id, 0)), 1),
                6,
            ),
            "top_terms": " / ".join(payload["terms"][:top_terms_per_topic]),
        }
        for topic_id, payload in sorted(topic_lookup.items())
    ]
    return topic_term_rows, document_topic_rows, topic_summary_rows


def keyword_clusters(
    feature_rows: list[dict[str, Any]],
    tfidf_bundle: TfidfAnalysisBundle,
    cluster_k: int,
) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]]]:
    if tfidf_bundle.empty:
        return [], {}

    selected = [row for row in feature_rows if row["selected"]]
    term_index_lookup = {term: index for index, term in enumerate(tfidf_bundle.terms)}
    selected_terms = [row["term"] for row in selected if row["term"] in term_index_lookup]
    if not selected_terms:
        return [], {}

    selected_indices = [term_index_lookup[term] for term in selected_terms]
    cluster_count = max(1, min(cluster_k, len(selected_terms)))
    feature_matrix = tfidf_bundle.matrix[:, selected_indices].T
    cluster_matrix = _reduced_cluster_matrix(feature_matrix, cluster_count, max_components=32)
    if cluster_matrix.size == 0 or cluster_matrix.shape[1] == 0:
        return [], {}
    model = MiniBatchKMeans(n_clusters=cluster_count, random_state=42, n_init="auto", batch_size=max(32, cluster_count * 8))
    labels = model.fit_predict(cluster_matrix)

    cluster_rows: list[dict[str, Any]] = []
    topic_lookup: dict[int, dict[str, Any]] = defaultdict(lambda: {"terms": []})

    for index, term in enumerate(selected_terms):
        centroid = model.cluster_centers_[labels[index]]
        distance = float(np.linalg.norm(cluster_matrix[index] - centroid))
        topic_lookup[int(labels[index])]["terms"].append((term, distance))
        cluster_rows.append(
            {
                "term": term,
                "cluster_id": int(labels[index]),
                "distance_to_centroid": distance,
                "is_label_term": False,
                "topic_label": "",
            }
        )

    for cluster_id, payload in topic_lookup.items():
        payload["terms"].sort(key=lambda item: item[1])
        payload["label"] = " / ".join(term for term, _ in payload["terms"][:3])

    for row in cluster_rows:
        row["topic_label"] = topic_lookup[row["cluster_id"]]["label"]
        label_terms = [term for term, _ in topic_lookup[row["cluster_id"]]["terms"][:3]]
        row["is_label_term"] = row["term"] in label_terms

    return cluster_rows, topic_lookup


def institution_keyword_and_topic(
    corpus: list[dict[str, Any]],
    keyword_rows: list[dict[str, Any]],
    doc_topics: dict[str, dict[str, Any]],
    topic_lookup: dict[int, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    doc_keywords: dict[str, list[str]] = defaultdict(list)
    for row in keyword_rows:
        if row["scope"] == "doc" and row.get("doc_id"):
            doc_keywords[row["doc_id"]].append(row["keyword"])

    institution_keyword_counter: Counter[tuple[str, str, int | None]] = Counter()
    institution_topic_counter: Counter[tuple[str, int, int | None]] = Counter()

    for item in corpus:
        institution = item.get("institution")
        if not institution:
            continue
        year = item.get("year")
        for keyword in doc_keywords.get(item["doc_id"], []):
            institution_keyword_counter[(institution, keyword, year)] += 1
        topic_payload = doc_topics.get(item["doc_id"])
        if topic_payload is not None:
            institution_topic_counter[(institution, int(topic_payload["topic_id"]), year)] += 1

    keyword_rows_out = [
        {
            "institution": institution,
            "keyword": keyword,
            "cooccurrence_count": count,
            "year": year,
            "score": round(math.log(count + 1), 4),
        }
        for (institution, keyword, year), count in institution_keyword_counter.items()
    ]

    topic_rows_out = []
    for (institution, topic_id, year), count in institution_topic_counter.items():
        terms = topic_lookup.get(topic_id, {}).get("terms", [])[:3]
        topic_rows_out.append(
            {
                "institution": institution,
                "topic_id": topic_id,
                "topic_label": topic_lookup.get(topic_id, {}).get("label", f"topic-{topic_id}"),
                "cooccurrence_count": count,
                "representative_terms": terms,
                "year": year,
            }
        )

    return keyword_rows_out, topic_rows_out


def document_clusters(corpus: list[dict[str, Any]], tfidf_bundle: TfidfAnalysisBundle, cluster_k: int) -> list[dict[str, Any]]:
    if tfidf_bundle.empty:
        return []

    document_matrix = tfidf_bundle.matrix
    doc_count = len(corpus)
    cluster_count = max(1, min(cluster_k, doc_count))

    if doc_count == 1:
        return [
            {
                "doc_id": corpus[0]["doc_id"],
                "cluster_id": 0,
                "x": 0.0,
                "y": 0.0,
                "title": corpus[0]["title"],
                "year": corpus[0].get("year"),
                "source": corpus[0].get("source"),
            }
        ]

    cluster_matrix = _reduced_cluster_matrix(document_matrix, cluster_count, max_components=48)
    if cluster_matrix.size == 0 or cluster_matrix.shape[1] == 0:
        return []
    model = MiniBatchKMeans(n_clusters=cluster_count, random_state=42, n_init="auto", batch_size=max(64, cluster_count * 10))
    labels = model.fit_predict(cluster_matrix)
    if cluster_matrix.shape[1] >= 2:
        coords = cluster_matrix[:, :2]
    else:
        coords = np.pad(cluster_matrix, ((0, 0), (0, max(0, 2 - cluster_matrix.shape[1]))))
    if coords.shape[1] < 2:
        coords = np.pad(coords, ((0, 0), (0, 2 - coords.shape[1])))

    rows = []
    for index, item in enumerate(corpus):
        rows.append(
            {
                "doc_id": item["doc_id"],
                "cluster_id": int(labels[index]),
                "x": float(coords[index][0]),
                "y": float(coords[index][1]),
                "title": item["title"],
                "year": item.get("year"),
                "source": item.get("source"),
            }
        )
    return rows


def cluster_evaluation_rows(cluster_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not cluster_rows:
        return []

    frame = pd.DataFrame(cluster_rows)
    required_columns = {"cluster_id", "x", "y"}
    if not required_columns.issubset(frame.columns):
        return []

    frame = frame.dropna(subset=["cluster_id", "x", "y"])
    if frame.empty:
        return []

    labels = frame["cluster_id"].astype(int).to_numpy()
    coordinates = frame[["x", "y"]].astype(float).to_numpy()
    unique_labels = sorted(set(labels.tolist()))
    silhouette = 0.0
    davies_bouldin = 0.0

    if len(unique_labels) >= 2 and len(frame) > len(unique_labels):
        try:
            silhouette = float(silhouette_score(coordinates, labels))
        except Exception:
            silhouette = 0.0
        try:
            davies_bouldin = float(davies_bouldin_score(coordinates, labels))
        except Exception:
            davies_bouldin = 0.0

    rows: list[dict[str, Any]] = [
        {
            "row_type": "overall",
            "cluster_id": None,
            "cluster_size": int(len(frame)),
            "cluster_count": int(len(unique_labels)),
            "silhouette_score": round(silhouette, 6),
            "davies_bouldin_score": round(davies_bouldin, 6),
        }
    ]

    total = max(len(frame), 1)
    grouped = frame.groupby("cluster_id")
    for cluster_id, cluster_frame in grouped:
        centroid = cluster_frame[["x", "y"]].mean()
        rows.append(
            {
                "row_type": "cluster",
                "cluster_id": int(cluster_id),
                "cluster_size": int(len(cluster_frame)),
                "cluster_share": round(float(len(cluster_frame)) / total, 6),
                "centroid_x": round(float(centroid["x"]), 6),
                "centroid_y": round(float(centroid["y"]), 6),
                "silhouette_score": round(silhouette, 6),
                "davies_bouldin_score": round(davies_bouldin, 6),
            }
        )

    return rows


def join_table_rows(
    left_rows: list[dict[str, Any]],
    right_rows: list[dict[str, Any]],
    join_keys: list[str],
    *,
    join_type: str = "inner",
) -> list[dict[str, Any]]:
    normalized_keys = [str(key).strip() for key in join_keys if str(key).strip()]
    if not normalized_keys:
        return []

    left_frame = pd.DataFrame(left_rows)
    right_frame = pd.DataFrame(right_rows)
    if left_frame.empty or right_frame.empty:
        return []
    if not set(normalized_keys).issubset(left_frame.columns) or not set(normalized_keys).issubset(right_frame.columns):
        return []

    how = join_type if join_type in {"inner", "left", "right", "outer"} else "inner"
    joined = left_frame.merge(right_frame, on=normalized_keys, how=how, suffixes=("", "_right"))
    joined = joined.where(pd.notna(joined), None)
    return joined.to_dict(orient="records")
