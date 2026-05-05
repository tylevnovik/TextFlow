from app.graph_ops import (
    build_term_graph_tables,
    graph_metric_rows,
    community_rows,
    main_path_rows,
    link_prediction_rows,
)


def test_build_term_graph_tables_from_cooccurrence_rows():
    nodes, edges = build_term_graph_tables(
        [{"term_a": "dysprosium", "term_b": "recycling", "cooccurrence_count": 4}]
    )
    assert {row["term"] for row in nodes} == {"dysprosium", "recycling"}
    assert edges[0]["weight"] == 4


def test_graph_metrics_include_pagerank_and_betweenness():
    nodes, edges = build_term_graph_tables(
        [
            {"term_a": "a", "term_b": "b", "cooccurrence_count": 4},
            {"term_a": "b", "term_b": "c", "cooccurrence_count": 3},
        ]
    )
    rows = graph_metric_rows(nodes, edges)
    row_b = next(row for row in rows if row["term"] == "b")
    assert row_b["degree"] == 2
    assert row_b["betweenness"] > 0


def test_community_and_link_prediction_are_deterministic():
    nodes, edges = build_term_graph_tables(
        [
            {"term_a": "a", "term_b": "b", "cooccurrence_count": 4},
            {"term_a": "b", "term_b": "c", "cooccurrence_count": 3},
            {"term_a": "d", "term_b": "e", "cooccurrence_count": 5},
        ]
    )
    assert community_rows(nodes, edges)
    assert link_prediction_rows(nodes, edges, top_n=5)
