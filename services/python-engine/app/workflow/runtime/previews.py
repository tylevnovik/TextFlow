from __future__ import annotations

from typing import Any
import numpy as np

# We'll import json_ready directly from defaults or use a locally defined _json_ready
# to keep dependency clean.
def _json_ready(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    from pathlib import Path
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if hasattr(value, "tolist"):
        try:
            return value.tolist()
        except Exception:
            pass
    return str(value)


RUNTIME_PREVIEW_ROW_KEYS = (
    "doc_id",
    "title",
    "source",
    "institution",
    "year",
    "raw_text",
    "clean_text",
    "normalized_text",
    "tokens",
    "phrase_hits",
    "filtered_tokens",
    "term",
    "keyword",
    "topic_label",
    "cluster_id",
    "source_term",
    "target_term",
    "term_a",
    "term_b",
    "doc_id_a",
    "doc_id_b",
    "score",
    "tf",
    "df",
    "count",
    "action",
)


def _compact_runtime_preview_scalar(value: Any, limit: int = 160) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return _json_ready(value)
    text = str(value or "").strip().replace("\n", " ").replace("\r", " ")
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 1)].rstrip()}…"


def _compact_runtime_preview_row(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        return {"value": _compact_runtime_preview_scalar(row)}

    ordered_keys = [
        key
        for key in RUNTIME_PREVIEW_ROW_KEYS
        if key in row
    ]
    ordered_keys.extend(
        str(key)
        for key in row.keys()
        if str(key) not in ordered_keys
    )

    compacted: dict[str, Any] = {}
    for key in ordered_keys:
        if len(compacted) >= 12:
            break
        value = row.get(key)
        if value in (None, "", []):
            continue
        if isinstance(value, dict):
            compacted[key] = {
                str(item_key): _compact_runtime_preview_scalar(item_value, 80)
                for item_key, item_value in list(value.items())[:6]
            }
        elif isinstance(value, (list, tuple, set)):
            compacted[key] = [
                _compact_runtime_preview_scalar(item, 80)
                for item in list(value)[:12]
            ]
        else:
            compacted[key] = _compact_runtime_preview_scalar(value)
    return compacted


def _preview_runtime_value(value: Any) -> dict[str, Any]:
    normalized = _json_ready(value)
    if isinstance(normalized, list):
        if not normalized:
            return {"kind": "empty", "row_count": 0}
        if all(isinstance(item, dict) for item in normalized):
            return {
                "kind": "table",
                "row_count": len(normalized),
                "rows": [_compact_runtime_preview_row(item) for item in normalized[:5]],
            }
        return {
            "kind": "list",
            "row_count": len(normalized),
            "items": [_compact_runtime_preview_scalar(item, 120) for item in normalized[:12]],
        }
    if isinstance(normalized, dict):
        return {
            "kind": "object",
            "row_count": len(normalized),
            "keys": [str(key) for key in list(normalized.keys())[:12]],
            "value": _compact_runtime_preview_row(normalized),
        }
    if normalized is None:
        return {"kind": "empty", "row_count": 0}
    if isinstance(normalized, str):
        if not normalized.strip():
            return {"kind": "empty", "row_count": 0}
        return {
            "kind": "text",
            "row_count": 1,
            "text": _compact_runtime_preview_scalar(normalized, 500),
        }
    return {
        "kind": "scalar",
        "row_count": 1,
        "value": _compact_runtime_preview_scalar(normalized, 160),
    }


def _preview_runtime_outputs(outputs: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(port_id): _preview_runtime_value(value)
        for port_id, value in outputs.items()
    }
