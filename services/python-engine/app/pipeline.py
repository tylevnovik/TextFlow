from __future__ import annotations

import itertools
import math
import os
import re
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import jieba
import numpy as np
import pandas as pd
import yake
from sklearn.cluster import KMeans
from sklearn.decomposition import NMF, PCA
from sklearn.feature_extraction.text import TfidfVectorizer

from .defaults import empty_result_bundle, utc_now_iso
from .reporting import write_run_outputs

os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")
jieba.setLogLevel(20)

CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]+")
TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fff]+|[A-Za-z0-9_]+(?:[-/][A-Za-z0-9_]+)*")
HTML_PATTERN = re.compile(r"<[^>]+>")
URL_PATTERN = re.compile(r"https?://\S+|www\.\S+")
EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@[\w.-]+\.\w+\b")
PHONE_PATTERN = re.compile(r"\b(?:\+?\d[\d -]{7,}\d)\b")
EMOJI_PATTERN = re.compile(r"[\U00010000-\U0010ffff]", flags=re.UNICODE)
DATE_PATTERN = re.compile(
    r"\b(?:\d{4}[-/年.]\d{1,2}[-/月.]\d{1,2}日?|\d{1,2}[:：]\d{2}(?::\d{2})?)\b"
)

TRADITIONAL_TO_SIMPLIFIED = str.maketrans(
    {
        "體": "体",
        "學": "学",
        "術": "术",
        "寫": "写",
        "作": "作",
        "變": "变",
        "為": "为",
        "與": "与",
        "關": "关",
        "時": "时",
        "間": "间",
        "聯": "联",
        "數": "数",
        "據": "据",
        "網": "网",
        "頁": "页",
        "規": "规",
        "範": "范",
        "標": "标",
        "準": "准",
        "詞": "词",
        "彙": "汇",
        "處": "处",
        "理": "理",
        "機": "机",
        "構": "构",
        "題": "题",
        "門": "门",
        "類": "类",
        "檢": "检",
        "測": "测",
        "續": "续",
        "壓": "压",
        "縮": "缩",
        "後": "后",
        "臺": "台",
        "專": "专",
        "利": "利",
        "雲": "云",
        "庫": "库",
        "價": "价",
    }
)
DEFAULT_PIPELINE_ORDER = [
    "ingestion",
    "cleaning",
    "normalization",
    "tokenization",
    "dictionary_application",
    "filtering",
    "analysis",
    "export",
]

ProgressCallback = Callable[[float, str], None]


def normalize_run_scope(scope: dict[str, Any] | None) -> dict[str, Any]:
    scope = dict(scope or {})
    return {
        "mode": scope.get("mode", "all_documents"),
        "source_values": [str(value) for value in scope.get("source_values", []) if str(value).strip()],
        "institution_values": [str(value) for value in scope.get("institution_values", []) if str(value).strip()],
        "category_values": [str(value) for value in scope.get("category_values", []) if str(value).strip()],
        "year_from": scope.get("year_from"),
        "year_to": scope.get("year_to"),
        "selected_doc_ids": [str(value) for value in scope.get("selected_doc_ids", []) if str(value).strip()],
    }


def document_matches_scope(item: dict[str, Any], scope: dict[str, Any]) -> bool:
    mode = scope.get("mode", "all_documents")
    doc_id = str(item.get("doc_id") or item.get("id") or "")
    if mode == "selected_documents":
        selected_doc_ids = set(scope.get("selected_doc_ids", []))
        return doc_id in selected_doc_ids
    if mode != "filtered_subset":
        return True

    source_values = set(scope.get("source_values", []))
    institution_values = set(scope.get("institution_values", []))
    category_values = set(scope.get("category_values", []))
    year_from = scope.get("year_from")
    year_to = scope.get("year_to")
    year = item.get("year")

    if source_values and str(item.get("source") or "") not in source_values:
        return False
    if institution_values and str(item.get("institution") or "") not in institution_values:
        return False
    if category_values and str(item.get("category_or_tag") or "") not in category_values:
        return False
    if year_from not in (None, ""):
        if year is None or int(year) < int(year_from):
            return False
    if year_to not in (None, ""):
        if year is None or int(year) > int(year_to):
            return False
    return True


def describe_run_scope(scope: dict[str, Any], total_count: int, matched_count: int) -> str:
    mode = scope.get("mode", "all_documents")
    if mode == "selected_documents":
        selected_doc_ids = scope.get("selected_doc_ids", [])
        return f"手动选择 {len(selected_doc_ids)} 篇文档，实际命中 {matched_count}/{total_count} 篇。"
    if mode != "filtered_subset":
        return f"处理对象为项目内全部资料，共 {matched_count}/{total_count} 篇文档。"

    parts: list[str] = []
    if scope.get("source_values"):
        parts.append(f"来源={', '.join(scope['source_values'])}")
    if scope.get("institution_values"):
        parts.append(f"机构={', '.join(scope['institution_values'])}")
    if scope.get("category_values"):
        parts.append(f"标签={', '.join(scope['category_values'])}")
    year_from = scope.get("year_from")
    year_to = scope.get("year_to")
    if year_from not in (None, "") or year_to not in (None, ""):
        if year_from not in (None, "") and year_to not in (None, ""):
            parts.append(f"年份={year_from}-{year_to}")
        elif year_from not in (None, ""):
            parts.append(f"年份>= {year_from}")
        else:
            parts.append(f"年份<= {year_to}")
    detail = "；".join(parts) if parts else "已启用条件筛选"
    return f"处理对象为筛选资料：{detail}，实际命中 {matched_count}/{total_count} 篇文档。"


def describe_output_bundle(export_params: dict[str, Any]) -> str:
    outputs: list[str] = []
    if export_params.get("export_csv", True) or export_params.get("export_xlsx", True):
        outputs.append("表格包")
    if export_params.get("export_png", True):
        outputs.append("图表包")
    if export_params.get("export_html_report", True):
        outputs.append("HTML 报告")
    if export_params.get("include_audit", True):
        outputs.append("审计表")
    return "、".join(outputs) or "仅运行快照"


def normalize_width(text: str) -> str:
    return text.translate({0x3000: 0x20, **{code: code - 0xFEE0 for code in range(0xFF01, 0xFF5F)}})


def regex_entries(dictionary_set: dict[str, Any]) -> list[dict[str, Any]]:
    return [entry for entry in dictionary_set["sheets"]["regex_rules"]["entries"] if entry.get("enabled", True)]


def sheet_entries(dictionary_set: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    return [entry for entry in dictionary_set["sheets"][kind]["entries"] if entry.get("enabled", True)]


def audit_row(
    doc_id: str,
    position: int,
    source_term: str,
    target_term: str | None,
    rule_type: str,
    rule_source: str,
    rule_key: str,
    action: str,
) -> dict[str, Any]:
    return {
        "doc_id": doc_id,
        "position": position,
        "source_term": source_term,
        "target_term": target_term,
        "rule_type": rule_type,
        "rule_source": rule_source,
        "rule_key": rule_key,
        "action": action,
    }


def apply_cleaning(text: str, params: dict[str, Any]) -> tuple[str, list[str]]:
    flags: list[str] = []
    cleaned = text or ""

    if params.get("strip_html", True):
        next_text = HTML_PATTERN.sub(" ", cleaned)
        if next_text != cleaned:
            flags.append("strip_html")
        cleaned = next_text

    if params.get("strip_urls", True):
        next_text = URL_PATTERN.sub(" ", cleaned)
        if next_text != cleaned:
            flags.append("strip_urls")
        cleaned = next_text

    if params.get("strip_email", False):
        next_text = EMAIL_PATTERN.sub(" ", cleaned)
        if next_text != cleaned:
            flags.append("strip_email")
        cleaned = next_text

    if params.get("strip_phone", False):
        next_text = PHONE_PATTERN.sub(" ", cleaned)
        if next_text != cleaned:
            flags.append("strip_phone")
        cleaned = next_text

    if params.get("remove_emoji", False):
        next_text = EMOJI_PATTERN.sub("", cleaned)
        if next_text != cleaned:
            flags.append("remove_emoji")
        cleaned = next_text

    if params.get("full_half_width_normalize", True):
        next_text = normalize_width(cleaned)
        if next_text != cleaned:
            flags.append("full_half_width_normalize")
        cleaned = next_text

    if params.get("lowercase_english", True):
        next_text = cleaned.lower()
        if next_text != cleaned:
            flags.append("lowercase_english")
        cleaned = next_text

    if params.get("normalize_punctuation", True):
        next_text = re.sub(r"[，、；：]", " ", cleaned)
        next_text = re.sub(r"[。！？!?,.;:]", " ", next_text)
        if next_text != cleaned:
            flags.append("normalize_punctuation")
        cleaned = next_text

    if params.get("normalize_whitespace", True):
        next_text = re.sub(r"\s+", " ", cleaned).strip()
        if next_text != cleaned:
            flags.append("normalize_whitespace")
        cleaned = next_text

    if params.get("remove_special_chars", False):
        next_text = re.sub(r"[^\w\s\u4e00-\u9fff-]", " ", cleaned)
        if next_text != cleaned:
            flags.append("remove_special_chars")
        cleaned = re.sub(r"\s+", " ", next_text).strip()

    return cleaned, flags


def apply_normalization(text: str, dictionary_set: dict[str, Any], params: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    normalized = text
    audit_rows: list[dict[str, Any]] = []

    if params.get("convert_traditional_to_simplified", False):
        next_text = normalized.translate(TRADITIONAL_TO_SIMPLIFIED)
        if next_text != normalized:
            audit_rows.append(
                {
                    "doc_id": "",
                    "source_term": "traditional_text",
                    "target_term": "simplified_text",
                    "rule_type": "traditional_to_simplified",
                    "rule_source": "builtin",
                    "rule_key": "traditional_to_simplified",
                    "action": "replace",
                }
            )
        normalized = next_text

    if params.get("normalize_numbers", False):
        next_text = re.sub(r"\d+(?:\.\d+)?", " NUM_TOKEN ", normalized)
        if next_text != normalized:
            audit_rows.append(
                {
                    "doc_id": "",
                    "source_term": "number",
                    "target_term": "NUM_TOKEN",
                    "rule_type": "number_normalization",
                    "rule_source": "builtin",
                    "rule_key": "number",
                    "action": "replace",
                }
            )
        normalized = next_text

    if params.get("normalize_time_expr", False):
        next_text = DATE_PATTERN.sub(" TIME_TOKEN ", normalized)
        if next_text != normalized:
            audit_rows.append(
                {
                    "doc_id": "",
                    "source_term": "time_expression",
                    "target_term": "TIME_TOKEN",
                    "rule_type": "time_normalization",
                    "rule_source": "builtin",
                    "rule_key": "time_expression",
                    "action": "replace",
                }
            )
        normalized = next_text

    if params.get("apply_regex_rules", True):
        for entry in regex_entries(dictionary_set):
            source = entry["source"]
            target = entry.get("target", "")
            matches = list(re.finditer(source, normalized))
            if not matches:
                continue
            normalized = re.sub(source, f" {target} ", normalized)
            audit_rows.append(
                {
                    "doc_id": "",
                    "source_term": source,
                    "target_term": target,
                    "rule_type": "regex_rule",
                    "rule_source": "regex_rules.json",
                    "rule_key": source,
                    "action": "replace",
                }
            )
            if params.get("regex_rule_priority") == "first_match":
                break

    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized, audit_rows


def protect_phrases(text: str, dictionary_set: dict[str, Any], use_phrase_lexicon: bool) -> tuple[str, dict[str, str], list[str]]:
    if not use_phrase_lexicon:
        return text, {}, []

    phrase_map: dict[str, str] = {}
    phrase_hits: list[str] = []
    protected = text
    entries = sorted(sheet_entries(dictionary_set, "phrase_lexicon"), key=lambda item: len(item["source"]), reverse=True)

    for index, entry in enumerate(entries):
        source = entry["source"]
        target = entry.get("target") or source.replace(" ", "_")
        marker = f"phrase_marker_{index}"
        pattern = re.compile(re.escape(source), flags=re.IGNORECASE)
        if pattern.search(protected):
            protected = pattern.sub(f" {marker} ", protected)
            phrase_map[marker] = target
            phrase_hits.append(target)

    return protected, phrase_map, phrase_hits


def cjk_lexicon(dictionary_set: dict[str, Any], tokenization_params: dict[str, Any]) -> list[str]:
    candidates: set[str] = set()
    kinds = ["standard_terms", "synonym_map", "near_synonym_map"]
    if tokenization_params.get("use_custom_lexicon", True):
        kinds.append("custom_lexicon")
    if tokenization_params.get("use_phrase_lexicon", True):
        kinds.append("phrase_lexicon")
    for kind in kinds:
        for entry in sheet_entries(dictionary_set, kind):
            for value in [entry.get("source"), entry.get("target")]:
                if value and re.search(r"[\u4e00-\u9fff]", str(value)):
                    candidates.add(str(value).replace(" ", ""))
    return sorted(candidates, key=len, reverse=True)


def seed_jieba_dictionary(dictionary_set: dict[str, Any], tokenization_params: dict[str, Any]) -> None:
    for term in cjk_lexicon(dictionary_set, tokenization_params):
        jieba.add_word(term)


def segment_cjk(chunk: str, dictionary_set: dict[str, Any], tokenization_params: dict[str, Any]) -> list[str]:
    seed_jieba_dictionary(dictionary_set, tokenization_params)
    return [token.strip() for token in jieba.lcut(chunk) if token.strip()]


def tokenize_text(text: str, dictionary_set: dict[str, Any], params: dict[str, Any]) -> tuple[list[str], list[str]]:
    protected, phrase_map, phrase_hits = protect_phrases(
        text,
        dictionary_set,
        params.get("use_phrase_lexicon", True) and params.get("preserve_domain_phrases", True),
    )
    tokens: list[str] = []

    for match in TOKEN_PATTERN.finditer(protected):
        chunk = match.group(0)
        if chunk in phrase_map:
            tokens.append(phrase_map[chunk])
            continue

        if CJK_PATTERN.fullmatch(chunk):
            tokens.extend(segment_cjk(chunk, dictionary_set, params))
            continue

        normalized = chunk
        if params.get("normalize_camel_case", True):
            normalized = re.sub(r"([a-z])([A-Z])", r"\1 \2", normalized)
        if params.get("split_hyphenated_terms", True):
            normalized = normalized.replace("-", " ")
        if params.get("split_slash_terms", False):
            normalized = normalized.replace("/", " ")
        for token in re.split(r"\s+", normalized):
            token = token.strip().lower()
            if token:
                tokens.append(token)

    min_length = params.get("min_token_length_before_filter", 1)
    return [token for token in tokens if len(token) >= min_length], phrase_hits


def build_dictionary_maps(dictionary_set: dict[str, Any]) -> dict[str, dict[str, str | None]]:
    maps: dict[str, dict[str, str | None]] = {}
    for kind in [
        "standard_terms",
        "synonym_map",
        "near_synonym_map",
        "stopwords",
        "exclusion_terms",
    ]:
        maps[kind] = {}
        for entry in sheet_entries(dictionary_set, kind):
            maps[kind][entry["source"].lower()] = entry.get("target")
    return maps


def increment_dictionary_hit(dictionary_set: dict[str, Any], kind: str, source: str) -> None:
    for entry in sheet_entries(dictionary_set, kind):
        if entry["source"].lower() == source.lower():
            entry["hits"] = int(entry.get("hits", 0)) + 1
            return


def apply_dictionary(
    doc_id: str,
    tokens: list[str],
    dictionary_set: dict[str, Any],
    params: dict[str, Any],
) -> tuple[list[str], list[dict[str, Any]]]:
    maps = build_dictionary_maps(dictionary_set)
    result: list[str] = []
    audits: list[dict[str, Any]] = []

    for position, token in enumerate(tokens):
        lowered = token.lower()

        if params.get("apply_exclusion_terms", True) and lowered in maps["exclusion_terms"]:
            increment_dictionary_hit(dictionary_set, "exclusion_terms", lowered)
            audits.append(
                audit_row(doc_id, position, token, None, "exclusion_terms", "exclusion_terms.json", lowered, "drop")
            )
            continue

        target = token
        action = "keep"
        rule_type = "keep"
        rule_source = "pipeline"
        rule_key = token

        if params.get("apply_standard_terms", True) and lowered in maps["standard_terms"]:
            target = maps["standard_terms"][lowered] or token
            increment_dictionary_hit(dictionary_set, "standard_terms", lowered)
            action = "replace"
            rule_type = "standard_terms"
            rule_source = "standard_terms.json"
            rule_key = lowered
        elif params.get("apply_synonym_map", True) and lowered in maps["synonym_map"]:
            target = maps["synonym_map"][lowered] or token
            increment_dictionary_hit(dictionary_set, "synonym_map", lowered)
            action = "replace"
            rule_type = "synonym_map"
            rule_source = "synonym_map.json"
            rule_key = lowered
        elif params.get("apply_near_synonym_map", True) and lowered in maps["near_synonym_map"]:
            target = maps["near_synonym_map"][lowered] or token
            increment_dictionary_hit(dictionary_set, "near_synonym_map", lowered)
            action = "replace"
            rule_type = "near_synonym_map"
            rule_source = "near_synonym_map.json"
            rule_key = lowered

        target_lower = str(target).lower()
        if params.get("apply_stopwords", True) and target_lower in maps["stopwords"]:
            increment_dictionary_hit(dictionary_set, "stopwords", target_lower)
            audits.append(
                audit_row(doc_id, position, token, str(target), "stopwords", "stopwords.json", target_lower, "drop")
            )
            continue

        result.append(str(target))
        audits.append(audit_row(doc_id, position, token, str(target), rule_type, rule_source, rule_key, action))

    return result, audits


def filter_token_lists(corpus: list[dict[str, Any]], params: dict[str, Any], dictionary_set: dict[str, Any]) -> None:
    token_frequency = Counter(token for item in corpus for token in item["tokens"])
    important_single_chars = (
        {entry["source"] for entry in sheet_entries(dictionary_set, "custom_lexicon") if len(entry["source"]) == 1}
        if params.get("keep_single_char_important_terms", True)
        else set()
    )

    for item in corpus:
        filtered: list[str] = []
        for token in item["tokens"]:
            if len(token) < params.get("min_token_length", 2) and token not in important_single_chars:
                continue
            if params.get("filter_numeric_tokens", False) and token.isdigit():
                continue
            if token_frequency[token] < params.get("min_term_frequency", 1):
                continue
            filtered.append(token)
        item["filtered_tokens"] = filtered


def enabled_step_order(pipeline_definition: dict[str, Any]) -> list[str]:
    enabled = set(pipeline_definition.get("enabled_steps") or DEFAULT_PIPELINE_ORDER)
    requested_order = pipeline_definition.get("execution_order") or DEFAULT_PIPELINE_ORDER
    ordered = [step for step in requested_order if step in enabled and step in DEFAULT_PIPELINE_ORDER]
    for step in DEFAULT_PIPELINE_ORDER:
        if step in enabled and step not in ordered:
            ordered.append(step)
    return ordered


def step_enabled(pipeline_definition: dict[str, Any], step: str) -> bool:
    return step in set(enabled_step_order(pipeline_definition))


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
    year_totals = filtered.groupby("year").size().to_dict()
    grouped = (
        filtered.groupby(["term", "year"])
        .agg(tf_in_year=("term", "size"), df_in_year=("doc_id", pd.Series.nunique))
        .reset_index()
    )
    grouped["ratio_in_year"] = grouped.apply(
        lambda row: row["tf_in_year"] / year_totals.get(row["year"], 1),
        axis=1,
    )
    return grouped.sort_values(["tf_in_year", "df_in_year"], ascending=False).to_dict(orient="records")


def cooccurrence_table(corpus: list[dict[str, Any]], window_size: int, min_cooccurrence: int) -> list[dict[str, Any]]:
    counter: Counter[tuple[str, str]] = Counter()
    for item in corpus:
        tokens = item["filtered_tokens"]
        for start in range(len(tokens)):
            window = tokens[start : start + window_size]
            for a, b in itertools.combinations(sorted(set(window)), 2):
                counter[(a, b)] += 1

    rows = [
        {
            "term_a": a,
            "term_b": b,
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


def yake_keyword_rows(corpus: list[dict[str, Any]], analysis_params: dict[str, Any]) -> list[dict[str, Any]]:
    top_k_doc = max(1, int(analysis_params.get("top_k_per_doc", 10)))
    top_k_project = max(1, int(analysis_params.get("top_k_project", 100)))
    doc_keyword_rows: list[dict[str, Any]] = []
    project_scores: dict[str, dict[str, float | str | int]] = {}

    for item in corpus:
        text = build_analysis_text(item)
        ranked: list[tuple[str, float]] = []
        if text:
            extractor = yake.KeywordExtractor(
                lan=yake_language(text),
                n=3,
                dedupLim=0.85,
                dedupFunc="seqm",
                windowsSize=2,
                top=max(top_k_doc * 3, top_k_doc),
            )
            seen: set[str] = set()
            for candidate, raw_score in extractor.extract_keywords(text):
                normalized = normalize_keyword_candidate(candidate)
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                ranked.append((normalized, round(1.0 / (1.0 + max(float(raw_score), 0.0)), 6)))
                if len(ranked) >= top_k_doc:
                    break

        if not ranked:
            ranked = fallback_keywords(item.get("filtered_tokens", []), top_k_doc)

        doc_seen: set[str] = set()
        for rank, (keyword, score) in enumerate(ranked[:top_k_doc], start=1):
            doc_keyword_rows.append(
                {
                    "scope": "doc",
                    "doc_id": item["doc_id"],
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

    return [*doc_keyword_rows, *project_keyword_rows]


def tfidf_analysis(corpus: list[dict[str, Any]], analysis_params: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], pd.DataFrame]:
    documents = [" ".join(item["filtered_tokens"]) for item in corpus]
    if not any(documents):
        return [], [], pd.DataFrame()

    vectorizer = TfidfVectorizer(tokenizer=str.split, preprocessor=None, token_pattern=None, lowercase=False)
    matrix = vectorizer.fit_transform(documents)
    terms = vectorizer.get_feature_names_out()
    term_scores = np.asarray(matrix.sum(axis=0)).ravel()
    ranking = np.argsort(term_scores)[::-1]
    selected_count = analysis_params.get("feature_term_count", "all")
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

    keyword_rows = yake_keyword_rows(corpus, analysis_params)

    term_doc_df = pd.DataFrame(
        matrix.toarray().T,
        index=terms,
        columns=[item["doc_id"] for item in corpus],
    )
    return feature_rows, keyword_rows, term_doc_df


def nmf_topic_model(
    corpus: list[dict[str, Any]],
    term_doc_df: pd.DataFrame,
    analysis_params: dict[str, Any],
) -> tuple[dict[int, dict[str, Any]], dict[str, dict[str, Any]]]:
    if term_doc_df.empty:
        return {}, {}

    document_matrix = term_doc_df.T.to_numpy()
    if document_matrix.size == 0:
        return {}, {}

    requested_topics = int(analysis_params.get("topic_model_k", analysis_params.get("keyword_cluster_k", 4)))
    topic_count = max(1, min(requested_topics, document_matrix.shape[0], document_matrix.shape[1]))
    init = "nndsvda" if topic_count <= min(document_matrix.shape) else "random"
    model = NMF(n_components=topic_count, init=init, random_state=42, max_iter=400)
    doc_topic_matrix = model.fit_transform(document_matrix)

    terms = term_doc_df.index.to_list()
    topic_lookup: dict[int, dict[str, Any]] = {}
    for topic_id, weights in enumerate(model.components_):
        ranking = np.argsort(weights)[::-1]
        top_terms = [humanize_term(terms[index]) for index in ranking if weights[index] > 0][:5]
        label_terms = top_terms[:3] or [humanize_term(terms[ranking[0]])]
        topic_lookup[topic_id] = {
            "label": " / ".join(label_terms),
            "terms": top_terms,
        }

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


def keyword_clusters(
    feature_rows: list[dict[str, Any]],
    term_doc_df: pd.DataFrame,
    cluster_k: int,
) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]]]:
    selected = [row for row in feature_rows if row["selected"]]
    if not selected or term_doc_df.empty:
        return [], {}

    selected_terms = [row["term"] for row in selected if row["term"] in term_doc_df.index]
    if not selected_terms:
        return [], {}

    feature_matrix = term_doc_df.loc[selected_terms].to_numpy()
    cluster_count = max(1, min(cluster_k, len(selected_terms)))
    model = KMeans(n_clusters=cluster_count, random_state=42, n_init="auto")
    labels = model.fit_predict(feature_matrix)

    cluster_rows: list[dict[str, Any]] = []
    topic_lookup: dict[int, dict[str, Any]] = defaultdict(lambda: {"terms": []})

    for index, term in enumerate(selected_terms):
        centroid = model.cluster_centers_[labels[index]]
        distance = float(np.linalg.norm(feature_matrix[index] - centroid))
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


def document_clusters(corpus: list[dict[str, Any]], term_doc_df: pd.DataFrame, cluster_k: int) -> list[dict[str, Any]]:
    if term_doc_df.empty:
        return []

    document_matrix = term_doc_df.T.to_numpy()
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

    model = KMeans(n_clusters=cluster_count, random_state=42, n_init="auto")
    labels = model.fit_predict(document_matrix)
    reducer = PCA(n_components=2)
    coords = reducer.fit_transform(document_matrix) if document_matrix.shape[1] >= 2 else np.pad(document_matrix, ((0, 0), (0, 2 - document_matrix.shape[1])))
    if coords.shape[1] > 2:
        coords = coords[:, :2]

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


def build_run_record(
    manifest: dict[str, Any],
    logs: list[dict[str, Any]],
    warnings: list[str],
    errors: list[str],
    processed_document_count: int,
    run_scope_summary: str,
    recipe_id: str,
    output_bundle_id: str,
    output_summary: str,
) -> dict[str, Any]:
    run_id = f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:6]}"
    return {
        "run_id": run_id,
        "project_id": manifest["id"],
        "pipeline_version": manifest["pipeline"]["id"],
        "dictionary_version": manifest["dictionary_set"]["version"],
        "started_at": utc_now_iso(),
        "ended_at": None,
        "status": "running",
        "warnings": warnings,
        "errors": errors,
        "logs": logs,
        "artifacts": [],
        "params_snapshot_path": f"runs/{run_id}/params_snapshot.json",
        "processed_document_count": processed_document_count,
        "run_scope_summary": run_scope_summary,
        "recipe_id": recipe_id,
        "output_bundle_id": output_bundle_id,
        "output_summary": output_summary,
    }


def update_log(logs: list[dict[str, Any]], step: str, message: str, level: str = "info") -> None:
    logs.append({"timestamp": utc_now_iso(), "level": level, "step": step, "message": message})


def notify_progress(progress_callback: ProgressCallback | None, progress: float, message: str) -> None:
    if progress_callback is None:
        return
    progress_callback(progress, message)


def run_project_pipeline(
    project_dir: Path,
    manifest: dict[str, Any],
    corpus: list[dict[str, Any]],
    progress_callback: ProgressCallback | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    corpus = deepcopy(corpus)
    logs: list[dict[str, Any]] = []
    warnings: list[str] = []
    errors: list[str] = []
    pipeline_definition = manifest["pipeline"]
    pipeline_definition["run_scope"] = normalize_run_scope(pipeline_definition.get("run_scope"))
    pipeline_definition["recipe_id"] = pipeline_definition.get("recipe_id", "standard_analysis")
    pipeline_definition["output_bundle_id"] = pipeline_definition.get("output_bundle_id", "full_report")
    execution_steps = enabled_step_order(pipeline_definition)
    export_params = pipeline_definition.get("export", {})
    scoped_corpus = [item for item in corpus if document_matches_scope(item, pipeline_definition["run_scope"])]
    run_scope_summary = describe_run_scope(pipeline_definition["run_scope"], len(corpus), len(scoped_corpus))
    output_summary = describe_output_bundle(export_params)
    run_record = build_run_record(
        manifest,
        logs,
        warnings,
        errors,
        len(scoped_corpus),
        run_scope_summary,
        pipeline_definition["recipe_id"],
        pipeline_definition["output_bundle_id"],
        output_summary,
    )

    normalization_audits: list[dict[str, Any]] = []
    dictionary_audits: list[dict[str, Any]] = []
    result_bundle = empty_result_bundle()
    update_log(logs, "system", f"本次执行步骤：{', '.join(execution_steps)}")
    update_log(logs, "system", run_scope_summary)
    update_log(logs, "system", f"本次输出包：{output_summary}")
    notify_progress(progress_callback, 0.08, "正在读取项目语料")

    if not scoped_corpus:
        message = "当前处理对象筛选后没有可运行的文档，请调整资料范围后重试。"
        errors.append(message)
        update_log(logs, "ingestion", message, "error")
        run_record["status"] = "failed"
        run_record["ended_at"] = utc_now_iso()
        run_record["artifacts"] = [
            {"step": "ingestion", "output_files": ["metadata/corpus.json"], "record_count": 0, "cache_hit": False},
        ]
        manifest["results"] = result_bundle
        manifest["updated_at"] = utc_now_iso()
        manifest.setdefault("run_history", []).append(run_record)
        notify_progress(progress_callback, 1.0, message)
        return manifest, corpus, run_record

    if step_enabled(pipeline_definition, "ingestion"):
        update_log(logs, "ingestion", f"已载入 {len(scoped_corpus)} 篇文档进入运行流程。")
        notify_progress(progress_callback, 0.14, "语料已载入")

    text_progress = 0.18
    for item in scoped_corpus:
        cleaned = item["raw_text"]
        if step_enabled(pipeline_definition, "cleaning"):
            cleaned, flags = apply_cleaning(item["raw_text"], pipeline_definition["cleaning"])
            if flags:
                update_log(logs, "cleaning", f"{item['doc_id']} 命中清洗规则：{', '.join(flags)}")
        item["clean_text"] = cleaned
        if not cleaned:
            item["status"] = "warning"
            warnings.append(f"{item['doc_id']} 在清洗后为空。")

        normalized = cleaned
        if step_enabled(pipeline_definition, "normalization"):
            normalized, regex_audits = apply_normalization(cleaned, manifest["dictionary_set"], pipeline_definition["normalization"])
            for audit in regex_audits:
                audit["doc_id"] = item["doc_id"]
            normalization_audits.extend(regex_audits)
        item["normalized_text"] = normalized

        tokens: list[str] = []
        phrase_hits: list[str] = []
        if step_enabled(pipeline_definition, "tokenization"):
            tokens, phrase_hits = tokenize_text(normalized, manifest["dictionary_set"], pipeline_definition["tokenization"])
        item["phrase_hits"] = phrase_hits

        if step_enabled(pipeline_definition, "dictionary_application") and tokens:
            mapped_tokens, token_audits = apply_dictionary(
                item["doc_id"],
                tokens,
                manifest["dictionary_set"],
                pipeline_definition["dictionary"],
            )
            item["tokens"] = mapped_tokens
            dictionary_audits.extend(token_audits)
        else:
            item["tokens"] = tokens
        text_progress = min(0.58, text_progress + (0.4 / max(len(scoped_corpus), 1)))
        notify_progress(progress_callback, text_progress, f"正在处理文本：{item['doc_id']}")

    if step_enabled(pipeline_definition, "filtering"):
        if pipeline_definition["filtering"].get("filter_by_pos", False):
            message = "当前 V1 后端尚未实现词性过滤，已按关闭处理。"
            warnings.append(message)
            update_log(logs, "filtering", message, "warning")
        filter_token_lists(scoped_corpus, pipeline_definition["filtering"], manifest["dictionary_set"])
        update_log(logs, "filtering", f"已完成 {len(scoped_corpus)} 篇文档的最终词项过滤。")
        notify_progress(progress_callback, 0.64, "词项过滤已完成")
    else:
        for item in scoped_corpus:
            item["filtered_tokens"] = list(item["tokens"])
        update_log(logs, "filtering", "过滤步骤已禁用，直接沿用 tokens 作为 filtered_tokens。")
        notify_progress(progress_callback, 0.64, "已跳过词项过滤")

    result_bundle["audit_table"] = normalization_audits + dictionary_audits

    frequency: list[dict[str, Any]] = []
    term_doc: list[dict[str, Any]] = []
    term_year: list[dict[str, Any]] = []
    cooccur: list[dict[str, Any]] = []
    feature_rows: list[dict[str, Any]] = []
    keyword_rows: list[dict[str, Any]] = []
    cluster_rows: list[dict[str, Any]] = []
    institution_keyword_rows: list[dict[str, Any]] = []
    institution_topic_rows: list[dict[str, Any]] = []
    clustering_rows: list[dict[str, Any]] = []
    term_doc_df = pd.DataFrame()

    if step_enabled(pipeline_definition, "analysis"):
        notify_progress(progress_callback, 0.72, "正在生成统计与关键词结果")
        df_tokens = explode_tokens(scoped_corpus)
        frequency = frequency_table(df_tokens)
        term_doc = term_document_table(df_tokens)
        term_year = term_year_table(df_tokens)
        cooccur = cooccurrence_table(
            scoped_corpus,
            pipeline_definition["analysis"]["cooccurrence_window"],
            pipeline_definition["analysis"]["min_cooccurrence"],
        )
        feature_rows, keyword_rows, term_doc_df = tfidf_analysis(scoped_corpus, pipeline_definition["analysis"])
        cluster_rows, topic_lookup = keyword_clusters(
            feature_rows,
            term_doc_df,
            pipeline_definition["analysis"]["keyword_cluster_k"],
        )
        nmf_topics, doc_topics = nmf_topic_model(scoped_corpus, term_doc_df, pipeline_definition["analysis"])
        institution_keyword_rows, institution_topic_rows = institution_keyword_and_topic(
            scoped_corpus,
            keyword_rows,
            doc_topics,
            nmf_topics,
        )
        clustering_rows = document_clusters(
            scoped_corpus,
            term_doc_df,
            pipeline_definition["analysis"]["document_cluster_k"],
        )

        result_bundle["frequency_table"] = frequency
        result_bundle["term_document_table"] = term_doc
        result_bundle["term_year_table"] = term_year
        result_bundle["cooccurrence_table"] = cooccur
        result_bundle["selected_feature_terms"] = feature_rows
        result_bundle["keyword_result"] = keyword_rows
        result_bundle["keyword_cluster_result"] = cluster_rows
        result_bundle["institution_keyword_cooccurrence"] = institution_keyword_rows
        result_bundle["institution_topic_cooccurrence"] = institution_topic_rows
        result_bundle["clustering_result"] = clustering_rows
        update_log(
            logs,
            "analysis",
            f"已使用 YAKE 生成关键词、使用 NMF 生成主题，并产出 {len(frequency)} 条高频词结果和 {len(cluster_rows)} 条关键词聚类结果。",
        )
        notify_progress(progress_callback, 0.88, "分析结果已生成")
    else:
        update_log(logs, "analysis", "分析步骤已禁用，仅保留审计与中间状态。")
        notify_progress(progress_callback, 0.82, "已跳过分析步骤")

    run_record["status"] = "completed" if not errors else "failed"
    run_record["ended_at"] = utc_now_iso()
    enabled_formats = [
        label
        for label, flag in {
            "csv": export_params.get("export_csv", True),
            "xlsx": export_params.get("export_xlsx", True),
            "png": export_params.get("export_png", True),
            "html": export_params.get("export_html_report", True),
        }.items()
        if flag
    ]
    export_message = (
        f"正在写出运行快照与导出文件，启用格式：{', '.join(enabled_formats) or 'none'}。"
        if step_enabled(pipeline_definition, "export")
        else "导出步骤已禁用，仅写出运行快照文件。"
    )
    update_log(logs, "export", export_message)
    notify_progress(progress_callback, 0.94, "正在写出运行记录与导出文件")
    report_files = write_run_outputs(project_dir, run_record["run_id"], manifest, scoped_corpus, result_bundle, run_record)
    result_bundle["report_files"] = report_files
    snapshot_prefix = f"runs/{run_record['run_id']}"
    snapshot_files = [
        f"{snapshot_prefix}/params_snapshot.json",
        f"{snapshot_prefix}/logs.json",
        f"{snapshot_prefix}/logs.txt",
        f"{snapshot_prefix}/corpus_snapshot.json",
    ]
    analysis_output_files = [path for path in report_files if "/outputs/" in path]
    export_output_files = report_files
    artifacts = [
        {"step": "ingestion", "output_files": ["metadata/corpus.json"], "record_count": len(scoped_corpus), "cache_hit": False},
    ]
    if step_enabled(pipeline_definition, "analysis"):
        artifacts.append(
            {"step": "analysis", "output_files": analysis_output_files, "record_count": len(frequency), "cache_hit": False}
        )
    artifacts.append(
        {"step": "export", "output_files": [*snapshot_files, *export_output_files], "record_count": len(export_output_files), "cache_hit": False}
    )
    run_record["artifacts"] = artifacts
    manifest["results"] = result_bundle
    manifest["updated_at"] = utc_now_iso()
    manifest.setdefault("run_history", []).append(run_record)
    notify_progress(progress_callback, 1.0, "本次运行已完成")
    return manifest, corpus, run_record
