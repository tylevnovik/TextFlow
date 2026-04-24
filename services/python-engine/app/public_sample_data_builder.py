from __future__ import annotations

import argparse
import bz2
import io
import json
import os
import re
import tarfile
import time
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Iterator, Sequence
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .sample_dataset_cache import normalized_cache_path, sample_data_cache_root, write_normalized_sample_cache
from .sample_dataset_sources import PUBLIC_SAMPLE_DATA_SOURCE_BY_ID, normalize_public_sample_row

PUBLIC_SAMPLE_CACHE_SCHEMA_VERSION = 2
PUBLIC_SAMPLE_RAW_ROOT_ENV_VAR = "TEXTFLOW_PUBLIC_SAMPLE_RAW_ROOT"
HTTP_TIMEOUT_SECONDS = 120
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2.0
USER_AGENT = "TextFlow public sample cache builder/0.1"
OPENALEX_WORKS_URL = "https://api.openalex.org/works"
UN_TESTSETS_URL = "https://www.un.org/dgacm/sites/www.un.org.dgacm/files/files/UNCORPUS/UNv1.0.testsets.tar.gz"
UN_TEI_ARCHIVE_BY_LANGUAGE = {
    "en": "https://www.un.org/dgacm/sites/www.un.org.dgacm/files/files/UNCORPUS/UNv1.0-TEI.en.tar.gz.00",
    "zh": "https://www.un.org/dgacm/sites/www.un.org.dgacm/files/files/UNCORPUS/UNv1.0-TEI.zh.tar.gz.00",
}
WIKIMEDIA_API_BY_DATASET = {
    "wikimedia_enwiki": ("https://en.wikipedia.org/w/api.php", "en"),
    "wikimedia_zhwiki": ("https://zh.wikipedia.org/w/api.php", "zh"),
}
WIKIMEDIA_LOCAL_DUMP_FILENAME_BY_DATASET = {
    "wikimedia_enwiki": "enwiki-latest-pages-articles-multistream1.xml-p1p41242.bz2",
    "wikimedia_zhwiki": "zhwiki-latest-pages-articles-multistream1.xml-p1p187712.bz2",
}
UN_TESTSETS_LOCAL_FILENAME = "UNv1.0.testsets.tar.gz"
UN_TEI_LOCAL_FILENAME_BY_LANGUAGE = {
    "en": "UNv1.0-TEI.en.tar.gz.00",
    "zh": "UNv1.0-TEI.zh.tar.gz.00",
}
MEDIAWIKI_XML_NAMESPACE = "{http://www.mediawiki.org/xml/export-0.11/}"
WIKIMEDIA_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
WIKIMEDIA_REF_RE = re.compile(r"<ref\b[^>/]*>.*?</ref>|<ref\b[^>]*/>", re.DOTALL | re.IGNORECASE)
WIKIMEDIA_TABLE_RE = re.compile(r"\{\|.*?\|\}", re.DOTALL)
WIKIMEDIA_TEMPLATE_RE = re.compile(r"\{\{[^{}]*\}\}", re.DOTALL)
WIKIMEDIA_FILE_RE = re.compile(r"\[\[(?:File|Image|Category|文件|檔案|分类|分類):[^\]]+\]\]", re.IGNORECASE)
WIKIMEDIA_EXTERNAL_LINK_RE = re.compile(r"\[(https?://[^\s\]]+)\s+([^\]]+)\]")
WIKIMEDIA_BARE_EXTERNAL_LINK_RE = re.compile(r"\[(https?://[^\]]+)\]")
WIKIMEDIA_PIPED_LINK_RE = re.compile(r"\[\[[^\]|]+\|([^\]]+)\]\]")
WIKIMEDIA_SIMPLE_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
WIKIMEDIA_HEADING_RE = re.compile(r"={2,}\s*(.*?)\s*={2,}")
WIKIMEDIA_TAG_RE = re.compile(r"<[^>]+>")
WIKIMEDIA_APOSTROPHE_RE = re.compile(r"'{2,}")
WIKIMEDIA_WHITESPACE_RE = re.compile(r"\s+")


def reconstruct_openalex_abstract(abstract_inverted_index: dict[str, list[int]] | None) -> str:
    if not abstract_inverted_index:
        return ""
    last_position = -1
    for positions in abstract_inverted_index.values():
        if positions:
            last_position = max(last_position, max(positions))
    if last_position < 0:
        return ""

    words = [""] * (last_position + 1)
    for token, positions in abstract_inverted_index.items():
        for position in positions:
            if 0 <= position < len(words):
                words[position] = token
    return " ".join(word for word in words if word).strip()


def public_sample_raw_root() -> Path:
    configured_root = os.getenv(PUBLIC_SAMPLE_RAW_ROOT_ENV_VAR)
    if configured_root:
        return Path(configured_root)
    return Path(__file__).resolve().parent.parent / ".cache" / "public-source-raw"


def raw_public_source_path(filename: str) -> Path:
    return public_sample_raw_root() / filename


def normalize_wikimedia_page(dataset_id: str, page: dict[str, Any]) -> dict[str, Any] | None:
    language = WIKIMEDIA_API_BY_DATASET[dataset_id][1]
    title = str(page.get("title") or "").strip()
    raw_text = str(page.get("extract") or "").strip()
    if not title or len(raw_text) < 240:
        return None

    touched = str(page.get("touched") or "")
    year = None
    if len(touched) >= 4 and touched[:4].isdigit():
        year = int(touched[:4])

    page_id = str(page.get("pageid") or title)
    source_url = str(page.get("canonicalurl") or page.get("fullurl") or "").strip() or None

    return normalize_public_sample_row(
        {
            "doc_id": f"{dataset_id}-{page_id}",
            "title": title,
            "raw_text": raw_text,
            "year": year,
            "source": "Wikipedia",
            "sample_origin": "real_public_data",
        },
        dataset_id=dataset_id,
        language=language,
        source_record_id=page_id,
        source_url=source_url,
        source_profile="generic",
    )


def strip_wikimedia_markup(raw_text: str) -> str:
    text = raw_text
    text = WIKIMEDIA_COMMENT_RE.sub(" ", text)
    text = WIKIMEDIA_REF_RE.sub(" ", text)
    text = WIKIMEDIA_TABLE_RE.sub(" ", text)
    for _ in range(4):
        next_text = WIKIMEDIA_TEMPLATE_RE.sub(" ", text)
        if next_text == text:
            break
        text = next_text
    text = WIKIMEDIA_FILE_RE.sub(" ", text)
    text = WIKIMEDIA_EXTERNAL_LINK_RE.sub(r"\2", text)
    text = WIKIMEDIA_BARE_EXTERNAL_LINK_RE.sub(" ", text)
    text = WIKIMEDIA_PIPED_LINK_RE.sub(r"\1", text)
    text = WIKIMEDIA_SIMPLE_LINK_RE.sub(r"\1", text)
    text = WIKIMEDIA_HEADING_RE.sub(r"\1", text)
    text = WIKIMEDIA_TAG_RE.sub(" ", text)
    text = WIKIMEDIA_APOSTROPHE_RE.sub("", text)
    return WIKIMEDIA_WHITESPACE_RE.sub(" ", text).strip()


def normalize_wikimedia_dump_page(dataset_id: str, page: dict[str, Any]) -> dict[str, Any] | None:
    language = WIKIMEDIA_API_BY_DATASET[dataset_id][1]
    title = str(page.get("title") or "").strip()
    if not title or _is_probably_disambiguation_page(title):
        return None

    page_id = str(page.get("pageid") or "").strip()
    raw_markup = str(page.get("raw_text") or "").strip()
    raw_text = strip_wikimedia_markup(raw_markup)
    if not page_id or len(raw_text) < 240:
        return None

    timestamp = str(page.get("timestamp") or "").strip()
    year = _parse_year_text(timestamp)
    source_url = f"https://{language}.wikipedia.org/wiki/{title.replace(' ', '_')}"
    return normalize_public_sample_row(
        {
            "doc_id": f"{dataset_id}-{page_id}",
            "title": title,
            "raw_text": raw_text,
            "year": year,
            "source": "Wikipedia",
            "sample_origin": "real_public_data",
        },
        dataset_id=dataset_id,
        language=language,
        source_record_id=page_id,
        source_url=source_url,
        source_profile="generic",
    )


def parse_un_tei_document(xml_payload: str) -> dict[str, Any] | None:
    try:
        root = ET.fromstring(xml_payload)
    except ET.ParseError:
        return None

    title = _text_at(root, ".//titleStmt/title")
    symbol = _find_idno(root, "symbol") or _find_idno(root, "jobno")
    publisher = _text_at(root, ".//publicationStmt/publisher")
    date_text = _text_at(root, ".//publicationStmt/date")
    year = _parse_year_text(date_text)
    sentences = [_clean_text("".join(element.itertext())) for element in root.findall(".//body//s")]
    raw_text = "\n".join(sentence for sentence in sentences if sentence).strip()
    if len(raw_text) < 240:
        return None

    return {
        "title": title or symbol or "UN document",
        "raw_text": raw_text,
        "year": year,
        "source": publisher or "United Nations",
        "source_record_id": symbol,
    }


def build_public_sample_cache(
    dataset_ids: Sequence[str],
    *,
    languages: Sequence[str],
    limit_per_language: int,
    cache_root: Path | None = None,
    force_refresh: bool = False,
) -> Path:
    if not dataset_ids:
        raise ValueError("At least one dataset id is required")
    if limit_per_language < 1:
        raise ValueError("limit_per_language must be positive")

    cache_root = cache_root or sample_data_cache_root()
    requested_languages = tuple(dict.fromkeys(language for language in languages if language in {"en", "zh"}))
    if not requested_languages:
        raise ValueError("At least one supported language is required")

    existing_manifest = _load_manifest(cache_root)
    dataset_entries: list[dict[str, Any]] = []

    for dataset_id in dataset_ids:
        source = PUBLIC_SAMPLE_DATA_SOURCE_BY_ID.get(dataset_id)
        if source is None:
            raise ValueError(f"Unknown public dataset id: {dataset_id}")

        dataset_languages = tuple(language for language in requested_languages if language in source.languages)
        if not dataset_languages:
            raise ValueError(f"Dataset {dataset_id} does not support requested languages: {requested_languages}")

        if force_refresh or not _cache_meets_requirements(
            cache_root,
            dataset_id=dataset_id,
            dataset_languages=dataset_languages,
            limit_per_language=limit_per_language,
            manifest=existing_manifest,
        ):
            rows = _build_rows_for_dataset(dataset_id, dataset_languages, limit_per_language)
            write_normalized_sample_cache(cache_root, dataset_id, rows)

        dataset_entries.append(_manifest_entry(cache_root, dataset_id, dataset_languages))

    manifest = {
        "cache_schema_version": PUBLIC_SAMPLE_CACHE_SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "limit_per_language": limit_per_language,
        "builder": "real_public_data",
        "datasets": dataset_entries,
    }
    manifest_path = cache_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build real public-data cache files for TextFlow sample projects.")
    parser.add_argument("--dataset", action="append", dest="datasets", default=[])
    parser.add_argument("--language", action="append", dest="languages", default=[])
    parser.add_argument("--limit-per-language", type=int, default=10_000)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--force-refresh", action="store_true")
    args = parser.parse_args(argv)

    datasets = list(args.datasets)
    if args.all:
        datasets = [
            "un_parallel_en_zh",
            "wikimedia_enwiki",
            "wikimedia_zhwiki",
            "openalex_works",
        ]
    if not datasets:
        parser.error("Specify --dataset or use --all")

    languages = args.languages or ["en", "zh"]
    manifest_path = build_public_sample_cache(
        datasets,
        languages=languages,
        limit_per_language=args.limit_per_language,
        force_refresh=args.force_refresh,
    )
    print(manifest_path)
    return 0


def _build_rows_for_dataset(dataset_id: str, dataset_languages: Sequence[str], limit_per_language: int) -> list[dict[str, Any]]:
    if dataset_id in WIKIMEDIA_API_BY_DATASET:
        rows: list[dict[str, Any]] = []
        for language in dataset_languages:
            rows.extend(_build_wikimedia_rows(dataset_id, language, limit_per_language))
        return rows
    if dataset_id == "openalex_works":
        rows = []
        for language in dataset_languages:
            rows.extend(_build_openalex_rows(language, limit_per_language))
        return rows
    if dataset_id == "un_parallel_en_zh":
        rows = []
        for language in dataset_languages:
            rows.extend(_build_un_rows(language, limit_per_language))
        return rows
    raise ValueError(f"No public sample data builder for dataset: {dataset_id}")


def _build_wikimedia_rows(dataset_id: str, language: str, limit_per_language: int) -> list[dict[str, Any]]:
    api_url, dataset_language = WIKIMEDIA_API_BY_DATASET[dataset_id]
    if language != dataset_language:
        raise ValueError(f"Dataset {dataset_id} does not support language {language}")

    local_dump = raw_public_source_path(WIKIMEDIA_LOCAL_DUMP_FILENAME_BY_DATASET[dataset_id])
    if local_dump.exists():
        rows = _load_wikimedia_dump_rows(local_dump, dataset_id, limit_per_language)
        if len(rows) < limit_per_language:
            raise ValueError(
                f"Not enough real Wikimedia rows in local dump for dataset={dataset_id} language={language}: "
                f"requested={limit_per_language} available={len(rows)}"
            )
        return rows

    rows: list[dict[str, Any]] = []
    apcontinue: str | None = None
    while len(rows) < limit_per_language:
        params = {
            "action": "query",
            "format": "json",
            "list": "allpages",
            "apnamespace": "0",
            "aplimit": "max",
        }
        if apcontinue:
            params["apcontinue"] = apcontinue
        listing = _fetch_json(api_url, params)
        page_ids = [str(item["pageid"]) for item in listing.get("query", {}).get("allpages", []) if item.get("pageid")]
        if not page_ids:
            break
        for chunk in _chunked(page_ids, 50):
            detail = _fetch_json(
                api_url,
                {
                    "action": "query",
                    "format": "json",
                    "prop": "extracts|info",
                    "pageids": "|".join(chunk),
                    "inprop": "url",
                    "explaintext": "1",
                },
            )
            pages = detail.get("query", {}).get("pages", {})
            for page in sorted(pages.values(), key=lambda item: str(item.get("title") or "")):
                row = normalize_wikimedia_page(dataset_id, page)
                if row is None:
                    continue
                rows.append(row)
                if len(rows) >= limit_per_language:
                    break
            if len(rows) >= limit_per_language:
                break
        apcontinue = listing.get("continue", {}).get("apcontinue")
        if not apcontinue:
            break

    if len(rows) < limit_per_language:
        raise ValueError(
            f"Not enough real Wikimedia rows for dataset={dataset_id} language={language}: "
            f"requested={limit_per_language} available={len(rows)}"
        )
    return rows


def _build_openalex_rows(language: str, limit_per_language: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cursor = "*"
    today = date.today().isoformat()
    while len(rows) < limit_per_language and cursor:
        payload = _fetch_json(
            OPENALEX_WORKS_URL,
            {
                "filter": (
                    f"language:{language},has_abstract:true,"
                    f"from_publication_date:2015-01-01,to_publication_date:{today}"
                ),
                "per-page": "200",
                "cursor": cursor,
            },
        )
        cursor = payload.get("meta", {}).get("next_cursor")
        for work in payload.get("results", []):
            abstract = reconstruct_openalex_abstract(work.get("abstract_inverted_index"))
            if len(abstract) < 120:
                continue
            work_id = str(work.get("id") or "").strip()
            source_record_id = work_id.rsplit("/", 1)[-1] if work_id else None
            source_url = work_id or (
                ((work.get("primary_location") or {}).get("landing_page_url"))
                or ((work.get("primary_location") or {}).get("source") or {}).get("host_organization_lineage")
            )
            institution = _first_openalex_institution(work)
            country = _first_openalex_country(work)
            topic = _first_openalex_topic(work)
            keywords = _openalex_keywords(work)
            row = normalize_public_sample_row(
                {
                    "doc_id": source_record_id or f"openalex-{language}-{len(rows)}",
                    "title": str(work.get("display_name") or work.get("title") or source_record_id or "OpenAlex work"),
                    "raw_text": abstract,
                    "year": work.get("publication_year"),
                    "source": _openalex_source_name(work),
                    "institution": institution,
                    "country_or_region": country,
                    "category_or_tag": topic,
                    "keyword_field": keywords,
                    "sample_origin": "real_public_data",
                },
                dataset_id="openalex_works",
                language=language,
                source_record_id=source_record_id,
                source_url=str(source_url or OPENALEX_WORKS_URL),
                source_profile="literature",
            )
            rows.append(row)
            if len(rows) >= limit_per_language:
                break
        if not payload.get("results"):
            break

    if len(rows) < limit_per_language:
        raise ValueError(
            f"Not enough real OpenAlex rows for language={language}: requested={limit_per_language} available={len(rows)}"
        )
    return rows


def _build_un_rows(language: str, limit_per_language: int) -> list[dict[str, Any]]:
    rows = _load_un_test_rows(language)
    if len(rows) >= limit_per_language:
        return rows[:limit_per_language]

    needed = limit_per_language - len(rows)
    rows.extend(_load_un_tei_rows(language, needed))
    if len(rows) < limit_per_language:
        raise ValueError(
            f"Not enough real UN corpus rows for language={language}: requested={limit_per_language} available={len(rows)}"
        )
    return rows[:limit_per_language]


def _load_un_test_rows(language: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    local_path = raw_public_source_path(UN_TESTSETS_LOCAL_FILENAME)
    if local_path.exists():
        archive_context = tarfile.open(local_path, mode="r:gz")
    else:
        buffer = io.BytesIO(_fetch_bytes(UN_TESTSETS_URL))
        archive_context = tarfile.open(fileobj=buffer, mode="r:gz")
    with archive_context as archive:
        split_defs = [
            ("testset", f"testsets/testset/UNv1.0.testset.{language}", "testsets/testset/UNv1.0.testset.ids"),
            ("devset", f"testsets/devset/UNv1.0.devset.{language}", "testsets/devset/UNv1.0.devset.ids"),
        ]
        for split_name, text_member_name, id_member_name in split_defs:
            text_lines = _read_tar_lines(archive, text_member_name)
            id_lines = _read_tar_lines(archive, id_member_name)
            for text_value, id_value in zip(text_lines, id_lines, strict=True):
                raw_text = text_value.strip()
                if len(raw_text) < 20:
                    continue
                source_record_id = str(id_value.split()[0]).strip()
                rows.append(
                    normalize_public_sample_row(
                        {
                            "doc_id": f"un-{split_name}-{source_record_id}",
                            "title": source_record_id,
                            "raw_text": raw_text,
                            "year": _parse_year_text(source_record_id),
                            "source": "United Nations",
                            "sample_origin": "real_public_data",
                        },
                        dataset_id="un_parallel_en_zh",
                        language=language,
                        source_record_id=source_record_id,
                        source_url=UN_TESTSETS_URL,
                        source_profile="generic",
                    )
                )
    return rows


def _load_un_tei_rows(language: str, limit: int) -> list[dict[str, Any]]:
    if limit <= 0:
        return []

    rows: list[dict[str, Any]] = []
    url = UN_TEI_ARCHIVE_BY_LANGUAGE[language]
    local_path = raw_public_source_path(UN_TEI_LOCAL_FILENAME_BY_LANGUAGE[language])
    if local_path.exists():
        archive_context = tarfile.open(local_path, mode="r:gz")
    else:
        request = Request(url, headers={"User-Agent": USER_AGENT})
        archive_context = tarfile.open(fileobj=_open_with_retries(request), mode="r|gz")
    with archive_context as archive:
        for member in archive:
            if not member.isfile() or not member.name.endswith(".xml"):
                continue
            fileobj = archive.extractfile(member)
            if fileobj is None:
                continue
            parsed = parse_un_tei_document(fileobj.read().decode("utf-8", errors="replace"))
            if parsed is None:
                continue
            source_record_id = str(parsed.get("source_record_id") or member.name)
            rows.append(
                normalize_public_sample_row(
                    {
                        "doc_id": f"un-tei-{language}-{source_record_id.replace('/', '_')}",
                        "title": parsed["title"],
                        "raw_text": parsed["raw_text"],
                        "year": parsed.get("year"),
                        "source": parsed.get("source"),
                        "sample_origin": "real_public_data",
                    },
                    dataset_id="un_parallel_en_zh",
                    language=language,
                    source_record_id=source_record_id,
                    source_url=url,
                    source_profile="generic",
                )
            )
            if len(rows) >= limit:
                break
    return rows


def _load_wikimedia_dump_rows(path: Path, dataset_id: str, limit_per_language: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with bz2.open(path, "rb") as handle:
        context = ET.iterparse(handle, events=("end",))
        for _event, element in context:
            if element.tag != f"{MEDIAWIKI_XML_NAMESPACE}page":
                continue
            page = _parse_wikimedia_page_element(element)
            element.clear()
            if page is None:
                continue
            row = normalize_wikimedia_dump_page(dataset_id, page)
            if row is None:
                continue
            rows.append(row)
            if len(rows) >= limit_per_language:
                break
    return rows


def _parse_wikimedia_page_element(element: ET.Element) -> dict[str, Any] | None:
    namespace = MEDIAWIKI_XML_NAMESPACE
    if (element.findtext(f"{namespace}ns") or "").strip() != "0":
        return None
    if element.find(f"{namespace}redirect") is not None:
        return None

    revision = element.find(f"{namespace}revision")
    if revision is None:
        return None
    text_value = revision.findtext(f"{namespace}text") or ""
    if not text_value.strip():
        return None

    return {
        "pageid": (element.findtext(f"{namespace}id") or "").strip(),
        "title": (element.findtext(f"{namespace}title") or "").strip(),
        "timestamp": (revision.findtext(f"{namespace}timestamp") or "").strip(),
        "raw_text": text_value,
    }


def _manifest_entry(cache_root: Path, dataset_id: str, dataset_languages: Sequence[str]) -> dict[str, Any]:
    source = PUBLIC_SAMPLE_DATA_SOURCE_BY_ID[dataset_id]
    cache_path = normalized_cache_path(cache_root, dataset_id)
    counts = _count_rows_by_language(cache_path)
    return {
        "dataset_id": dataset_id,
        "name": source.name,
        "homepage_url": source.homepage_url,
        "download_url": source.download_url,
        "license_name": source.license_name,
        "public_access_note": source.public_access_note,
        "redistribution_note": source.redistribution_note,
        "row_count_by_language": {language: counts.get(language, 0) for language in sorted(set(dataset_languages))},
        "sha256": _sha256(cache_path),
        "cache_file": cache_path.name,
        "sample_origin": "real_public_data",
    }


def _load_manifest(cache_root: Path) -> dict[str, Any] | None:
    manifest_path = cache_root / "manifest.json"
    if not manifest_path.exists():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _cache_meets_requirements(
    cache_root: Path,
    *,
    dataset_id: str,
    dataset_languages: Sequence[str],
    limit_per_language: int,
    manifest: dict[str, Any] | None,
) -> bool:
    cache_path = normalized_cache_path(cache_root, dataset_id)
    if not cache_path.exists():
        return False
    if not manifest or manifest.get("cache_schema_version") != PUBLIC_SAMPLE_CACHE_SCHEMA_VERSION:
        return False

    entries = manifest.get("datasets")
    if not isinstance(entries, list):
        return False
    entry = next((item for item in entries if isinstance(item, dict) and item.get("dataset_id") == dataset_id), None)
    if entry and entry.get("sample_origin") == "real_public_data":
        counts = entry.get("row_count_by_language")
        if isinstance(counts, dict) and all(int(counts.get(language, 0) or 0) >= limit_per_language for language in dataset_languages):
            return True

    return _cache_file_meets_requirements(cache_path, dataset_languages, limit_per_language)


def _fetch_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    query = urlencode(params, doseq=True)
    request = Request(f"{url}?{query}", headers={"User-Agent": USER_AGENT})
    with _open_with_retries(request) as response:
        return json.load(response)


def _fetch_bytes(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with _open_with_retries(request) as response:
        return response.read()


def _open_with_retries(request: Request):
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return urlopen(request, timeout=HTTP_TIMEOUT_SECONDS)
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = exc
            if attempt == MAX_RETRIES:
                break
            time.sleep(RETRY_DELAY_SECONDS * attempt)
    assert last_error is not None
    raise last_error


def _chunked(items: Sequence[str], size: int) -> Iterator[list[str]]:
    for index in range(0, len(items), size):
        yield list(items[index:index + size])


def _read_tar_lines(archive: tarfile.TarFile, member_name: str) -> list[str]:
    member = archive.getmember(member_name)
    extracted = archive.extractfile(member)
    if extracted is None:
        return []
    return extracted.read().decode("utf-8", errors="replace").splitlines()


def _count_rows_by_language(cache_path: Path) -> dict[str, int]:
    import gzip

    counts: dict[str, int] = {}
    with gzip.open(cache_path, "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            language = str(row.get("language") or "")
            counts[language] = counts.get(language, 0) + 1
    return counts


def _cache_file_meets_requirements(cache_path: Path, dataset_languages: Sequence[str], limit_per_language: int) -> bool:
    import gzip

    counts = {language: 0 for language in dataset_languages}
    saw_real_origin = False
    with gzip.open(cache_path, "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            extra_metadata = row.get("extra_metadata") if isinstance(row.get("extra_metadata"), dict) else {}
            if extra_metadata.get("sample_origin") == "real_public_data":
                saw_real_origin = True
            language = str(row.get("language") or "")
            if language in counts:
                counts[language] += 1
    return saw_real_origin and all(counts.get(language, 0) >= limit_per_language for language in dataset_languages)


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _text_at(root: ET.Element, path: str) -> str:
    element = root.find(path)
    if element is None:
        return ""
    return _clean_text("".join(element.itertext()))


def _find_idno(root: ET.Element, id_type: str) -> str:
    for element in root.findall(".//idno"):
        if element.attrib.get("type") == id_type:
            return _clean_text("".join(element.itertext()))
    return ""


def _clean_text(value: str) -> str:
    return " ".join(value.split()).strip()


def _is_probably_disambiguation_page(title: str) -> bool:
    lowered = title.lower()
    return (
        lowered.endswith("(disambiguation)")
        or lowered.endswith("(disambiguation page)")
        or "消歧义" in title
        or "消歧義" in title
    )


def _parse_year_text(value: Any) -> int | None:
    text = str(value or "")
    digits = "".join(character for character in text if character.isdigit())
    if len(digits) < 4:
        return None
    year = int(digits[:4])
    if 1800 <= year <= 2100:
        return year
    return None


def _first_openalex_institution(work: dict[str, Any]) -> str | None:
    for authorship in work.get("authorships") or []:
        for institution in authorship.get("institutions") or []:
            name = str(institution.get("display_name") or "").strip()
            if name:
                return name
    for institution in work.get("institutions") or []:
        name = str(institution.get("display_name") or "").strip()
        if name:
            return name
    return None


def _first_openalex_country(work: dict[str, Any]) -> str | None:
    for authorship in work.get("authorships") or []:
        for institution in authorship.get("institutions") or []:
            country = str(institution.get("country_code") or "").strip()
            if country:
                return country
    return None


def _first_openalex_topic(work: dict[str, Any]) -> str | None:
    primary_topic = work.get("primary_topic") or {}
    display_name = str(primary_topic.get("display_name") or "").strip()
    if display_name:
        return display_name
    for topic in work.get("topics") or []:
        display_name = str(topic.get("display_name") or "").strip()
        if display_name:
            return display_name
    return None


def _openalex_keywords(work: dict[str, Any]) -> str | None:
    values: list[str] = []
    for keyword in work.get("keywords") or []:
        name = str(keyword.get("display_name") or "").strip()
        if name:
            values.append(name)
    if not values:
        for topic in work.get("topics") or []:
            name = str(topic.get("display_name") or "").strip()
            if name:
                values.append(name)
    if not values:
        for concept in work.get("concepts") or []:
            name = str(concept.get("display_name") or "").strip()
            if name:
                values.append(name)
            if len(values) >= 8:
                break
    if not values:
        return None
    return "; ".join(values[:8])


def _openalex_source_name(work: dict[str, Any]) -> str:
    primary_location = work.get("primary_location") or {}
    source = primary_location.get("source") or {}
    display_name = str(source.get("display_name") or "").strip()
    if display_name:
        return display_name
    raw_source_name = str(primary_location.get("raw_source_name") or "").strip()
    if raw_source_name:
        return raw_source_name
    return "OpenAlex"


if __name__ == "__main__":
    raise SystemExit(main())
