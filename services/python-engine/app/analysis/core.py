from __future__ import annotations

import re
from typing import Any

CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]+")


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


def build_analysis_text(item: dict[str, Any]) -> str:
    sections = [
        str(item.get("title") or ""),
        " ".join(item.get("filtered_tokens", [])),
        str(item.get("keyword_field") or ""),
    ]
    return "\n".join(section for section in sections if section).strip()
