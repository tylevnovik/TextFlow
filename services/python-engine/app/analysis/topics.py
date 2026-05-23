from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import MiniBatchKMeans
from sklearn.decomposition import LatentDirichletAllocation, NMF, TruncatedSVD
from sklearn.metrics import davies_bouldin_score, silhouette_score

from .core import humanize_term
from .keywords import TfidfAnalysisBundle


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


def _fit_topic_model(
    tfidf_bundle: TfidfAnalysisBundle,
    analysis_params: dict[str, Any],
) -> tuple[Any | None, np.ndarray | None, dict[int, dict[str, Any]]]:
    if tfidf_bundle.empty:
        return None, None, {}

    document_matrix = tfidf_bundle.matrix
    if document_matrix.size == 0:
        return None, None, {}

    requested_topics = int(analysis_params.get("topic_model_k", analysis_params.get("keyword_cluster_k", 4)))
    topic_count = max(1, min(requested_topics, document_matrix.shape[0], document_matrix.shape[1]))
    algorithm = str(analysis_params.get("topic_algorithm") or "nmf").lower()
    if algorithm == "lda":
        model = LatentDirichletAllocation(
            n_components=topic_count,
            random_state=42,
            learning_method="batch",
            max_iter=20,
        )
    else:
        algorithm = "nmf"
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
            "algorithm": algorithm,
        }

    return model, doc_topic_matrix, topic_lookup


def nmf_topic_model(
    corpus: list[dict[str, Any]],
    tfidf_bundle: TfidfAnalysisBundle,
    analysis_params: dict[str, Any],
) -> tuple[dict[int, dict[str, Any]], dict[str, dict[str, Any]]]:
    model, doc_topic_matrix, topic_lookup = _fit_topic_model(tfidf_bundle, {**analysis_params, "topic_algorithm": "nmf"})
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


def topic_model_tables(
    corpus: list[dict[str, Any]],
    tfidf_bundle: TfidfAnalysisBundle,
    analysis_params: dict[str, Any],
    *,
    top_terms_per_topic: int = 5,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    model, doc_topic_matrix, topic_lookup = _fit_topic_model(tfidf_bundle, analysis_params)
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
                    "topic_algorithm": topic_lookup[topic_id].get("algorithm", "nmf"),
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
                "topic_algorithm": topic_lookup[topic_id].get("algorithm", "nmf"),
            }
        )

    topic_summary_rows = [
        {
            "topic_id": topic_id,
            "topic_label": payload["label"],
            "topic_algorithm": payload.get("algorithm", "nmf"),
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

    return cluster_rows, topic_lookup


def document_similarity_rows(
    corpus: list[dict[str, Any]],
    tfidf_bundle: TfidfAnalysisBundle,
    analysis_params: dict[str, Any],
) -> list[dict[str, Any]]:
    if tfidf_bundle.empty:
        return []
    matrix = tfidf_bundle.matrix
    if matrix is None or matrix.shape[0] < 2:
        return []

    method = str(analysis_params.get("similarity_method") or "cosine").lower()
    if method != "cosine":
        method = "cosine"
    min_similarity = float(analysis_params.get("min_similarity", 0.2) or 0.0)
    top_k = int(analysis_params.get("similarity_top_k", 200) or 200)

    similarity_matrix = matrix @ matrix.T
    if hasattr(similarity_matrix, "toarray"):
        similarity_matrix = similarity_matrix.toarray()
    similarity_matrix = np.asarray(similarity_matrix)
    doc_lookup = {
        str(item.get("doc_id") or item.get("id") or ""): item
        for item in corpus
    }

    rows: list[dict[str, Any]] = []
    for left_index, doc_id_a in enumerate(tfidf_bundle.doc_ids):
        for right_index in range(left_index + 1, len(tfidf_bundle.doc_ids)):
            score = float(similarity_matrix[left_index, right_index])
            if score < min_similarity:
                continue
            doc_id_b = tfidf_bundle.doc_ids[right_index]
            doc_a = doc_lookup.get(doc_id_a, {})
            doc_b = doc_lookup.get(doc_id_b, {})
            rows.append(
                {
                    "doc_id_a": doc_id_a,
                    "doc_id_b": doc_id_b,
                    "title_a": str(doc_a.get("title") or ""),
                    "title_b": str(doc_b.get("title") or ""),
                    "year_a": doc_a.get("year"),
                    "year_b": doc_b.get("year"),
                    "institution_a": doc_a.get("institution"),
                    "institution_b": doc_b.get("institution"),
                    "similarity": round(score, 6),
                    "similarity_method": method,
                }
            )

    rows.sort(key=lambda row: (-float(row["similarity"]), str(row["doc_id_a"]), str(row["doc_id_b"])))
    return rows[:top_k] if top_k > 0 else rows


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

