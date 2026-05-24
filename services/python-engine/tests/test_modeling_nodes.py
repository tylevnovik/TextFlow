from types import SimpleNamespace

from app.workflow.nodes.cluster_evaluation import execute_node as execute_cluster_evaluation
from app.workflow.nodes.cooccurrence_analysis import execute_node as execute_cooccurrence_analysis
from app.workflow.nodes.deduplicate_documents import execute_node as execute_deduplicate_documents
from app.workflow.nodes.filter_by_metadata import execute_node as execute_filter_by_metadata
from app.workflow.nodes.focus_terms import execute_node as execute_focus_terms
from app.workflow.nodes.frequency_statistics import execute_node as execute_frequency_statistics
from app.workflow.nodes.join_results import execute_node as execute_join_results
from app.workflow.nodes.keyword_extraction import execute_node as execute_keyword_extraction
from app.workflow.nodes.similarity_analysis import execute_node as execute_similarity_analysis
from app.workflow.nodes.split_corpus import execute_node as execute_split_corpus
from app.workflow.nodes.topic_modeling import execute_node as execute_topic_modeling


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


def _progress_context() -> tuple[SimpleNamespace, list[tuple[str, float, str]]]:
    events: list[tuple[str, float, str]] = []
    context = _context()

    def node_progress(node: dict[str, object], fraction: float, detail: str | None = None) -> None:
        events.append((str(node.get("node_id") or node.get("node_type") or ""), float(fraction), detail or ""))

    context.node_progress = node_progress
    return context, events


def test_workflow_nodes_emit_real_stage_progress_before_completion():
    corpus = _filtered_token_corpus()

    frequency_context, frequency_events = _progress_context()
    execute_frequency_statistics(
        frequency_context,
        {"node_id": "node-frequency", "node_type": "frequency_statistics", "config": {}},
        {"token_corpus_in": corpus},
    )

    similarity_context, similarity_events = _progress_context()
    execute_similarity_analysis(
        similarity_context,
        {"node_id": "node-similarity", "node_type": "similarity_analysis", "config": {"min_similarity": 0.01}},
        {"token_corpus_in": corpus},
    )

    topic_context, topic_events = _progress_context()
    execute_topic_modeling(
        topic_context,
        {"node_id": "node-topic", "node_type": "topic_modeling", "config": {"topic_model_k": 2}},
        {"token_corpus_in": corpus},
    )

    cooccurrence_context, cooccurrence_events = _progress_context()
    execute_cooccurrence_analysis(
        cooccurrence_context,
        {"node_id": "node-cooccurrence", "node_type": "cooccurrence_analysis", "config": {"min_cooccurrence": 1}},
        {"token_corpus_in": corpus},
    )

    keyword_context, keyword_events = _progress_context()
    execute_keyword_extraction(
        keyword_context,
        {"node_id": "node-keyword", "node_type": "keyword_extraction", "config": {"top_k_per_doc": 2}},
        {"token_corpus_in": corpus},
    )

    filter_context, filter_events = _progress_context()
    execute_filter_by_metadata(
        filter_context,
        {"node_id": "node-filter", "node_type": "filter_by_metadata", "config": {"field": "source", "values": ["paper"]}},
        {"corpus_in": corpus},
    )

    dedupe_context, dedupe_events = _progress_context()
    execute_deduplicate_documents(
        dedupe_context,
        {"node_id": "node-dedupe", "node_type": "deduplicate_documents", "config": {"dedupe_keys_text": "title,year"}},
        {"corpus_in": corpus},
    )

    split_context, split_events = _progress_context()
    execute_split_corpus(
        split_context,
        {"node_id": "node-split", "node_type": "split_corpus", "config": {"splits_text": "train:0.5\ntest:0.5"}},
        {"corpus_in": corpus},
    )

    for node_id, events in [
        ("node-frequency", frequency_events),
        ("node-similarity", similarity_events),
        ("node-topic", topic_events),
        ("node-cooccurrence", cooccurrence_events),
        ("node-keyword", keyword_events),
        ("node-filter", filter_events),
        ("node-dedupe", dedupe_events),
        ("node-split", split_events),
    ]:
        node_events = [event for event in events if event[0] == node_id]
        assert node_events
        assert any(0.0 < fraction < 1.0 for _event_node_id, fraction, _detail in node_events)


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


def test_similarity_analysis_node_outputs_ranked_document_pairs():
    corpus = _filtered_token_corpus()

    result = execute_similarity_analysis(
        _context(),
        {"node_id": "node-similarity", "config": {"min_similarity": 0.01, "similarity_top_k": 4}},
        {"token_corpus_in": corpus},
    )

    rows = result["similarity_table"]
    assert rows
    assert rows == sorted(rows, key=lambda row: (-row["similarity"], row["doc_id_a"], row["doc_id_b"]))
    assert {"doc_id_a", "doc_id_b", "similarity"} <= set(rows[0])


def test_focus_terms_node_reduces_token_corpus_to_keyword_whitelist():
    corpus = _filtered_token_corpus()
    context = _context()

    result = execute_focus_terms(
        context,
        {
            "node_id": "node-focus",
            "config": {
                "term_source": "keywords",
                "term_field": "keyword",
                "max_terms": 2,
                "project_keywords_only": True,
            },
        },
        {
            "token_corpus_in": corpus,
            "term_table_in": [
                {"scope": "doc", "keyword": "risk", "rank": 1},
                {"scope": "project", "keyword": "battery", "rank": 1},
                {"scope": "project", "keyword": "supply", "rank": 2},
                {"scope": "project", "keyword": "writing", "rank": 3},
            ],
        },
    )

    focused = result["focused_token_corpus"]
    assert focused[0]["filtered_tokens"] == ["battery", "supply"]
    assert focused[1]["filtered_tokens"] == ["battery", "supply"]
    assert focused[2]["filtered_tokens"] == []
    summary = result["focus_term_summary"][0]
    assert summary["selected_term_count"] == 2
    assert summary["tokens_after"] < summary["tokens_before"]


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
