from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
import shutil

from .support import ProgressCallback, notify, ensure_bootstrap_project, load_project_or_fail
from ...ingestion import import_files, ensure_sample_files, parse_optional_year
from ...storage.projects import save_project, remember_project, export_project_package, import_project_package, read_json, write_json
from ...ingestion.specs import save_ingestion_spec, list_ingestion_specs
from ...domain.defaults import json_ready


def normalize_corpus_document(document: dict[str, Any], current: dict[str, Any] | None = None) -> dict[str, Any]:
    normalized = dict(current or {})
    normalized.update(document)
    doc_id = str(normalized.get("doc_id") or normalized.get("id") or f"doc-{hashlib.md5(json.dumps(json_ready(document), ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()[:8]}")
    raw_text = str(normalized.get("raw_text") or "")
    normalized["id"] = doc_id
    normalized["doc_id"] = doc_id
    normalized["title"] = str(normalized.get("title") or doc_id)
    normalized["source_profile"] = str(normalized.get("source_profile") or "generic")
    normalized["raw_text"] = raw_text
    normalized["clean_text"] = ""
    normalized["normalized_text"] = ""
    normalized["tokens"] = []
    normalized["phrase_hits"] = []
    normalized["filtered_tokens"] = []
    normalized["year"] = parse_optional_year(normalized.get("year"))
    normalized["extra_metadata"] = dict(normalized.get("extra_metadata") or {})
    normalized["status"] = "ready" if raw_text.strip() else "warning"
    normalized["raw_hash"] = hashlib.md5(raw_text.encode("utf-8")).hexdigest()
    return normalized


def refresh_source_files(project_dir: Path, manifest: dict[str, Any], corpus: list[dict[str, Any]]) -> dict[str, Any]:
    tracked_counts: dict[str, int] = {}
    has_untracked_documents = False
    for item in corpus:
        relative_path = item.get("extra_metadata", {}).get("_source_relative_path")
        if isinstance(relative_path, str) and relative_path:
            tracked_counts[relative_path] = tracked_counts.get(relative_path, 0) + 1
        else:
            has_untracked_documents = True

    next_sources: list[dict[str, Any]] = []
    for source in manifest.get("source_files", []):
        relative_path = str(source.get("relative_path") or "")
        next_source = dict(source)
        if relative_path in tracked_counts:
            next_source["row_count"] = tracked_counts[relative_path]
            next_sources.append(next_source)
            continue
        source_path = project_dir / relative_path if relative_path else None
        if not has_untracked_documents and relative_path.startswith("corpus/imported/") and source_path and source_path.exists():
            try:
                source_path.unlink()
            except OSError:
                pass
            continue
        next_sources.append(next_source)

    manifest["source_files"] = next_sources
    return manifest


def action_import_project_files(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.08, "正在读取项目配置")
    ensure_bootstrap_project()
    project_dir, manifest, corpus = load_project_or_fail(payload["project_id"])

    if payload.get("import_template"):
        manifest["import_template"] = payload["import_template"]

    existing_hashes = [item.get("raw_hash", "") for item in corpus if item.get("raw_hash")]
    notify(progress_callback, 0.35, "正在导入并校验文件")
    imported_corpus, source_files, validation_issues = import_files(
        payload.get("file_paths", []),
        manifest["import_template"],
        project_dir=project_dir,
        existing_hashes=existing_hashes,
    )
    corpus.extend(imported_corpus)
    manifest["source_files"] = [*manifest.get("source_files", []), *source_files]
    notify(progress_callback, 0.8, "正在保存导入结果")
    save_project(project_dir, manifest, corpus, already_normalized=True, dirty_sections={"manifest", "corpus"})
    remember_project(manifest["id"], set_current=True)

    notify(progress_callback, 1.0, "导入完成")
    return {
        "project_id": manifest["id"],
        "imported_documents": len(imported_corpus),
        "documents": imported_corpus,
        "project": manifest,
        "source_files": source_files,
        "document_count": len(corpus),
        "skipped_rows": len(validation_issues),
        "validation_issues": validation_issues[:10],
    }


def action_export_project_backup(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.1, "正在整理项目文件")
    ensure_bootstrap_project()
    project_dir, manifest, _corpus = load_project_or_fail(payload["project_id"])
    output_path = Path(payload["path"]).expanduser() if payload.get("path") else None
    notify(progress_callback, 0.6, "正在打包 .tfproj 项目包")
    archive_path = export_project_package(project_dir, output_path)
    remember_project(manifest["id"], set_current=True)
    notify(progress_callback, 1.0, "项目包已导出")
    try:
        relative_path = archive_path.relative_to(project_dir).as_posix()
    except ValueError:
        relative_path = str(archive_path)
    return {"path": str(archive_path), "relative_path": relative_path}


def action_import_project_package(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.1, "正在读取 .tfproj 项目包")
    project_dir, manifest, corpus = import_project_package(Path(payload["path"]))
    remember_project(manifest["id"], set_current=True)
    notify(progress_callback, 1.0, "项目包已导入")
    from ...storage.projects import build_project_summary
    return build_project_summary(project_dir, manifest, corpus)


def action_update_corpus_document(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.1, "正在保存语料文档")
    ensure_bootstrap_project()
    project_dir, manifest, corpus = load_project_or_fail(payload["project_id"])
    document = payload["document"]
    doc_id = str(document.get("doc_id") or document.get("id") or "")
    existing = next((item for item in corpus if item.get("doc_id") == doc_id or item.get("id") == doc_id), None)
    normalized = normalize_corpus_document(document, current=existing)

    updated = False
    next_corpus: list[dict[str, Any]] = []
    for item in corpus:
        item_doc_id = str(item.get("doc_id") or item.get("id") or "")
        if item_doc_id == normalized["doc_id"]:
            next_corpus.append(normalized)
            updated = True
        else:
            next_corpus.append(item)
    if not updated:
        next_corpus.append(normalized)

    manifest = refresh_source_files(project_dir, manifest, next_corpus)
    save_project(project_dir, manifest, next_corpus, already_normalized=True, dirty_sections={"manifest", "corpus"})
    remember_project(manifest["id"], set_current=True)
    notify(progress_callback, 1.0, "语料文档已保存，请重新运行处理流程")
    return {
        **normalized,
        "document": normalized,
        "document_count": len(next_corpus),
        "source_files": manifest.get("source_files", []),
        "project_updated_at": manifest.get("updated_at"),
    }


def action_delete_corpus_document(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.1, "正在删除语料文档")
    ensure_bootstrap_project()
    project_dir, manifest, corpus = load_project_or_fail(payload["project_id"])
    doc_id = str(payload["doc_id"])
    next_corpus = [item for item in corpus if str(item.get("doc_id") or item.get("id") or "") != doc_id]
    if len(next_corpus) == len(corpus):
        raise ValueError(f"Corpus document {doc_id} not found")

    manifest = refresh_source_files(project_dir, manifest, next_corpus)
    save_project(project_dir, manifest, next_corpus, already_normalized=True, dirty_sections={"manifest", "corpus"})
    remember_project(manifest["id"], set_current=True)
    notify(progress_callback, 1.0, "语料文档已删除，请重新运行处理流程")
    return {
        "doc_id": doc_id,
        "document_count": len(next_corpus),
        "source_files": manifest.get("source_files", []),
        "project_updated_at": manifest.get("updated_at"),
    }


def action_import_dictionary_sheet(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.1, "正在读取词表文件")
    ensure_bootstrap_project()
    project_dir, manifest, corpus = load_project_or_fail(payload["project_id"])
    kind = payload["kind"]
    source_path = Path(payload["path"])
    imported_table = read_json(source_path)
    if not isinstance(imported_table, dict):
        raise ValueError(f"Invalid dictionary sheet: {source_path}")

    collection = manifest["dictionary_set"]["collections"][kind]
    existing_ids = {
        str(table.get("id") or "")
        for table in collection.get("tables", [])
        if isinstance(table, dict)
    }
    base_id = str(imported_table.get("id") or f"{kind}-imported-{source_path.stem}")
    table_id = base_id
    suffix = 2
    while table_id in existing_ids:
        table_id = f"{base_id}-{suffix}"
        suffix += 1

    imported_table["id"] = table_id
    imported_table["kind"] = kind
    imported_table.setdefault("name", source_path.stem or "导入词表")
    imported_table.setdefault("version", "2.0.0")
    imported_table.setdefault("description", f"从 {source_path.name} 导入的词表资源。")
    imported_table.setdefault("source_url", None)
    imported_table["built_in"] = False
    imported_table["editable"] = True
    imported_table["enabled"] = bool(imported_table.get("enabled", True))
    imported_table.setdefault("tags", ["imported"])
    imported_table.setdefault("entries", [])
    collection.setdefault("tables", []).append(imported_table)
    notify(progress_callback, 0.7, "正在写入项目词表")
    save_project(project_dir, manifest, corpus, already_normalized=True, dirty_sections={"manifest", "dictionary_set"})
    remember_project(manifest["id"], set_current=True)
    notify(progress_callback, 1.0, "词表已导入")
    return {
        **imported_table,
        "table": imported_table,
        "dictionary_set": manifest["dictionary_set"],
        "project_updated_at": manifest.get("updated_at"),
    }


def action_export_dictionary_sheet(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.1, "正在整理词表")
    ensure_bootstrap_project()
    _project_dir, manifest, _corpus = load_project_or_fail(payload["project_id"])
    kind = payload["kind"]
    table_id = str(payload["table_id"])
    output_path = payload["path"]
    table = next(
        (
            item
            for item in manifest["dictionary_set"]["collections"][kind].get("tables", [])
            if isinstance(item, dict) and str(item.get("id") or "") == table_id
        ),
        None,
    )
    if table is None:
        raise ValueError(f"Dictionary table {table_id} not found in {kind}")
    write_json(Path(output_path), table)
    remember_project(manifest["id"], set_current=True)
    notify(progress_callback, 1.0, "词表已导出")
    return {
        "kind": kind,
        "table_id": table_id,
        "path": output_path,
    }


def action_save_ingestion_spec(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    notify(progress_callback, 0.1, "正在保存导入规格")
    ensure_bootstrap_project()
    project_dir, manifest, corpus = load_project_or_fail(payload["project_id"])
    spec_payload = payload.get("spec") if isinstance(payload.get("spec"), dict) else {key: value for key, value in payload.items() if key != "project_id"}
    saved = save_ingestion_spec(project_dir, manifest, spec_payload)
    save_project(project_dir, manifest, corpus, already_normalized=True, dirty_sections={"manifest", "ingestion_specs"})
    remember_project(manifest["id"], set_current=True)
    notify(progress_callback, 1.0, "导入规格已保存")
    return saved


def action_list_ingestion_specs(payload: dict[str, Any], progress_callback: ProgressCallback | None = None) -> list[dict[str, Any]]:
    notify(progress_callback, 0.1, "正在读取导入规格")
    ensure_bootstrap_project()
    project_dir, manifest, _corpus = load_project_or_fail(payload["project_id"])
    specs = list_ingestion_specs(project_dir, manifest)
    remember_project(manifest["id"], set_current=True)
    notify(progress_callback, 1.0, "导入规格已加载")
    return specs
