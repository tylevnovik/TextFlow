from __future__ import annotations

from app.api.actions.imports import normalize_corpus_document
from app.storage.projects import create_project, load_project, save_project
from app.storage.reviews import create_review_task, resolve_review_task


def test_create_review_task_for_keyword_merge(isolated_workspace):
    project_dir, manifest = create_project("review queue", "review queue")

    created = create_review_task(
        manifest,
        review_type="keyword_merge",
        target_ref={"source_term": "AIGC", "target_term": "生成式 AI"},
        title="合并关键词 AIGC",
        payload={
            "dictionary_kind": "standard_terms",
            "source_term": "AIGC",
            "target_term": "生成式 AI",
        },
    )
    save_project(project_dir, manifest, [], already_normalized=True)

    reloaded_manifest, _ = load_project(project_dir)
    assert created["review_type"] == "keyword_merge"
    assert created["status"] == "open"
    assert reloaded_manifest["review_tasks"][0]["payload"]["target_term"] == "生成式 AI"


def test_resolve_review_task_writes_dictionary_overlay(isolated_workspace):
    project_dir, manifest = create_project("review writeback", "review writeback")
    created = create_review_task(
        manifest,
        review_type="keyword_merge",
        target_ref={"source_term": "AIGC", "target_term": "生成式 AI"},
        payload={
            "dictionary_kind": "standard_terms",
            "source_term": "AIGC",
            "target_term": "生成式 AI",
        },
    )

    resolve_review_task(manifest, [], created["review_id"], {"decision": "resolve", "notes": "采用标准词写回"})
    save_project(project_dir, manifest, [], already_normalized=True)

    reloaded_manifest, _ = load_project(project_dir)
    custom_table = next(
        table
        for table in reloaded_manifest["dictionary_set"]["collections"]["standard_terms"]["tables"]
        if table.get("editable")
    )
    custom_lookup = {
        (str(entry.get("source") or ""), str(entry.get("target") or "")): entry
        for entry in custom_table.get("entries", [])
    }

    assert ("AIGC", "生成式 AI") in custom_lookup
    assert reloaded_manifest["review_tasks"][0]["status"] == "resolved"


def test_resolve_review_task_can_patch_corpus_document(isolated_workspace):
    project_dir, manifest = create_project("review document patch", "review document patch")
    corpus = [
        normalize_corpus_document(
            {
                "doc_id": "DOC-001",
                "title": "初始标题",
                "raw_text": "旧正文",
                "source_profile": "generic",
            }
        )
    ]
    save_project(project_dir, manifest, corpus, already_normalized=True)

    created = create_review_task(
        manifest,
        review_type="document_patch",
        target_ref={"doc_id": "DOC-001"},
        payload={
            "document_patch": {
                "title": "修订标题",
                "raw_text": "修订后的正文",
            }
        },
    )

    resolve_review_task(manifest, corpus, created["review_id"], {"decision": "resolve", "notes": "按人工校对写回"})
    save_project(project_dir, manifest, corpus, already_normalized=True)

    reloaded_manifest, reloaded_corpus = load_project(project_dir)
    assert reloaded_corpus[0]["title"] == "修订标题"
    assert reloaded_corpus[0]["raw_text"] == "修订后的正文"
    assert reloaded_manifest["review_tasks"][0]["status"] == "resolved"
