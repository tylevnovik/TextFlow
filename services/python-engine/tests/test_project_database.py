import json
from pathlib import Path

from app.project_database import (
    initialize_project_database,
    load_dictionary_set,
    load_corpus_rows,
    load_result_bundle,
    replace_corpus_rows,
    replace_dictionary_set,
    replace_result_bundle,
    write_artifact_payload,
    load_artifact_payload,
    project_database_integrity_check,
)


def test_project_database_round_trips_corpus_rows(tmp_path):
    db = initialize_project_database(tmp_path / "project.db")
    rows = [
        {
            "id": "DOC-1",
            "doc_id": "DOC-1",
            "source_profile": "wos",
            "language": None,
            "title": "Rare earth recovery",
            "raw_text": "Rare earth recovery text",
            "year": 2024,
            "source": None,
            "author": None,
            "institution": "Example University",
            "country_or_region": None,
            "category_or_tag": None,
            "keyword_field": None,
            "extra_metadata": {"UT": "WOS:1"},
            "status": "ready",
            "raw_hash": "hash-1",
            "clean_text": "",
            "normalized_text": "",
            "tokens": [],
            "phrase_hits": [],
            "filtered_tokens": [],
        }
    ]

    replace_corpus_rows(db, rows)

    assert load_corpus_rows(db) == rows
    assert project_database_integrity_check(db) == "ok"


def test_project_database_preserves_corpus_row_order(tmp_path):
    db = initialize_project_database(tmp_path / "project.db")
    rows = [
        {
            "id": "B",
            "doc_id": "B",
            "source_profile": "wos",
            "title": "Second",
            "raw_text": "Second text",
            "extra_metadata": {},
            "status": "ready",
        },
        {
            "id": "A",
            "doc_id": "A",
            "source_profile": "wos",
            "title": "First",
            "raw_text": "First text",
            "extra_metadata": {},
            "status": "ready",
        },
    ]

    replace_corpus_rows(db, rows)

    assert [row["doc_id"] for row in load_corpus_rows(db)] == ["B", "A"]


def test_project_database_round_trips_compressed_artifacts(tmp_path):
    db = initialize_project_database(tmp_path / "project.db")
    artifact = write_artifact_payload(
        db,
        run_id="run-1",
        node_id="node-frequency",
        kind="table",
        payload=[{"term": "dysprosium", "tf": 3}],
    )

    assert artifact["row_count"] == 1
    assert artifact["path"] == f"project.db:artifacts/{artifact['artifact_id']}/payload"
    assert artifact["preview_path"] == f"project.db:artifacts/{artifact['artifact_id']}/preview"
    assert load_artifact_payload(db, artifact["artifact_id"]) == [{"term": "dysprosium", "tf": 3}]


def test_project_database_round_trips_dictionary_set(tmp_path):
    db = initialize_project_database(tmp_path / "project.db")
    dictionary_set = {
        "id": "dict-test",
        "name": "测试词表",
        "version": "2.0.0",
        "bound_to_project": True,
        "collections": {
            "stopwords": {
                "kind": "stopwords",
                "name": "停用词",
                "description": "",
                "tables": [
                    {
                        "id": "builtin-stopwords-zh",
                        "kind": "stopwords",
                        "name": "中文停用词",
                        "version": "2.0.0",
                        "description": "",
                        "source_url": None,
                        "built_in": True,
                        "editable": False,
                        "enabled": True,
                        "tags": ["zh"],
                        "entries": [{"id": "sw-1", "source": "的", "target": None, "tags": ["zh"], "enabled": True, "hits": 7, "notes": ""}],
                    }
                ],
            }
        },
    }

    replace_dictionary_set(db, dictionary_set)

    assert load_dictionary_set(db) == dictionary_set


def test_project_database_round_trips_result_bundle(tmp_path):
    db = initialize_project_database(tmp_path / "project.db")
    results = {
        "frequency_table": [{"term": "rare earth", "tf": 2}],
        "report_files": ["runs/run-1/report.html"],
    }

    replace_result_bundle(db, results)

    assert load_result_bundle(db) == results
