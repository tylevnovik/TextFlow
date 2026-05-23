from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from ...defaults import utc_now_iso

CORPUS_SOURCE_NODE_TYPES = {"corpus_input", "load_project_corpus"}
DICTIONARY_SOURCE_NODE_TYPES = {
    "dictionary_input",
    "project_dictionary_set",
}


def _stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _node_id(node: dict[str, Any]) -> str:
    return str(node.get("node_id") or "")


def _node_type(node: dict[str, Any]) -> str:
    return str(node.get("node_type") or "")


def build_dependency_index(workflow_definition: dict[str, Any]) -> dict[str, Any]:
    nodes = {
        _node_id(node): deepcopy(node)
        for node in workflow_definition.get("nodes", [])
        if isinstance(node, dict) and _node_id(node)
    }
    downstream: dict[str, set[str]] = {node_id: set() for node_id in nodes}
    upstream: dict[str, set[str]] = {node_id: set() for node_id in nodes}

    for edge in workflow_definition.get("edges", []):
        if not isinstance(edge, dict):
            continue
        from_node = str(edge.get("from_node") or "")
        to_node = str(edge.get("to_node") or "")
        if from_node not in nodes or to_node not in nodes:
            continue
        downstream.setdefault(from_node, set()).add(to_node)
        upstream.setdefault(to_node, set()).add(from_node)

    node_types = {node_id: _node_type(node) for node_id, node in nodes.items()}
    return {
        "nodes": nodes,
        "node_types": node_types,
        "downstream": downstream,
        "upstream": upstream,
        "corpus_node_ids": {node_id for node_id, node_type in node_types.items() if node_type in CORPUS_SOURCE_NODE_TYPES},
        "dictionary_node_ids": {node_id for node_id, node_type in node_types.items() if node_type in DICTIONARY_SOURCE_NODE_TYPES},
    }


def _downstream_closure(seed_node_ids: set[str], downstream: dict[str, set[str]]) -> set[str]:
    dirty = set(seed_node_ids)
    stack = list(seed_node_ids)
    while stack:
        node_id = stack.pop()
        for child_id in downstream.get(node_id, set()):
            if child_id in dirty:
                continue
            dirty.add(child_id)
            stack.append(child_id)
    return dirty


def compute_dirty_node_ids(
    workflow_definition: dict[str, Any],
    changed_resources: dict[str, Any],
    dependency_index: dict[str, Any] | None = None,
) -> set[str]:
    index = dependency_index or build_dependency_index(workflow_definition)
    seed_node_ids = {
        str(item)
        for item in changed_resources.get("changed_node_ids", [])
        if str(item)
    }

    changed_doc_ids = [str(item) for item in changed_resources.get("changed_doc_ids", []) if str(item)]
    if changed_doc_ids or changed_resources.get("corpus_changed"):
        explicit_sources = {
            str(item)
            for item in changed_resources.get("source_node_ids", [])
            if str(item)
        }
        seed_node_ids.update(explicit_sources or index.get("corpus_node_ids", set()))

    changed_dictionary_tables = [
        str(item)
        for item in changed_resources.get("changed_dictionary_tables", [])
        if str(item)
    ]
    if changed_dictionary_tables or changed_resources.get("dictionary_changed"):
        seed_node_ids.update(index.get("dictionary_node_ids", set()))

    return _downstream_closure(seed_node_ids, index.get("downstream", {}))


def document_fingerprint(document: dict[str, Any]) -> str:
    raw_hash = document.get("raw_hash")
    if raw_hash:
        return str(raw_hash)
    payload = {
        "doc_id": document.get("doc_id") or document.get("id"),
        "raw_text": document.get("raw_text"),
        "title": document.get("title"),
        "year": document.get("year"),
        "source": document.get("source"),
        "institution": document.get("institution"),
        "keyword_field": document.get("keyword_field"),
    }
    return _stable_hash(payload)


def corpus_fingerprint_index(corpus: list[dict[str, Any]]) -> dict[str, str]:
    return {
        str(item.get("doc_id") or item.get("id") or ""): document_fingerprint(item)
        for item in corpus
        if isinstance(item, dict) and str(item.get("doc_id") or item.get("id") or "")
    }


def detect_changed_doc_ids(manifest: dict[str, Any], corpus: list[dict[str, Any]]) -> list[str]:
    state = manifest.get("incremental_state") if isinstance(manifest.get("incremental_state"), dict) else {}
    previous = state.get("document_fingerprints") if isinstance(state.get("document_fingerprints"), dict) else {}
    current = corpus_fingerprint_index(corpus)
    return sorted(
        doc_id
        for doc_id, fingerprint in current.items()
        if str(previous.get(doc_id) or "") != fingerprint
    )


def select_incremental_scope(manifest: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    run_mode = "incremental" if str(payload.get("run_mode") or "").lower() == "incremental" else "full"
    changed_doc_ids = [str(item) for item in payload.get("changed_doc_ids", []) if str(item)]
    changed_dictionary_tables = [str(item) for item in payload.get("changed_dictionary_tables", []) if str(item)]
    process_changed_only = bool(
        payload.get("process_changed_only")
        or payload.get("changed_docs_only")
        or str(payload.get("incremental_scope") or "") == "changed_documents"
    )
    scope_doc_ids = changed_doc_ids if run_mode == "incremental" and process_changed_only else []
    return {
        "run_mode": run_mode,
        "changed_doc_ids": changed_doc_ids,
        "changed_dictionary_tables": changed_dictionary_tables,
        "process_changed_only": process_changed_only,
        "scope_doc_ids": scope_doc_ids,
        "previous_run_id": (manifest.get("run_history") or [{}])[-1].get("run_id") if manifest.get("run_history") else None,
    }


def invalidate_artifacts_for_dirty_nodes(
    manifest: dict[str, Any],
    dirty_node_ids: set[str],
    *,
    current_run_id: str | None = None,
) -> int:
    if not dirty_node_ids:
        return 0
    invalidated_at = utc_now_iso()
    invalidated_count = 0
    for record in manifest.get("artifact_records", []):
        if not isinstance(record, dict):
            continue
        if current_run_id and str(record.get("run_id") or "") == current_run_id:
            continue
        if str(record.get("node_id") or "") not in dirty_node_ids:
            continue
        if not record.get("invalidated"):
            invalidated_count += 1
        record["invalidated"] = True
        record["invalidated_at"] = invalidated_at
        record["invalidated_reason"] = "dirty_node"
    return invalidated_count


def update_incremental_state(
    manifest: dict[str, Any],
    corpus: list[dict[str, Any]],
    run_record: dict[str, Any],
    dirty_node_ids: set[str],
    incremental_scope: dict[str, Any],
) -> dict[str, Any]:
    state = manifest.get("incremental_state") if isinstance(manifest.get("incremental_state"), dict) else {}
    state = {
        **deepcopy(state),
        "document_fingerprints": corpus_fingerprint_index(corpus),
        "last_run_id": run_record.get("run_id"),
        "last_run_mode": run_record.get("run_mode", incremental_scope.get("run_mode", "full")),
        "last_dirty_node_ids": sorted(dirty_node_ids),
        "last_changed_doc_ids": list(incremental_scope.get("changed_doc_ids", [])),
        "last_changed_dictionary_tables": list(incremental_scope.get("changed_dictionary_tables", [])),
        "updated_at": utc_now_iso(),
    }
    manifest["incremental_state"] = state
    return state

