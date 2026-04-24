from __future__ import annotations

from app.defaults import default_workflow_definition
from app.incremental_runtime import (
    build_dependency_index,
    compute_dirty_node_ids,
    detect_changed_doc_ids,
    select_incremental_scope,
)


def test_editing_single_document_invalidates_only_dependent_nodes():
    workflow = {
        "nodes": [
            {"node_id": "node-corpus-a", "node_type": "corpus_input"},
            {"node_id": "node-clean-a", "node_type": "clean_text"},
            {"node_id": "node-analysis-a", "node_type": "frequency_statistics"},
            {"node_id": "node-corpus-b", "node_type": "corpus_input"},
            {"node_id": "node-analysis-b", "node_type": "frequency_statistics"},
        ],
        "edges": [
            {"from_node": "node-corpus-a", "to_node": "node-clean-a"},
            {"from_node": "node-clean-a", "to_node": "node-analysis-a"},
            {"from_node": "node-corpus-b", "to_node": "node-analysis-b"},
        ],
    }

    dependency_index = build_dependency_index(workflow)
    dirty = compute_dirty_node_ids(
        workflow,
        {"changed_doc_ids": ["DOC-001"], "source_node_ids": ["node-corpus-a"]},
        dependency_index,
    )

    assert dirty == {"node-corpus-a", "node-clean-a", "node-analysis-a"}


def test_incremental_run_processes_new_docs_only_when_requested():
    manifest = {
        "incremental_state": {
            "document_fingerprints": {
                "DOC-001": "old-hash",
            }
        }
    }
    corpus = [
        {"doc_id": "DOC-001", "raw_hash": "old-hash", "raw_text": "old"},
        {"doc_id": "DOC-002", "raw_hash": "new-hash", "raw_text": "new"},
    ]

    detected = detect_changed_doc_ids(manifest, corpus)
    scope = select_incremental_scope(
        manifest,
        {
            "run_mode": "incremental",
            "changed_doc_ids": detected,
            "process_changed_only": True,
        },
    )

    assert detected == ["DOC-002"]
    assert scope["run_mode"] == "incremental"
    assert scope["scope_doc_ids"] == ["DOC-002"]


def test_dictionary_overlay_change_invalidates_dictionary_downstream_nodes():
    workflow = default_workflow_definition()
    dependency_index = build_dependency_index(workflow)

    dirty = compute_dirty_node_ids(
        workflow,
        {"changed_dictionary_tables": ["standard_terms-project-custom"]},
        dependency_index,
    )

    assert "node-dictionary-input" in dirty
    assert "node-apply-dictionary-rules" in dirty
    assert "node-corpus-input" not in dirty
    assert any(node_id.startswith("node-frequency") or node_id == "node-frequency-statistics" for node_id in dirty)
