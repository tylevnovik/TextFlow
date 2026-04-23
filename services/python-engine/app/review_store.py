from __future__ import annotations

from copy import deepcopy
import hashlib
from typing import Any
from uuid import uuid4

from .defaults import build_dictionary_sheets_from_collections, utc_now_iso
from .project_store import editable_dictionary_table_for_kind

SUPPORTED_REVIEW_TYPES = {
    "keyword_merge",
    "institution_merge",
    "cluster_rename",
    "document_patch",
    "dictionary_patch",
}


def _review_tasks(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    tasks = manifest.setdefault("review_tasks", [])
    if not isinstance(tasks, list):
        manifest["review_tasks"] = []
        tasks = manifest["review_tasks"]
    return tasks


def _normalize_target_ref(target_ref: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(target_ref, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, value in target_ref.items():
        if value is None:
            continue
        normalized[str(key)] = str(value)
    return normalized


def _task_title(review_type: str, target_ref: dict[str, str], payload: dict[str, Any]) -> str:
    if review_type == "keyword_merge":
        return f"合并关键词 {target_ref.get('source_term') or payload.get('source_term') or '待确认'}"
    if review_type == "institution_merge":
        return f"统一机构名 {payload.get('canonical_institution') or target_ref.get('institution') or '待确认'}"
    if review_type == "cluster_rename":
        return f"重命名聚类 {target_ref.get('cluster_id') or payload.get('cluster_id') or '待确认'}"
    if review_type == "document_patch":
        return f"修订文档 {target_ref.get('doc_id') or payload.get('doc_id') or '待确认'}"
    if review_type == "dictionary_patch":
        return f"更新词表 {payload.get('dictionary_kind') or target_ref.get('dictionary_kind') or '待确认'}"
    return "人工复核任务"


def create_review_task(
    manifest: dict[str, Any],
    *,
    review_type: str,
    target_ref: dict[str, Any] | None = None,
    title: str | None = None,
    description: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_type = str(review_type or "").strip()
    if normalized_type not in SUPPORTED_REVIEW_TYPES:
        raise ValueError(f"Unsupported review type: {review_type}")

    timestamp = utc_now_iso()
    normalized_target_ref = _normalize_target_ref(target_ref)
    task_payload = deepcopy(payload) if isinstance(payload, dict) else {}
    task = {
        "review_id": f"review-{uuid4().hex[:12]}",
        "project_id": str(manifest.get("id") or ""),
        "review_type": normalized_type,
        "status": "open",
        "target_ref": normalized_target_ref,
        "title": str(title or _task_title(normalized_type, normalized_target_ref, task_payload)),
        "description": str(description or ""),
        "payload": task_payload,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    _review_tasks(manifest).append(task)
    return task


def list_review_tasks(manifest: dict[str, Any], status: str | None = None) -> list[dict[str, Any]]:
    tasks = [deepcopy(task) for task in _review_tasks(manifest) if isinstance(task, dict)]
    normalized_status = str(status or "").strip().lower()
    if normalized_status:
        tasks = [task for task in tasks if str(task.get("status") or "").strip().lower() == normalized_status]
    tasks.sort(key=lambda item: (str(item.get("status") or ""), str(item.get("updated_at") or "")), reverse=True)
    return tasks


def _find_review_task(manifest: dict[str, Any], review_id: str) -> dict[str, Any]:
    for task in _review_tasks(manifest):
        if isinstance(task, dict) and str(task.get("review_id") or "") == review_id:
            return task
    raise ValueError(f"Review task {review_id} not found")


def _normalize_resolution_payload(resolution: dict[str, Any] | None) -> dict[str, Any]:
    normalized = deepcopy(resolution) if isinstance(resolution, dict) else {}
    decision = str(normalized.get("decision") or "resolve").strip().lower() or "resolve"
    normalized["decision"] = "reject" if decision == "reject" else "resolve"
    return normalized


def _refresh_dictionary_sheets(manifest: dict[str, Any]) -> None:
    dictionary_set = manifest.get("dictionary_set")
    if not isinstance(dictionary_set, dict):
        raise ValueError("Project dictionary set is unavailable")
    collections = dictionary_set.get("collections")
    if not isinstance(collections, dict):
        raise ValueError("Project dictionary collections are unavailable")
    dictionary_set["sheets"] = build_dictionary_sheets_from_collections(collections)


def _upsert_editable_dictionary_entry(
    manifest: dict[str, Any],
    kind: str,
    entry_patch: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(entry_patch, dict):
        raise ValueError("Dictionary entry patch must be a record")

    source = str(entry_patch.get("source") or "").strip()
    if not source:
        raise ValueError("Dictionary entry source is required")
    target = entry_patch.get("target")
    normalized_target = None if target in (None, "") else str(target)

    table = editable_dictionary_table_for_kind(manifest["dictionary_set"], kind)
    entries = table.setdefault("entries", [])
    if not isinstance(entries, list):
        table["entries"] = []
        entries = table["entries"]

    existing = next(
        (
            entry
            for entry in entries
            if isinstance(entry, dict)
            and str(entry.get("source") or "").casefold() == source.casefold()
            and str(entry.get("target") or "").casefold() == str(normalized_target or "").casefold()
        ),
        None,
    )
    if existing is None:
        existing = {
            "id": entry_patch.get("id") or uuid4().hex,
            "source": source,
            "target": normalized_target,
            "enabled": True,
            "hits": int(entry_patch.get("hits") or 0),
            "tags": list(entry_patch.get("tags") or []),
            "notes": str(entry_patch.get("notes") or ""),
        }
        entries.append(existing)
    else:
        existing["source"] = source
        existing["target"] = normalized_target
        existing["enabled"] = bool(entry_patch.get("enabled", existing.get("enabled", True)))
        existing["hits"] = int(entry_patch.get("hits", existing.get("hits", 0)) or 0)
        if "tags" in entry_patch:
            existing["tags"] = list(entry_patch.get("tags") or [])
        if "notes" in entry_patch:
            existing["notes"] = str(entry_patch.get("notes") or "")

    _refresh_dictionary_sheets(manifest)
    return existing


def _patch_corpus_document(corpus: list[dict[str, Any]], doc_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(patch, dict):
        raise ValueError("Document patch must be a record")

    for index, document in enumerate(corpus):
        current_doc_id = str(document.get("doc_id") or document.get("id") or "")
        if current_doc_id != doc_id:
            continue

        merged = deepcopy(document)
        if isinstance(merged.get("extra_metadata"), dict) and isinstance(patch.get("extra_metadata"), dict):
            merged["extra_metadata"] = {
                **deepcopy(merged.get("extra_metadata") or {}),
                **deepcopy(patch.get("extra_metadata") or {}),
            }
        for key, value in patch.items():
            if key == "extra_metadata" and isinstance(patch.get("extra_metadata"), dict):
                continue
            merged[key] = value

        merged["doc_id"] = doc_id
        merged["id"] = str(merged.get("id") or doc_id)
        merged["title"] = str(merged.get("title") or document.get("title") or doc_id)
        merged["source_profile"] = str(merged.get("source_profile") or document.get("source_profile") or "generic")
        raw_text = str(merged.get("raw_text") or "")
        merged["raw_text"] = raw_text
        if "year" in merged and merged["year"] not in (None, ""):
            try:
                merged["year"] = int(merged["year"])
            except (TypeError, ValueError):
                merged["year"] = None
        if "raw_text" in patch:
            merged["clean_text"] = ""
            merged["normalized_text"] = ""
            merged["tokens"] = []
            merged["phrase_hits"] = []
            merged["filtered_tokens"] = []
            merged["raw_hash"] = hashlib.md5(raw_text.encode("utf-8")).hexdigest()
            merged["status"] = "ready" if raw_text.strip() else "warning"
        corpus[index] = merged
        return merged

    raise ValueError(f"Corpus document {doc_id} not found")


def apply_review_resolution(
    manifest: dict[str, Any],
    corpus: list[dict[str, Any]],
    task: dict[str, Any],
    resolution: dict[str, Any] | None = None,
) -> tuple[set[str], list[str]]:
    normalized_resolution = _normalize_resolution_payload(resolution)
    if normalized_resolution["decision"] == "reject":
        return {"manifest"}, []

    review_type = str(task.get("review_type") or "")
    payload = task.get("payload") if isinstance(task.get("payload"), dict) else {}
    dirty_sections = {"manifest"}
    applied_changes: list[str] = []

    if review_type == "keyword_merge":
        kind = str(normalized_resolution.get("dictionary_kind") or payload.get("dictionary_kind") or "standard_terms")
        source_term = str(normalized_resolution.get("source_term") or payload.get("source_term") or task.get("target_ref", {}).get("source_term") or "").strip()
        target_term = str(normalized_resolution.get("target_term") or payload.get("target_term") or task.get("target_ref", {}).get("target_term") or "").strip()
        if not source_term or not target_term:
            raise ValueError("Keyword merge resolution requires source_term and target_term")
        _upsert_editable_dictionary_entry(
            manifest,
            kind,
            {
                "source": source_term,
                "target": target_term,
                "notes": str(normalized_resolution.get("notes") or payload.get("notes") or ""),
                "tags": ["review", "keyword-merge"],
            },
        )
        dirty_sections.add("dictionary_set")
        applied_changes.append(f"{kind}:{source_term}->{target_term}")
    elif review_type == "dictionary_patch":
        kind = str(normalized_resolution.get("dictionary_kind") or payload.get("dictionary_kind") or task.get("target_ref", {}).get("dictionary_kind") or "custom_lexicon")
        entries = normalized_resolution.get("entries")
        if not isinstance(entries, list) or not entries:
            entries = payload.get("entries")
        if not isinstance(entries, list) or not entries:
            entries = [
                {
                    "source": normalized_resolution.get("source_term") or payload.get("source_term"),
                    "target": normalized_resolution.get("target_term") or payload.get("target_term"),
                    "notes": normalized_resolution.get("notes") or payload.get("notes"),
                }
            ]
        for entry in entries:
            upserted = _upsert_editable_dictionary_entry(manifest, kind, dict(entry))
            applied_changes.append(f"{kind}:{upserted['source']}->{upserted.get('target') or ''}".rstrip(">"))
        dirty_sections.add("dictionary_set")
    elif review_type == "document_patch":
        doc_id = str(normalized_resolution.get("doc_id") or payload.get("doc_id") or task.get("target_ref", {}).get("doc_id") or "").strip()
        patch = normalized_resolution.get("document_patch") if isinstance(normalized_resolution.get("document_patch"), dict) else payload.get("document_patch")
        if not doc_id or not isinstance(patch, dict):
            raise ValueError("Document patch resolution requires doc_id and document_patch")
        _patch_corpus_document(corpus, doc_id, patch)
        dirty_sections.add("corpus")
        applied_changes.append(f"document:{doc_id}")
    elif review_type == "institution_merge":
        canonical = str(normalized_resolution.get("canonical_institution") or payload.get("canonical_institution") or task.get("target_ref", {}).get("institution") or "").strip()
        if not canonical:
            raise ValueError("Institution merge resolution requires canonical_institution")
        requested_doc_ids = normalized_resolution.get("doc_ids")
        if not isinstance(requested_doc_ids, list) or not requested_doc_ids:
            requested_doc_ids = payload.get("doc_ids")
        target_doc_ids = [str(item) for item in requested_doc_ids if item] if isinstance(requested_doc_ids, list) else []
        if not target_doc_ids:
            source_values = normalized_resolution.get("source_values")
            if not isinstance(source_values, list) or not source_values:
                source_values = payload.get("source_values")
            alias_values = {str(item).strip() for item in source_values if item} if isinstance(source_values, list) else set()
            target_doc_ids = [
                str(document.get("doc_id") or document.get("id") or "")
                for document in corpus
                if str(document.get("institution") or "").strip() in alias_values
            ]
        if not target_doc_ids:
            target_doc_ids = [str(task.get("target_ref", {}).get("doc_id") or "").strip()]
        applied_doc_ids = [doc_id for doc_id in target_doc_ids if doc_id]
        if not applied_doc_ids:
            raise ValueError("Institution merge resolution did not match any corpus documents")
        for doc_id in applied_doc_ids:
            _patch_corpus_document(corpus, doc_id, {"institution": canonical})
        dirty_sections.add("corpus")
        applied_changes.append(f"institution:{canonical}:{len(applied_doc_ids)}")
    elif review_type == "cluster_rename":
        cluster_id = str(normalized_resolution.get("cluster_id") or payload.get("cluster_id") or task.get("target_ref", {}).get("cluster_id") or "").strip()
        label = str(normalized_resolution.get("label") or normalized_resolution.get("new_label") or payload.get("label") or payload.get("new_label") or "").strip()
        if not cluster_id or not label:
            raise ValueError("Cluster rename resolution requires cluster_id and label")
        results = manifest.setdefault("results", {})
        if not isinstance(results, dict):
            raise ValueError("Project results bundle is unavailable")
        cluster_label_map = results.setdefault("cluster_label_map", {})
        if not isinstance(cluster_label_map, dict):
            cluster_label_map = {}
            results["cluster_label_map"] = cluster_label_map
        cluster_label_map[cluster_id] = label
        applied_changes.append(f"cluster:{cluster_id}->{label}")
    else:
        raise ValueError(f"Unsupported review type: {review_type}")

    return dirty_sections, applied_changes


def resolve_review_task(
    manifest: dict[str, Any],
    corpus: list[dict[str, Any]],
    review_id: str,
    resolution: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], set[str]]:
    task = _find_review_task(manifest, review_id)
    normalized_resolution = _normalize_resolution_payload(resolution)
    dirty_sections, applied_changes = apply_review_resolution(manifest, corpus, task, normalized_resolution)
    timestamp = utc_now_iso()
    task["status"] = "resolved"
    task["updated_at"] = timestamp
    task["resolved_at"] = timestamp
    task["resolution"] = {
        **deepcopy(normalized_resolution),
        "applied_changes": applied_changes,
        "resolved_at": timestamp,
    }
    return task, dirty_sections | {"manifest"}
