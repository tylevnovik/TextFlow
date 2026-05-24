from __future__ import annotations

import gzip
import hashlib
import json
import pickle
from pathlib import Path
from typing import Any

from ...domain.common import utc_now_iso
from ...domain.workflow import workflow_payload_hash
from .previews import _json_ready

CORPUS_PORT_TYPES = {
    "CorpusTable",
    "ProjectCorpus",
    "ScopedCorpus",
    "CleanCorpus",
    "NormalizedCorpus",
    "TokenCorpus",
    "FilteredTokenCorpus",
}


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(_json_ready(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_json_file(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))


def _read_json_file(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _hash_port_value(port_type: str, value: Any) -> str:
    if port_type in CORPUS_PORT_TYPES and isinstance(value, list):
        normalized_rows: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            base = {
                "doc_id": item.get("doc_id"),
                "raw_hash": item.get("raw_hash"),
                "title": item.get("title"),
                "year": item.get("year"),
                "source": item.get("source"),
                "institution": item.get("institution"),
                "category_or_tag": item.get("category_or_tag"),
            }
            if port_type in {"CorpusTable", "ProjectCorpus", "ScopedCorpus"}:
                base["raw_text"] = item.get("raw_text")
            if port_type == "CleanCorpus":
                base["clean_text"] = item.get("clean_text")
            if port_type == "NormalizedCorpus":
                base["normalized_text"] = item.get("normalized_text")
            if port_type == "TokenCorpus":
                base["tokens"] = item.get("tokens")
                base["phrase_hits"] = item.get("phrase_hits")
            if port_type == "FilteredTokenCorpus":
                base["filtered_tokens"] = item.get("filtered_tokens")
            normalized_rows.append(base)
        encoded = json.dumps(normalized_rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _cache_payload_path(project_dir: Path, node_id: str, cache_key: str) -> Path:
    return project_dir / "cache" / "nodes" / node_id / f"{cache_key}.pkl"


def _legacy_json_cache_payload_path(project_dir: Path, node_id: str, cache_key: str) -> Path:
    return project_dir / "cache" / "nodes" / node_id / f"{cache_key}.json"


def _legacy_gzip_cache_payload_path(project_dir: Path, node_id: str, cache_key: str) -> Path:
    return project_dir / "cache" / "nodes" / node_id / f"{cache_key}.json.gz"


def _write_cache_payload(project_dir: Path, node_id: str, cache_key: str, outputs: dict[str, Any], output_hashes: dict[str, str]) -> str:
    cache_path = _cache_payload_path(project_dir, node_id, cache_key)
    payload = {
        "node_id": node_id,
        "cache_key": cache_key,
        "created_at": utc_now_iso(),
        "outputs": outputs,
        "output_hashes": output_hashes,
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("wb") as handle:
        pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
    return str(cache_path)


def _read_cache_payload(project_dir: Path, node_id: str, cache_key: str) -> tuple[dict[str, Any], dict[str, str], str] | None:
    cache_path = _cache_payload_path(project_dir, node_id, cache_key)
    if cache_path.exists():
        with cache_path.open("rb") as handle:
            payload = pickle.load(handle)
    else:
        legacy_cache_path = _legacy_json_cache_payload_path(project_dir, node_id, cache_key)
        if not legacy_cache_path.exists():
            legacy_cache_path = _legacy_gzip_cache_payload_path(project_dir, node_id, cache_key)
            if not legacy_cache_path.exists():
                return None
            with gzip.open(legacy_cache_path, "rt", encoding="utf-8") as handle:
                payload = json.load(handle)
            cache_path = legacy_cache_path
        else:
            payload = _read_json_file(legacy_cache_path)
            cache_path = legacy_cache_path
    outputs = payload.get("outputs") if isinstance(payload, dict) else None
    output_hashes = payload.get("output_hashes") if isinstance(payload, dict) else None
    if not isinstance(outputs, dict) or not isinstance(output_hashes, dict):
        return None
    return outputs, {str(key): str(value) for key, value in output_hashes.items()}, str(cache_path)


def _node_cache_enabled(node: dict[str, Any], definition: dict[str, Any]) -> bool:
    runtime = definition.get("runtime") if isinstance(definition.get("runtime"), dict) else {}
    if not bool(runtime.get("cacheable", False)):
        return False
    runtime_meta = node.get("runtime_meta") if isinstance(node.get("runtime_meta"), dict) else {}
    cache_override = runtime_meta.get("cache_enabled")
    if cache_override is None:
        return True
    return bool(cache_override)


def _node_cache_key(
    manifest: dict[str, Any],
    workflow_definition: dict[str, Any],
    node: dict[str, Any],
    executor_id: str,
    input_hashes: dict[str, Any],
) -> str:
    payload = {
        "project_id": manifest.get("id"),
        "workflow_id": workflow_definition.get("workflow_id"),
        "workflow_hash": workflow_payload_hash(workflow_definition),
        "dictionary_version": ((manifest.get("dictionary_set") or {}).get("version")),
        "node_id": node.get("node_id"),
        "node_type": node.get("node_type"),
        "node_impl_version": ((node.get("runtime_meta") or {}).get("node_impl_version")),
        "executor_id": executor_id,
        "config": node.get("config") or {},
        "inputs": input_hashes,
    }
    return _stable_hash(payload)
