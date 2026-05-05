from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from .defaults import json_ready, utc_now_iso
from .project_store import data_root, workspace_root

CORE_FIELDS = {
    "doc_id",
    "source_type",
    "title",
    "raw_text",
    "year",
    "source",
    "author",
    "institution",
    "country_or_region",
    "category_or_tag",
    "keyword_field",
    "extra_metadata",
}

SOURCE_PROFILE_VALUES = {
    "generic",
    "literature",
    "wos",
    "scopus",
    "patent",
    "incopat",
    "business_reserved",
}

HEADER_VARIANT_TRANSLATION = str.maketrans({
    "（": "(",
    "）": ")",
    "【": "[",
    "】": "]",
    "｛": "{",
    "｝": "}",
    "：": ":",
    "，": ",",
    "；": ";",
    "　": " ",
    "\u00A0": " ",
})


def stable_payload_hash(payload: Any) -> str:
    encoded = json.dumps(json_ready(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def normalize_lookup_key(value: Any) -> str:
    normalized = str(value).translate(HEADER_VARIANT_TRANSLATION).casefold().strip()
    return re.sub(r"\s+", "", normalized)


def is_missing_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple, dict, set)):
        return False
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def sample_records() -> list[dict[str, Any]]:
    return [
        {
            "doc_id": "DOC-001",
            "title": "生成式 AI 在学术写作支持中的应用边界",
            "abstract": "生成式AI辅助写作正在改变研究流程，但也带来学术规范与引用透明度问题。",
            "year": 2024,
            "source": "Journal of Digital Humanities",
            "author": "Wang; Li",
            "institution": "复旦大学",
            "country_or_region": "CN",
            "category_or_tag": "academic writing",
            "keyword_field": "generative ai; academic writing",
            "source_profile": "literature",
        },
        {
            "doc_id": "DOC-002",
            "title": "Patent intelligence mining for battery supply chains",
            "abstract": "Battery recycling analytics reveals supply chain risks and patent hotspots across East Asia.",
            "year": 2023,
            "source": "WoS",
            "author": "Smith; Tan",
            "institution": "清华大学",
            "country_or_region": "CN",
            "category_or_tag": "battery",
            "keyword_field": "battery recycling; patent intelligence",
            "source_profile": "wos",
        },
        {
            "doc_id": "DOC-003",
            "title": "智能制造语料中的工艺知识抽取",
            "abstract": "面向智能制造的工艺知识抽取，需要结合术语词典、规则治理和机构主题演化分析。",
            "year": 2025,
            "source": "IncoPat",
            "author": "Chen",
            "institution": "上海交通大学",
            "country_or_region": "CN",
            "category_or_tag": "manufacturing",
            "keyword_field": "智能制造; 知识抽取",
            "source_profile": "incopat",
        },
    ]


def ensure_sample_files() -> list[Path]:
    root = data_root()
    csv_path = root / "literature_sample.csv"
    json_path = root / "patent_sample.json"
    txt_path = root / "notes_sample.txt"

    if not csv_path.exists():
        df = pd.DataFrame(sample_records()[:2])
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    if not json_path.exists():
        json_path.write_text(
            json.dumps(sample_records()[2:], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    if not txt_path.exists():
        txt_path.write_text(
            "This standalone txt document captures quick notes about terminology governance and institution-topic change.",
            encoding="utf-8",
        )

    return [csv_path, json_path, txt_path]


def resolve_source_value(
    record: dict[str, Any],
    source_field: str,
    aliases: Iterable[str] | None = None,
) -> tuple[str | None, Any]:
    if not source_field:
        return None, None

    candidates = [source_field, *(aliases or [])]
    casefold_lookup = {str(key).casefold(): key for key in record}
    normalized_lookup = {normalize_lookup_key(key): key for key in record}

    for candidate in candidates:
        candidate_text = str(candidate).strip()
        if not candidate_text:
            continue
        if candidate in record:
            actual_key = candidate
        else:
            actual_key = casefold_lookup.get(candidate_text.casefold()) or normalized_lookup.get(normalize_lookup_key(candidate_text))
        if actual_key is None:
            continue
        value = record[actual_key]
        if is_missing_value(value):
            continue
        return str(actual_key), value

    return None, None


def map_record_fields(import_template: dict[str, Any], record: dict[str, Any]) -> tuple[dict[str, Any], set[str]]:
    mapped: dict[str, Any] = {}
    consumed_fields: set[str] = set()

    for rule in import_template.get("field_mappings", []):
        matched_key, value = resolve_source_value(
            record,
            str(rule.get("source_field", "")),
            rule.get("aliases", []),
        )
        if matched_key is None:
            continue

        consumed_fields.add(matched_key)
        target_field = str(rule.get("target_field", ""))
        if target_field == "extra_metadata":
            extra = mapped.setdefault("extra_metadata", {})
            if isinstance(value, dict):
                extra.update(value)
            else:
                extra[matched_key] = value
            continue

        mapped[target_field] = value

    return mapped, consumed_fields


def resolve_text_build_value(
    field: str,
    record: dict[str, Any],
    mapped_fields: dict[str, Any] | None = None,
    field_mappings: Iterable[dict[str, Any]] | None = None,
) -> Any:
    matched_key, value = resolve_source_value(record, str(field))
    if matched_key is not None:
        return value

    if not mapped_fields:
        return None

    direct_value = mapped_fields.get(str(field))
    if not is_missing_value(direct_value):
        return direct_value

    return None


def build_raw_text(
    record: dict[str, Any],
    text_build: dict[str, Any],
    mapped_fields: dict[str, Any] | None = None,
    field_mappings: Iterable[dict[str, Any]] | None = None,
) -> str:
    fields = text_build.get("fields") or ["raw_text"]
    values: list[str] = []

    for field in fields:
        value = resolve_text_build_value(str(field), record, mapped_fields, field_mappings)
        if is_missing_value(value):
            if text_build.get("skip_empty", True):
                continue
            values.append("")
            continue
        values.append(str(value))

    delimiter = text_build.get("delimiter", "\n\n")
    return delimiter.join(values).strip()


def dataframe_from_source(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in (".xlsx", ".xls"):
        return pd.read_excel(path)
    if suffix == ".json":
        return pd.read_json(path)
    if suffix == ".txt":
        return pd.DataFrame([{"title": path.stem, "raw_text": path.read_text(encoding="utf-8")}])
    raise ValueError(f"Unsupported source type: {path.suffix}")


def parse_optional_year(value: Any) -> int | None:
    if is_missing_value(value):
        return None
    if isinstance(value, pd.Timestamp):
        return int(value.year)
    if hasattr(value, "year") and isinstance(getattr(value, "year"), int):
        return int(value.year)
    if isinstance(value, str):
        parsed = pd.to_datetime(value, errors="coerce")
        if not pd.isna(parsed):
            return int(parsed.year)
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            parsed = pd.to_datetime(value, errors="coerce")
        except (TypeError, ValueError):
            return None
        if pd.isna(parsed):
            return None
        return int(parsed.year)


def normalize_source_profile(import_template: dict[str, Any], mapped_fields: dict[str, Any]) -> str:
    candidate = str(mapped_fields.get("source_type", import_template.get("source_profile", "generic")) or "generic")
    return candidate if candidate in SOURCE_PROFILE_VALUES else str(import_template.get("source_profile", "generic"))


def missing_required_fields(record: dict[str, Any], import_template: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for rule in import_template.get("field_mappings", []):
        if not rule.get("required", False):
            continue
        matched_key, value = resolve_source_value(record, str(rule.get("source_field", "")), rule.get("aliases", []))
        if matched_key is None or is_missing_value(value):
            missing.append(str(rule.get("source_field", "")))
    return missing


def normalize_record(record: dict[str, Any], import_template: dict[str, Any], source_file: Path) -> dict[str, Any]:
    mapped_fields, consumed_fields = map_record_fields(import_template, record)
    raw_text = build_raw_text(record, import_template.get("text_build", {}), mapped_fields, import_template.get("field_mappings", []))
    if not raw_text:
        raw_text = str(mapped_fields.get("raw_text", "") or "").strip()

    extra_metadata = {
        key: json_ready(value)
        for key, value in record.items()
        if key not in consumed_fields and key not in CORE_FIELDS
    }

    if isinstance(mapped_fields.get("extra_metadata"), dict):
        extra_metadata.update(json_ready(mapped_fields["extra_metadata"]))

    if mapped_fields.get("source_type") not in (None, ""):
        extra_metadata.setdefault("source_type", json_ready(mapped_fields["source_type"]))

    normalized: dict[str, Any] = {
        "doc_id": mapped_fields.get("doc_id")
        or f"{source_file.stem}-{hashlib.md5(json.dumps(json_ready(record), ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()[:8]}",
        "source_profile": normalize_source_profile(import_template, mapped_fields),
        "title": str(mapped_fields.get("title") or record.get("title") or source_file.stem),
        "raw_text": raw_text,
        "year": parse_optional_year(mapped_fields.get("year")),
        "source": json_ready(mapped_fields.get("source")),
        "author": json_ready(mapped_fields.get("author")),
        "institution": json_ready(mapped_fields.get("institution")),
        "country_or_region": json_ready(mapped_fields.get("country_or_region")),
        "category_or_tag": json_ready(mapped_fields.get("category_or_tag")),
        "keyword_field": json_ready(mapped_fields.get("keyword_field")),
        "extra_metadata": extra_metadata,
        "clean_text": "",
        "normalized_text": "",
        "tokens": [],
        "phrase_hits": [],
        "filtered_tokens": [],
        "status": "ready",
    }
    normalized["raw_hash"] = hashlib.md5(normalized["raw_text"].encode("utf-8")).hexdigest()
    normalized["id"] = normalized["doc_id"]
    return normalized


def imported_copy_path(project_dir: Path, source_path: Path) -> Path:
    imported_dir = project_dir / "corpus" / "imported"
    imported_dir.mkdir(parents=True, exist_ok=True)
    candidate = imported_dir / source_path.name
    if not candidate.exists():
        return candidate

    index = 2
    while True:
        candidate = imported_dir / f"{source_path.stem}-{index}{source_path.suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def project_relative_source_path(project_dir: Path, source_path: Path) -> tuple[Path, str]:
    copied_path = imported_copy_path(project_dir, source_path)
    shutil.copy2(source_path, copied_path)
    return copied_path, copied_path.relative_to(project_dir).as_posix()


def workspace_relative_source_path(source_path: Path) -> str:
    try:
        return source_path.resolve().relative_to(workspace_root()).as_posix()
    except ValueError:
        return str(source_path.resolve())


def import_files(
    file_paths: Iterable[Path | str],
    import_template: dict[str, Any],
    project_dir: Path | None = None,
    existing_hashes: Iterable[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    corpus: list[dict[str, Any]] = []
    source_files: list[dict[str, Any]] = []
    validation_issues: list[dict[str, Any]] = []
    seen_hashes: set[str] = set(existing_hashes or [])

    for raw_path in file_paths:
        path = Path(raw_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Source file not found: {path}")

        dataframe = dataframe_from_source(path)
        stored_path = path
        relative_path = workspace_relative_source_path(path)
        if project_dir is not None:
            stored_path, relative_path = project_relative_source_path(project_dir, path)

        records = dataframe.fillna("").to_dict(orient="records")
        valid_rows = 0
        for row_index, raw_record in enumerate(records, start=1):
            missing_fields = missing_required_fields(raw_record, import_template)
            if missing_fields:
                validation_issues.append(
                    {"file": str(path), "row": row_index, "missing_fields": missing_fields, "reason": "missing_required_fields"}
                )
                continue
            record = normalize_record(raw_record, import_template, stored_path)
            record.setdefault("extra_metadata", {})
            record["extra_metadata"]["_source_relative_path"] = relative_path
            record["extra_metadata"]["_source_file_name"] = stored_path.name
            record["extra_metadata"]["_source_row_index"] = row_index
            if not record["raw_text"]:
                validation_issues.append(
                    {"file": str(path), "row": row_index, "missing_fields": ["raw_text"], "reason": "empty_raw_text"}
                )
                record["status"] = "warning"
                continue
            if record["raw_hash"] in seen_hashes:
                validation_issues.append(
                    {"file": str(path), "row": row_index, "missing_fields": [], "reason": "duplicate_raw_text"}
                )
                continue
            seen_hashes.add(record["raw_hash"])
            corpus.append(record)
            valid_rows += 1

        source_files.append(
            {
                "id": f"source-{stored_path.stem}-{hashlib.md5(str(stored_path).encode('utf-8')).hexdigest()[:8]}",
                "name": stored_path.name,
                "source_type": stored_path.suffix.lower().lstrip("."),
                "relative_path": relative_path,
                "imported_at": utc_now_iso(),
                "row_count": valid_rows,
            }
        )

    return corpus, source_files, validation_issues
