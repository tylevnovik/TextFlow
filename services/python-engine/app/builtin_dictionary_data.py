from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

BUILTIN_DICTIONARY_SOURCE_DIR = Path(__file__).resolve().with_name("builtin_dictionary_sources")
MISSPELL_ARRAY_PATTERN = re.compile(
    r"var\s+(?P<name>Dict(?:Main|American|British))\s*=\s*\[\]string\{(?P<body>.*?)\r?\n\}",
    flags=re.DOTALL,
)
MISSPELL_VALUE_PATTERN = re.compile(r'"([^"]*)"')


def _stable_entry_id(table_id: str, source: str, target: str | None) -> str:
    payload = f"{table_id}\u241f{source}\u241f{target or ''}".encode("utf-8")
    return f"{table_id}-{hashlib.sha1(payload).hexdigest()[:16]}"


def _row(table_id: str, source: str, target: str | None = None, hits: int = 0) -> tuple[str, str | None, int, str]:
    return (source, target, hits, _stable_entry_id(table_id, source, target))


def _source_path(relative_path: str) -> Path:
    path = BUILTIN_DICTIONARY_SOURCE_DIR / relative_path
    if not path.exists():
        raise RuntimeError(f"Missing built-in dictionary source file: {path}")
    return path


@lru_cache(maxsize=1)
def _source_manifest() -> dict[str, str]:
    manifest_path = BUILTIN_DICTIONARY_SOURCE_DIR / "manifest.json"
    if not manifest_path.exists():
        return {}
    payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    files = payload.get("files", []) if isinstance(payload, dict) else []
    return {
        str(item.get("relative_path")): str(item.get("source_url"))
        for item in files
        if isinstance(item, dict) and item.get("relative_path") and item.get("source_url")
    }


def _source_url(relative_path: str) -> str | None:
    return _source_manifest().get(relative_path)


def _dedupe_rows(rows: list[tuple[str, str | None, int, str]]) -> list[tuple[str, str | None, int, str]]:
    deduped: list[tuple[str, str | None, int, str]] = []
    seen: set[tuple[str, str | None]] = set()
    for source, target, hits, entry_id in rows:
        key = (source.casefold(), target.casefold() if isinstance(target, str) else None)
        if key in seen:
            continue
        seen.add(key)
        deduped.append((source, target, hits, entry_id))
    return deduped


def _load_json_terms(relative_path: str, table_id: str) -> list[tuple[str, str | None, int, str]]:
    payload = json.loads(_source_path(relative_path).read_text(encoding="utf-8"))
    rows: list[tuple[str, str | None, int, str]] = []
    for value in payload if isinstance(payload, list) else []:
        term = str(value).strip()
        if not term:
            continue
        rows.append(_row(table_id, term))
    return _dedupe_rows(rows)


def _load_thuocl_terms(relative_path: str, table_id: str) -> list[tuple[str, str | None, int, str]]:
    rows: list[tuple[str, str | None, int, str]] = []
    for raw_line in _source_path(relative_path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        term = line.split("\t", 1)[0].strip()
        if term:
            rows.append(_row(table_id, term))
    return _dedupe_rows(rows)


def _opencc_candidates(line: str) -> tuple[str, list[str]] | None:
    if not line or line.startswith("#"):
        return None
    if "\t" not in line:
        return None
    source, raw_targets = line.split("\t", 1)
    source = source.strip()
    targets = [token.strip() for token in re.split(r"\s+", raw_targets.strip()) if token.strip()]
    if not source or not targets:
        return None
    return source, targets


def _load_opencc_rows(
    relative_path: str,
    table_id: str,
    *,
    multi_target: bool | None = None,
) -> list[tuple[str, str | None, int, str]]:
    rows: list[tuple[str, str | None, int, str]] = []
    for raw_line in _source_path(relative_path).read_text(encoding="utf-8").splitlines():
        parsed = _opencc_candidates(raw_line.strip())
        if parsed is None:
            continue
        source, targets = parsed
        is_multi_target = len(targets) > 1
        if multi_target is True and not is_multi_target:
            continue
        if multi_target is False and is_multi_target:
            continue
        rows.append(_row(table_id, source, targets[0]))
    return _dedupe_rows(rows)


@lru_cache(maxsize=1)
def _load_misspell_arrays() -> dict[str, list[tuple[str, str | None, int, str]]]:
    text = _source_path("misspell/words.go").read_text(encoding="utf-8")
    arrays: dict[str, list[tuple[str, str | None, int, str]]] = {}
    table_ids = {
        "DictMain": "builtin-misspell-main",
        "DictAmerican": "builtin-misspell-american",
        "DictBritish": "builtin-misspell-british",
    }
    for match in MISSPELL_ARRAY_PATTERN.finditer(text):
        name = str(match.group("name"))
        values = MISSPELL_VALUE_PATTERN.findall(match.group("body"))
        if len(values) % 2 != 0:
            raise RuntimeError(f"Unexpected misspell dictionary shape in {name}")
        table_id = table_ids[name]
        rows = [
            _row(table_id, values[index].strip(), values[index + 1].strip())
            for index in range(0, len(values), 2)
            if values[index].strip() and values[index + 1].strip()
        ]
        arrays[name] = _dedupe_rows(rows)
    missing = [name for name in table_ids if name not in arrays]
    if missing:
        raise RuntimeError(f"Missing misspell arrays: {', '.join(missing)}")
    return arrays


def _table_spec(
    *,
    kind: str,
    table_id: str,
    name: str,
    rows: list[tuple[str, str | None, int, str]],
    description: str,
    relative_path: str,
    enabled: bool = True,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": table_id,
        "kind": kind,
        "name": name,
        "description": f"{description} 共 {len(rows)} 条，随安装包内置分发。",
        "source_url": _source_url(relative_path),
        "built_in": True,
        "editable": False,
        "enabled": enabled,
        "tags": list(tags or []),
        "rows": rows,
    }


@lru_cache(maxsize=1)
def builtin_dictionary_table_specs() -> dict[str, list[dict[str, Any]]]:
    stopwords_zh = _load_json_terms("stopwords-iso/stopwords-zh.json", "builtin-stopwords-zh")
    stopwords_en = _load_json_terms("stopwords-iso/stopwords-en.json", "builtin-stopwords-en")
    thuocl_it = _load_thuocl_terms("THUOCL/THUOCL_IT.txt", "builtin-thuocl-it")
    thuocl_finance = _load_thuocl_terms("THUOCL/THUOCL_caijing.txt", "builtin-thuocl-finance")
    thuocl_medical = _load_thuocl_terms("THUOCL/THUOCL_medical.txt", "builtin-thuocl-medical")
    thuocl_chengyu = _load_thuocl_terms("THUOCL/THUOCL_chengyu.txt", "builtin-thuocl-chengyu")
    thuocl_historical = _load_thuocl_terms("THUOCL/THUOCL_lishimingren.txt", "builtin-thuocl-historical")
    thuocl_locations = _load_thuocl_terms("THUOCL/THUOCL_diming.txt", "builtin-thuocl-locations")
    opencc_tsphrases = _load_opencc_rows("OpenCC/TSPhrases.txt", "builtin-opencc-tsphrases")
    opencc_twphrases_single = _load_opencc_rows(
        "OpenCC/TWPhrasesRev.txt",
        "builtin-opencc-twphrasesrev-single",
        multi_target=False,
    )
    opencc_twphrases_multi = _load_opencc_rows(
        "OpenCC/TWPhrasesRev.txt",
        "builtin-opencc-twphrasesrev-multi",
        multi_target=True,
    )
    misspell = _load_misspell_arrays()

    return {
        "stopwords": [
            _table_spec(
                kind="stopwords",
                table_id="builtin-stopwords-zh",
                name="停用词 · 中文（stopwords-iso）",
                rows=stopwords_zh,
                description="stopwords-iso 中文停用词完整快照。",
                relative_path="stopwords-iso/stopwords-zh.json",
                enabled=True,
                tags=["builtin", "upstream", "zh", "stopwords-iso"],
            ),
            _table_spec(
                kind="stopwords",
                table_id="builtin-stopwords-en",
                name="停用词 · English（stopwords-iso）",
                rows=stopwords_en,
                description="stopwords-iso 英文停用词完整快照。",
                relative_path="stopwords-iso/stopwords-en.json",
                enabled=True,
                tags=["builtin", "upstream", "en", "stopwords-iso"],
            ),
        ],
        "custom_lexicon": [
            _table_spec(
                kind="custom_lexicon",
                table_id="builtin-thuocl-it",
                name="术语词表 · IT（THUOCL）",
                rows=thuocl_it,
                description="THUOCL IT 词表完整快照，用于帮助技术术语整体保留。",
                relative_path="THUOCL/THUOCL_IT.txt",
                enabled=True,
                tags=["builtin", "upstream", "zh", "THUOCL", "it"],
            ),
            _table_spec(
                kind="custom_lexicon",
                table_id="builtin-thuocl-finance",
                name="术语词表 · 财经（THUOCL）",
                rows=thuocl_finance,
                description="THUOCL 财经词表完整快照。",
                relative_path="THUOCL/THUOCL_caijing.txt",
                enabled=True,
                tags=["builtin", "upstream", "zh", "THUOCL", "finance"],
            ),
            _table_spec(
                kind="custom_lexicon",
                table_id="builtin-thuocl-medical",
                name="术语词表 · 医学（THUOCL）",
                rows=thuocl_medical,
                description="THUOCL 医学词表完整快照。",
                relative_path="THUOCL/THUOCL_medical.txt",
                enabled=True,
                tags=["builtin", "upstream", "zh", "THUOCL", "medical"],
            ),
        ],
        "phrase_lexicon": [
            _table_spec(
                kind="phrase_lexicon",
                table_id="builtin-thuocl-chengyu",
                name="短语词表 · 成语（THUOCL）",
                rows=thuocl_chengyu,
                description="THUOCL 成语词表完整快照。默认关闭，避免对通用文本切分过度干预。",
                relative_path="THUOCL/THUOCL_chengyu.txt",
                enabled=False,
                tags=["builtin", "upstream", "zh", "THUOCL", "chengyu"],
            ),
        ],
        "synonym_map": [
            _table_spec(
                kind="synonym_map",
                table_id="builtin-opencc-twphrasesrev-single",
                name="同义归并 · 繁体到简体口径（OpenCC 单目标）",
                rows=opencc_twphrases_single,
                description="OpenCC TWPhrasesRev 单目标映射快照，用于把繁体/地区写法归并到简体主写法。",
                relative_path="OpenCC/TWPhrasesRev.txt",
                enabled=True,
                tags=["builtin", "upstream", "zh", "OpenCC", "single-target"],
            ),
        ],
        "near_synonym_map": [
            _table_spec(
                kind="near_synonym_map",
                table_id="builtin-opencc-twphrasesrev-multi",
                name="近义归并 · 繁体多候选（OpenCC 多目标）",
                rows=opencc_twphrases_multi,
                description="OpenCC TWPhrasesRev 多目标映射快照。当前引擎仍是一对一替换，因此暂存首个候选目标并默认关闭。",
                relative_path="OpenCC/TWPhrasesRev.txt",
                enabled=False,
                tags=["builtin", "upstream", "zh", "OpenCC", "multi-target"],
            ),
        ],
        "standard_terms": [
            _table_spec(
                kind="standard_terms",
                table_id="builtin-opencc-tsphrases",
                name="标准词库 · 繁体转简体（OpenCC）",
                rows=opencc_tsphrases,
                description="OpenCC TSPhrases 完整快照。若某行存在多个上游候选，当前版本按首个候选标准化。",
                relative_path="OpenCC/TSPhrases.txt",
                enabled=True,
                tags=["builtin", "upstream", "zh", "OpenCC", "t2s"],
            ),
            _table_spec(
                kind="standard_terms",
                table_id="builtin-misspell-main",
                name="标准词库 · 英文拼写纠正（misspell Main）",
                rows=misspell["DictMain"],
                description="client9/misspell 主词表完整快照，用于常见英文拼写纠正。",
                relative_path="misspell/words.go",
                enabled=True,
                tags=["builtin", "upstream", "en", "misspell", "main"],
            ),
            _table_spec(
                kind="standard_terms",
                table_id="builtin-misspell-american",
                name="标准词库 · 美式拼写归一（misspell American）",
                rows=misspell["DictAmerican"],
                description="client9/misspell 美式词形映射快照。默认关闭，按需启用。",
                relative_path="misspell/words.go",
                enabled=False,
                tags=["builtin", "upstream", "en", "misspell", "american"],
            ),
            _table_spec(
                kind="standard_terms",
                table_id="builtin-misspell-british",
                name="标准词库 · 英式拼写归一（misspell British）",
                rows=misspell["DictBritish"],
                description="client9/misspell 英式词形映射快照。默认关闭，按需启用。",
                relative_path="misspell/words.go",
                enabled=False,
                tags=["builtin", "upstream", "en", "misspell", "british"],
            ),
        ],
        "exclusion_terms": [
            _table_spec(
                kind="exclusion_terms",
                table_id="builtin-thuocl-historical",
                name="排除词表 · 历史名人（THUOCL）",
                rows=thuocl_historical,
                description="THUOCL 历史名人词表完整快照。默认关闭，适合对当前课题无关的人名批量排除。",
                relative_path="THUOCL/THUOCL_lishimingren.txt",
                enabled=False,
                tags=["builtin", "upstream", "zh", "THUOCL", "historical"],
            ),
            _table_spec(
                kind="exclusion_terms",
                table_id="builtin-thuocl-locations",
                name="排除词表 · 地名（THUOCL）",
                rows=thuocl_locations,
                description="THUOCL 地名词表完整快照。默认关闭，适合在非地理课题中批量排除地名噪声。",
                relative_path="THUOCL/THUOCL_diming.txt",
                enabled=False,
                tags=["builtin", "upstream", "zh", "THUOCL", "locations"],
            ),
        ],
        "regex_rules": [],
    }


@lru_cache(maxsize=1)
def builtin_stopword_terms() -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for spec in builtin_dictionary_table_specs().get("stopwords", []):
        for source, _target, _hits, _entry_id in spec.get("rows", []):
            key = source.casefold()
            if key in seen:
                continue
            seen.add(key)
            terms.append(source)
    return terms
