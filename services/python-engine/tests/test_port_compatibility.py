from __future__ import annotations

from app.api.actions.dispatcher import action_get_node_catalog
from app.storage.projects import load_workspace_snapshot


def test_node_catalog_includes_backend_derived_port_compatibility(isolated_workspace):
    catalog = action_get_node_catalog()
    compatibility = catalog["port_compatibility"]

    assert compatibility["corpus_order"] == [
        "CorpusTable",
        "ProjectCorpus",
        "ScopedCorpus",
        "CleanCorpus",
        "NormalizedCorpus",
        "TokenCorpus",
        "FilteredTokenCorpus",
    ]
    assert "FrequencyTable" in compatibility["table_sources"]
    assert "KeywordTable" in compatibility["table_sources"]
    assert "AnyTable" in compatibility["table_sources"]
    assert "FrequencyTable" in compatibility["renderable_sources"]
    assert "KeywordTable" in compatibility["renderable_sources"]
    assert "AnalysisBundle" not in compatibility["renderable_sources"]
    assert "AnalysisBundle" not in compatibility["analysis_result_sources"]
    assert set(compatibility["table_sources"]).issubset(set(compatibility["analysis_result_sources"]))


def test_workspace_snapshot_uses_same_port_compatibility_catalog(isolated_workspace):
    catalog = action_get_node_catalog()
    snapshot = load_workspace_snapshot()

    assert snapshot["port_compatibility"] == catalog["port_compatibility"]
