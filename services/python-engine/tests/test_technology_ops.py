from app.analysis.technology import technology_indicator_rows, technology_classification_rows


def test_technology_indicators_score_recent_growth_and_graph_bridge():
    term_year = [
        {"term": "dysprosium recycling", "year": 2021, "tf_in_year": 1, "df_in_year": 1},
        {"term": "dysprosium recycling", "year": 2024, "tf_in_year": 8, "df_in_year": 4},
        {"term": "legacy alloy", "year": 2021, "tf_in_year": 8, "df_in_year": 5},
        {"term": "legacy alloy", "year": 2024, "tf_in_year": 7, "df_in_year": 5},
    ]
    graph_metrics = [
        {"term": "dysprosium recycling", "betweenness": 0.5, "pagerank": 0.2},
        {"term": "legacy alloy", "betweenness": 0.01, "pagerank": 0.1},
    ]

    rows = technology_indicator_rows(term_year, graph_metrics, current_year=2024)
    emerging = next(row for row in rows if row["term"] == "dysprosium recycling")

    assert emerging["novelty_score"] > 0
    assert emerging["disruption_score"] > 0
    assert emerging["growth_rate"] > 1


def test_technology_classification_labels_emerging_terms():
    rows = technology_classification_rows(
        [
            {
                "term": "dysprosium recycling",
                "novelty_score": 0.9,
                "disruption_score": 0.7,
                "maturity_score": 0.2,
                "growth_rate": 3.0,
            }
        ]
    )
    assert rows[0]["technology_class"] == "emerging"
    assert rows[0]["primary_reason"]
