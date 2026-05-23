from __future__ import annotations

import itertools
import math
from collections import Counter
from typing import Any, Callable

import pandas as pd

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
        if progress_callback is not None and (index == 1 or index == total or index % 250 == 0):
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

