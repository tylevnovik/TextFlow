from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .ingestion import parse_optional_year


@dataclass(frozen=True)
class PublicSampleDataSource:
    source_id: str
    name: str
    homepage_url: str
    download_url: str | None
    languages: tuple[str, ...]
    license_name: str
    public_access_note: str
    redistribution_note: str
    citation: str


PUBLIC_SAMPLE_DATA_SOURCES = [
    PublicSampleDataSource(
        source_id="un_parallel_en_zh",
        name="United Nations Parallel Corpus v1.0",
        homepage_url="https://www.un.org/dgacm/en/node/5471",
        download_url="https://www.un.org/dgacm/en/content/uncorpus/download",
        languages=("en", "zh"),
        license_name="Public domain UN official records and parliamentary documents",
        public_access_note="UN describes the corpus as public-domain official records and other parliamentary documents.",
        redistribution_note="Package normalized subsets with source attribution, language metadata, and source record identifiers where available.",
        citation="United Nations Parallel Corpus v1.0.",
    ),
    PublicSampleDataSource(
        source_id="wikimedia_enwiki",
        name="English Wikipedia article dump",
        homepage_url="https://dumps.wikimedia.org/enwiki/latest/",
        download_url="https://dumps.wikimedia.org/enwiki/latest/",
        languages=("en",),
        license_name="CC BY-SA 4.0 and GFDL",
        public_access_note="Wikimedia publishes reusable text dumps with attribution and share-alike obligations.",
        redistribution_note="Persist article-derived subsets with page/source attribution and retain license metadata in the cache manifest.",
        citation="Wikimedia Dumps: English Wikipedia latest text dump.",
    ),
    PublicSampleDataSource(
        source_id="wikimedia_zhwiki",
        name="Chinese Wikipedia article dump",
        homepage_url="https://dumps.wikimedia.org/zhwiki/latest/",
        download_url="https://dumps.wikimedia.org/zhwiki/latest/",
        languages=("zh",),
        license_name="CC BY-SA 4.0 and GFDL",
        public_access_note="Wikimedia publishes reusable text dumps with attribution and share-alike obligations.",
        redistribution_note="Persist article-derived subsets with page/source attribution and retain license metadata in the cache manifest.",
        citation="Wikimedia Dumps: Chinese Wikipedia latest text dump.",
    ),
    PublicSampleDataSource(
        source_id="openalex_works",
        name="OpenAlex Works",
        homepage_url="https://developers.openalex.org/",
        download_url="https://docs.openalex.org/download-all-data/openalex-snapshot",
        languages=("en", "zh"),
        license_name="CC0 1.0 / No Rights Reserved",
        public_access_note="OpenAlex documents the dataset as free to use under CC0.",
        redistribution_note="Store normalized work records with OpenAlex identifiers, language metadata, and source URLs.",
        citation="OpenAlex Works dataset.",
    ),
    PublicSampleDataSource(
        source_id="cfpb_complaints_optional",
        name="CFPB Consumer Complaint Database",
        homepage_url="https://www.consumerfinance.gov/data-research/consumer-complaints/",
        download_url="https://www.consumerfinance.gov/data-research/consumer-complaints/#download-the-data",
        languages=("en",),
        license_name="Publicly available U.S. government complaint data",
        public_access_note="CFPB states the published complaint data is free to use, analyze, and build on.",
        redistribution_note="Use only as matched optional enrichment and preserve complaint identifiers plus CFPB attribution in manifests.",
        citation="CFPB Consumer Complaint Database.",
    ),
    PublicSampleDataSource(
        source_id="patentsview_optional",
        name="USPTO PatentsView",
        homepage_url="https://www.uspto.gov/ip-policy/economic-research/patentsview",
        download_url="https://patentsview.org/downloads/data-downloads",
        languages=("en",),
        license_name="Public U.S. patent data resource",
        public_access_note="USPTO describes PatentsView as a public research-grade patent data resource.",
        redistribution_note="Use only as matched optional enrichment and preserve patent identifiers plus USPTO attribution in manifests.",
        citation="USPTO PatentsView data downloads.",
    ),
    PublicSampleDataSource(
        source_id="20_newsgroups_optional",
        name="20 Newsgroups",
        homepage_url="https://kdd.ics.uci.edu/databases/20newsgroups/20newsgroups.html",
        download_url="https://kdd.ics.uci.edu/databases/20newsgroups/20newsgroups.html",
        languages=("en",),
        license_name="Public research dataset hosted by UCI KDD",
        public_access_note="The dataset is publicly hosted for research use and must be reviewed before redistribution as a bundled default source.",
        redistribution_note="Only use as an optional substitute after documenting redistribution review in the generated manifest.",
        citation="UCI KDD 20 Newsgroups dataset.",
    ),
]

PUBLIC_SAMPLE_DATA_SOURCE_BY_ID = {
    source.source_id: source for source in PUBLIC_SAMPLE_DATA_SOURCES
}

SUPPORTED_SAMPLE_LANGUAGES = {"en", "zh"}

REQUIRED_SAMPLE_ROW_FIELDS = {
    "doc_id",
    "language",
    "title",
    "raw_text",
    "year",
    "source",
    "institution",
    "category_or_tag",
    "keyword_field",
}


def source_supports_language(dataset_id: str, language: str) -> bool:
    source = PUBLIC_SAMPLE_DATA_SOURCE_BY_ID.get(dataset_id)
    return bool(source and language in source.languages)


def _default_doc_id(row: dict[str, Any], dataset_id: str) -> str:
    if row.get("doc_id"):
        return str(row["doc_id"])
    payload = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"{dataset_id}-{hashlib.md5(payload).hexdigest()[:12]}"


def _normalized_extra_metadata(
    row: dict[str, Any],
    *,
    dataset: PublicSampleDataSource,
    source_record_id: str | None,
    source_url: str | None,
) -> dict[str, Any]:
    extra_metadata = dict(row.get("extra_metadata") or {})
    extra_metadata["source_dataset_id"] = dataset.source_id
    extra_metadata["source_url"] = source_url or dataset.homepage_url
    extra_metadata["source_license"] = dataset.license_name
    if source_record_id:
        extra_metadata["source_record_id"] = source_record_id

    for key, value in row.items():
        if key in REQUIRED_SAMPLE_ROW_FIELDS or key in {"extra_metadata", "source_profile"}:
            continue
        extra_metadata.setdefault(key, value)
    return extra_metadata


def normalize_public_sample_row(
    row: dict[str, Any],
    *,
    dataset_id: str,
    language: str,
    source_record_id: str | None = None,
    source_url: str | None = None,
    source_profile: str = "generic",
) -> dict[str, Any]:
    dataset = PUBLIC_SAMPLE_DATA_SOURCE_BY_ID.get(dataset_id)
    if dataset is None:
        raise ValueError(f"Unknown public dataset source: {dataset_id}")
    if language not in SUPPORTED_SAMPLE_LANGUAGES:
        raise ValueError(f"Unsupported language: {language}")
    if not source_supports_language(dataset_id, language):
        raise ValueError(f"Dataset {dataset_id} does not support language {language}")

    raw_text = str(row.get("raw_text") or "").strip()
    if not raw_text:
        raise ValueError("Public sample rows require non-empty raw_text")

    doc_id = _default_doc_id(row, dataset_id)
    extra_metadata = _normalized_extra_metadata(
        row,
        dataset=dataset,
        source_record_id=source_record_id or row.get("source_record_id"),
        source_url=source_url or row.get("source_url"),
    )

    normalized = {
        "id": doc_id,
        "doc_id": doc_id,
        "language": language,
        "title": str(row.get("title") or doc_id),
        "raw_text": raw_text,
        "year": parse_optional_year(row.get("year")),
        "source": row.get("source") or dataset.name,
        "author": row.get("author"),
        "institution": row.get("institution"),
        "country_or_region": row.get("country_or_region"),
        "category_or_tag": row.get("category_or_tag"),
        "keyword_field": row.get("keyword_field"),
        "source_profile": str(source_profile or "generic"),
        "extra_metadata": extra_metadata,
        "clean_text": "",
        "normalized_text": "",
        "tokens": [],
        "phrase_hits": [],
        "filtered_tokens": [],
        "status": "ready",
    }
    normalized["raw_hash"] = hashlib.md5(raw_text.encode("utf-8")).hexdigest()

    for field in REQUIRED_SAMPLE_ROW_FIELDS:
        normalized.setdefault(field, None)

    return normalized
