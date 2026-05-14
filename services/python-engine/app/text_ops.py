from __future__ import annotations

import re
from collections import Counter
from typing import Any

import jieba

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

_REGEX_RULE_CACHE: dict[tuple[int, str], list[tuple[re.Pattern[str], str, str]]] = {}
_PHRASE_ENTRY_CACHE: dict[tuple[int, str], list[tuple[re.Pattern[str], str]]] = {}
_CJK_LEXICON_CACHE: dict[tuple[int, str, bool, bool], list[str]] = {}
_JIEBA_SEEDED_KEYS: set[tuple[int, str, bool, bool]] = set()


def _dictionary_cache_key(dictionary_set: dict[str, Any]) -> tuple[int, str]:
    return (id(dictionary_set), str(dictionary_set.get("version") or ""))


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


def apply_normalization(
    text: str,
    dictionary_set: dict[str, Any],
    params: dict[str, Any],
    *,
    collect_audit: bool = True,
) -> tuple[str, list[dict[str, Any]]]:
    normalized = text
    audit_rows: list[dict[str, Any]] = []

    def append_audit(row: dict[str, Any]) -> None:
        if collect_audit:
            audit_rows.append(row)

    if params.get("convert_traditional_to_simplified", False):
        next_text = normalized.translate(TRADITIONAL_TO_SIMPLIFIED)
        if next_text != normalized:
            append_audit(
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
            append_audit(
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
            append_audit(
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
        regex_cache_key = _dictionary_cache_key(dictionary_set)
        compiled_rules = _REGEX_RULE_CACHE.get(regex_cache_key)
        if compiled_rules is None:
            compiled_rules = [
                (re.compile(entry["source"]), entry["source"], str(entry.get("target", "")))
                for entry in regex_entries(dictionary_set)
            ]
            _REGEX_RULE_CACHE[regex_cache_key] = compiled_rules
        for pattern, source, target in compiled_rules:
            next_text, replaced_count = pattern.subn(f" {target} ", normalized)
            if not replaced_count:
                continue
            normalized = next_text
            append_audit(
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
    phrase_cache_key = _dictionary_cache_key(dictionary_set)
    compiled_entries = _PHRASE_ENTRY_CACHE.get(phrase_cache_key)
    if compiled_entries is None:
        entries = sorted(sheet_entries(dictionary_set, "phrase_lexicon"), key=lambda item: len(item["source"]), reverse=True)
        compiled_entries = [
            (re.compile(re.escape(entry["source"]), flags=re.IGNORECASE), str(entry.get("target") or entry["source"].replace(" ", "_")))
            for entry in entries
        ]
        _PHRASE_ENTRY_CACHE[phrase_cache_key] = compiled_entries

    for index, (pattern, target) in enumerate(compiled_entries):
        marker = f"phrase_marker_{index}"
        if pattern.search(protected):
            protected = pattern.sub(f" {marker} ", protected)
            phrase_map[marker] = target
            phrase_hits.append(target)

    return protected, phrase_map, phrase_hits


def cjk_lexicon(dictionary_set: dict[str, Any], tokenization_params: dict[str, Any]) -> list[str]:
    use_custom_lexicon = bool(tokenization_params.get("use_custom_lexicon", True))
    use_phrase_lexicon = bool(tokenization_params.get("use_phrase_lexicon", True))
    cache_key = (*_dictionary_cache_key(dictionary_set), use_custom_lexicon, use_phrase_lexicon)
    cached = _CJK_LEXICON_CACHE.get(cache_key)
    if cached is not None:
        return cached

    candidates: set[str] = set()
    kinds = ["standard_terms", "synonym_map", "near_synonym_map"]
    if use_custom_lexicon:
        kinds.append("custom_lexicon")
    if use_phrase_lexicon:
        kinds.append("phrase_lexicon")
    for kind in kinds:
        for entry in sheet_entries(dictionary_set, kind):
            for value in [entry.get("source"), entry.get("target")]:
                if value and re.search(r"[\u4e00-\u9fff]", str(value)):
                    candidates.add(str(value).replace(" ", ""))
    lexicon = sorted(candidates, key=len, reverse=True)
    _CJK_LEXICON_CACHE[cache_key] = lexicon
    return lexicon


def seed_jieba_dictionary(dictionary_set: dict[str, Any], tokenization_params: dict[str, Any]) -> None:
    cache_key = (
        *_dictionary_cache_key(dictionary_set),
        bool(tokenization_params.get("use_custom_lexicon", True)),
        bool(tokenization_params.get("use_phrase_lexicon", True)),
    )
    if cache_key in _JIEBA_SEEDED_KEYS:
        return
    for term in cjk_lexicon(dictionary_set, tokenization_params):
        jieba.add_word(term)
    _JIEBA_SEEDED_KEYS.add(cache_key)


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
    filtered_tokens = [token for token in tokens if len(token) >= min_length]
    if bool(params.get("enable_ngrams", False)):
        filtered_tokens = [*filtered_tokens, *_configured_ngrams(filtered_tokens, params)]
    return filtered_tokens, phrase_hits


def _configured_ngrams(tokens: list[str], params: dict[str, Any]) -> list[str]:
    if not tokens:
        return []
    ngram_min = max(2, int(params.get("ngram_min", 2) or 2))
    ngram_max = max(ngram_min, int(params.get("ngram_max", ngram_min) or ngram_min))
    ngram_max = min(ngram_max, 5)
    ngrams: list[str] = []
    seen = set(tokens)
    for width in range(ngram_min, ngram_max + 1):
        if width > len(tokens):
            break
        for index in range(0, len(tokens) - width + 1):
            candidate = "_".join(tokens[index : index + width])
            if candidate and candidate not in seen:
                ngrams.append(candidate)
                seen.add(candidate)
    return ngrams


def build_dictionary_runtime_state(dictionary_set: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    maps: dict[str, dict[str, str | None]] = {}
    hit_entries: dict[str, dict[str, dict[str, Any]]] = {}
    for kind in [
        "standard_terms",
        "synonym_map",
        "near_synonym_map",
        "stopwords",
        "exclusion_terms",
    ]:
        kind_map: dict[str, str | None] = {}
        kind_hits: dict[str, dict[str, Any]] = {}
        for entry in sheet_entries(dictionary_set, kind):
            lowered = entry["source"].lower()
            kind_map[lowered] = entry.get("target")
            kind_hits[lowered] = entry
        maps[kind] = kind_map
        hit_entries[kind] = kind_hits
    return {"maps": maps, "hit_entries": hit_entries}


def build_dictionary_maps(dictionary_set: dict[str, Any]) -> dict[str, dict[str, str | None]]:
    return build_dictionary_runtime_state(dictionary_set)["maps"]


def increment_dictionary_hit(
    dictionary_set: dict[str, Any],
    kind: str,
    source: str,
    runtime_state: dict[str, Any] | None = None,
) -> None:
    lowered = source.lower()
    if runtime_state:
        entry = ((runtime_state.get("hit_entries") or {}).get(kind) or {}).get(lowered)
        if isinstance(entry, dict):
            entry["hits"] = int(entry.get("hits", 0)) + 1
            return
    for entry in sheet_entries(dictionary_set, kind):
        if entry["source"].lower() == lowered:
            entry["hits"] = int(entry.get("hits", 0)) + 1
            return


def apply_dictionary(
    doc_id: str,
    tokens: list[str],
    dictionary_set: dict[str, Any],
    params: dict[str, Any],
    runtime_state: dict[str, Any] | None = None,
    *,
    collect_audit: bool = True,
) -> tuple[list[str], list[dict[str, Any]]]:
    runtime_state = runtime_state or build_dictionary_runtime_state(dictionary_set)
    maps = runtime_state["maps"]
    result: list[str] = []
    audits: list[dict[str, Any]] = []

    def append_audit(row: dict[str, Any]) -> None:
        if collect_audit:
            audits.append(row)

    for position, token in enumerate(tokens):
        lowered = token.lower()

        if params.get("apply_exclusion_terms", True) and lowered in maps["exclusion_terms"]:
            increment_dictionary_hit(dictionary_set, "exclusion_terms", lowered, runtime_state)
            append_audit(
                audit_row(doc_id, position, token, None, "exclusion_terms", "exclusion_terms.json", lowered, "drop")
            )
            continue

        target = token
        action = "keep"
        rule_type = "keep"
        rule_source = "workflow"
        rule_key = token

        if params.get("apply_standard_terms", True) and lowered in maps["standard_terms"]:
            target = maps["standard_terms"][lowered] or token
            increment_dictionary_hit(dictionary_set, "standard_terms", lowered, runtime_state)
            action = "replace"
            rule_type = "standard_terms"
            rule_source = "standard_terms.json"
            rule_key = lowered
        elif params.get("apply_synonym_map", True) and lowered in maps["synonym_map"]:
            target = maps["synonym_map"][lowered] or token
            increment_dictionary_hit(dictionary_set, "synonym_map", lowered, runtime_state)
            action = "replace"
            rule_type = "synonym_map"
            rule_source = "synonym_map.json"
            rule_key = lowered
        elif params.get("apply_near_synonym_map", True) and lowered in maps["near_synonym_map"]:
            target = maps["near_synonym_map"][lowered] or token
            increment_dictionary_hit(dictionary_set, "near_synonym_map", lowered, runtime_state)
            action = "replace"
            rule_type = "near_synonym_map"
            rule_source = "near_synonym_map.json"
            rule_key = lowered

        target_lower = str(target).lower()
        if params.get("apply_stopwords", True) and target_lower in maps["stopwords"]:
            increment_dictionary_hit(dictionary_set, "stopwords", target_lower, runtime_state)
            append_audit(
                audit_row(doc_id, position, token, str(target), "stopwords", "stopwords.json", target_lower, "drop")
            )
            continue

        result.append(str(target))
        if action != "keep":
            append_audit(audit_row(doc_id, position, token, str(target), rule_type, rule_source, rule_key, action))

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
