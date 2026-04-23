from types import SimpleNamespace

from app.node_executors import (
    execute_cluster_evaluation,
    execute_join_results,
    execute_topic_modeling,
)


def _filtered_token_corpus() -> list[dict[str, object]]:
    return [
        {
            "doc_id": "DOC-001",
            "title": "Battery recycling supply chain",
            "year": 2024,
            "source": "paper",
            "institution": "OpenAI",
            "filtered_tokens": ["battery", "recycling", "supply", "chain", "risk"],
        },
        {
            "doc_id": "DOC-002",
            "title": "Closed-loop battery process",
            "year": 2024,
            "source": "patent",
            "institution": "OpenAI",
            "filtered_tokens": ["battery", "recycling", "process", "manufacturing", "supply"],
        },
        {
            "doc_id": "DOC-003",
            "title": "Academic writing transparency",
            "year": 2025,
            "source": "paper",
            "institution": "Anthropic",
            "filtered_tokens": ["academic", "writing", "citation", "transparency", "review"],
        },
        {
            "doc_id": "DOC-004",
            "title": "AI writing assistant policy",
            "year": 2025,
            "source": "report",
            "institution": "Anthropic",
            "filtered_tokens": ["writing", "assistant", "policy", "review", "citation"],
        },
    ]


def _document_cluster_rows() -> list[dict[str, object]]:
    return [
        {"doc_id": "DOC-001", "cluster_id": 0, "x": 0.0, "y": 0.1, "title": "Battery recycling supply chain"},
        {"doc_id": "DOC-002", "cluster_id": 0, "x": 0.2, "y": 0.0, "title": "Closed-loop battery process"},
        {"doc_id": "DOC-003", "cluster_id": 1, "x": 4.8, "y": 5.1, "title": "Academic writing transparency"},
        {"doc_id": "DOC-004", "cluster_id": 1, "x": 5.0, "y": 4.9, "title": "AI writing assistant policy"},
    ]


def _context(result_bundle: dict[str, object] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        manifest={"dictionary_set": {"collections": {}, "sheets": {}}},
        shared={},
        result_bundle=result_bundle or {},
        runtime_profile={
            "analysis": {
                "feature_term_count": 24,
                "topic_model_k": 2,
                "document_cluster_k": 2,
            }
        },
        node_progress=lambda *args, **kwargs: None,
    )


def test_topic_modeling_node_outputs_topic_term_and_doc_topic_tables():
    context = _context()
    corpus = _filtered_token_corpus()

    result = execute_topic_modeling(
        context,
        {"config": {"topic_model_k": 2, "top_terms_per_topic": 3}},
        {"token_corpus_in": corpus},
    )

    topic_term_rows = result["topic_term_table"]
    document_topic_rows = result["document_topic_table"]
    topic_summary_rows = result["topic_summary_table"]

    assert len(topic_summary_rows) == 2
    assert len(document_topic_rows) == len(corpus)
    assert all(row["topic_label"] for row in document_topic_rows)
    assert any(row["term"] in {"battery", "writing", "citation"} for row in topic_term_rows)
    assert all("document_count" in row for row in topic_summary_rows)


def test_cluster_evaluation_node_outputs_silhouette_and_cluster_sizes():
    context = _context()

    result = execute_cluster_evaluation(
        context,
        {"config": {}},
        {"document_cluster_table_in": _document_cluster_rows()},
    )

    rows = result["cluster_evaluation_table"]
    overall_row = next(row for row in rows if row["row_type"] == "overall")
    cluster_rows = [row for row in rows if row["row_type"] == "cluster"]

    assert overall_row["silhouette_score"] > 0
    assert overall_row["davies_bouldin_score"] >= 0
    assert {row["cluster_id"] for row in cluster_rows} == {0, 1}
    assert all(row["cluster_size"] == 2 for row in cluster_rows)


def test_join_results_node_merges_tables_on_named_keys():
    context = _context(
        {
            "frequency_table": [
                {"term": "battery", "tf": 4, "group": "left"},
                {"term": "writing", "tf": 3, "group": "left"},
            ],
            "keyness_table": [
                {"term": "battery", "llr": 5.1},
                {"term": "citation", "llr": 4.3},
            ],
        }
    )

    result = execute_join_results(
        context,
        {
            "config": {
                "left_artifact": "frequency_table",
                "right_artifact": "keyness_table",
                "join_keys": ["term"],
                "join_type": "inner",
            }
        },
        {},
    )

    assert result["joined_table"] == [{"term": "battery", "tf": 4, "group": "left", "llr": 5.1}]
