from copy import deepcopy
from types import SimpleNamespace

from app.workflow.nodes.group_compare import execute_node as execute_group_compare
from app.workflow.nodes.keyness_analysis import execute_node as execute_keyness_analysis
from app.workflow.nodes.overlay_dictionary_rules import execute_node as execute_overlay_dictionary_rules
from app.workflow.nodes.select_dictionary_tables import execute_node as execute_select_dictionary_tables
from app.analysis.text import apply_dictionary, build_dictionary_runtime_state


DICTIONARY_KINDS = [
    "stopwords",
    "custom_lexicon",
    "phrase_lexicon",
    "synonym_map",
    "near_synonym_map",
    "standard_terms",
    "exclusion_terms",
    "regex_rules",
]


def _dictionary_entry(entry_id: str, source: str, target: str | None = None) -> dict[str, object]:
    return {
        "id": entry_id,
        "source": source,
        "target": target,
        "enabled": True,
        "hits": 0,
        "tags": [],
        "notes": "",
    }


def _dictionary_table(table_id: str, kind: str, entries: list[dict[str, object]]) -> dict[str, object]:
    return {
        "id": table_id,
        "kind": kind,
        "name": table_id,
        "version": "2.0.0",
        "description": "comparison node fixture",
        "source_url": None,
        "built_in": False,
        "editable": True,
        "enabled": True,
        "tags": [],
        "entries": deepcopy(entries),
    }


def _build_dictionary_set() -> dict[str, object]:
    collections: dict[str, object] = {}
    sheets: dict[str, object] = {}
    default_tables = {
        "standard_terms": [
            _dictionary_table(
                "standard-project",
                "standard_terms",
                [_dictionary_entry("standard-1", "llm", "large language model")],
            ),
            _dictionary_table(
                "standard-extra",
                "standard_terms",
                [_dictionary_entry("standard-2", "gpu", "graphics processing unit")],
            ),
        ],
        "synonym_map": [
            _dictionary_table(
                "synonym-project",
                "synonym_map",
                [_dictionary_entry("synonym-1", "genai", "generative ai")],
            )
        ],
        "stopwords": [
            _dictionary_table(
                "stopword-project",
                "stopwords",
                [_dictionary_entry("stopword-1", "the")],
            )
        ],
    }
    for kind in DICTIONARY_KINDS:
        tables = deepcopy(default_tables.get(kind, []))
        collections[kind] = {
            "kind": kind,
            "name": kind,
            "description": "comparison node fixture",
            "tables": tables,
        }
        entries: list[dict[str, object]] = []
        for table in tables:
            entries.extend(deepcopy(table.get("entries") or []))
        sheets[kind] = {
            "kind": kind,
            "name": kind,
            "version": "2.0.0",
            "entries": entries,
        }
    return {
        "id": "dictionary-test-fixture",
        "name": "comparison fixture",
        "version": "2.0.0",
        "bound_to_project": True,
        "collections": collections,
        "sheets": sheets,
    }


def _filtered_token_corpus() -> list[dict[str, object]]:
    return [
        {
            "doc_id": "DOC-001",
            "title": "OpenAI model systems",
            "year": 2024,
            "source": "journal",
            "institution": "OpenAI",
            "filtered_tokens": ["model", "model", "alignment", "scale"],
        },
        {
            "doc_id": "DOC-002",
            "title": "OpenAI alignment study",
            "year": 2024,
            "source": "journal",
            "institution": "OpenAI",
            "filtered_tokens": ["model", "alignment"],
        },
        {
            "doc_id": "DOC-003",
            "title": "Anthropic safety research",
            "year": 2025,
            "source": "report",
            "institution": "Anthropic",
            "filtered_tokens": ["safety", "safety", "alignment"],
        },
        {
            "doc_id": "DOC-004",
            "title": "Anthropic safety systems",
            "year": 2025,
            "source": "report",
            "institution": "Anthropic",
            "filtered_tokens": ["safety", "governance"],
        },
    ]


def _context(dictionary_set: dict[str, object] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        manifest={"dictionary_set": dictionary_set or _build_dictionary_set()},
        shared={},
        result_bundle={},
        runtime_profile={"analysis": {}},
        node_progress=lambda *args, **kwargs: None,
    )


def test_select_dictionary_tables_node_limits_active_tables():
    dictionary_set = _build_dictionary_set()
    context = _context(dictionary_set)

    result = execute_select_dictionary_tables(
        context,
        {"config": {"selected_table_ids": ["standard-extra", "synonym-project"]}},
        {"dictionary_set_in": dictionary_set},
    )

    filtered = result["dictionary_set"]
    standard_table_ids = [table["id"] for table in filtered["collections"]["standard_terms"]["tables"]]
    stopword_entries = filtered["sheets"]["stopwords"]["entries"]

    assert standard_table_ids == ["standard-extra"]
    assert filtered["sheets"]["standard_terms"]["entries"] == [
        _dictionary_entry("standard-2", "gpu", "graphics processing unit")
    ]
    assert stopword_entries == []


def test_select_dictionary_tables_node_accepts_multiline_kind_selection():
    dictionary_set = _build_dictionary_set()
    extra_stopword_table = _dictionary_table(
        "builtin-stopwords-en",
        "stopwords",
        [_dictionary_entry("stopword-2", "a")],
    )
    dictionary_set["collections"]["stopwords"]["tables"].append(extra_stopword_table)
    dictionary_set["sheets"]["stopwords"]["entries"].extend(deepcopy(extra_stopword_table["entries"]))
    context = _context(dictionary_set)

    result = execute_select_dictionary_tables(
        context,
        {"config": {"selected_table_ids_text": "standard_terms\nstopwords"}},
        {"dictionary_set_in": dictionary_set},
    )

    filtered = result["dictionary_set"]
    runtime_state = build_dictionary_runtime_state(filtered)
    tokens, audits = apply_dictionary(
        "DOC-001",
        ["the", "gpu", "a", "genai"],
        filtered,
        {"apply_standard_terms": True, "apply_stopwords": True, "apply_synonym_map": True},
        runtime_state=runtime_state,
    )

    assert [table["id"] for table in filtered["collections"]["standard_terms"]["tables"]] == [
        "standard-project",
        "standard-extra",
    ]
    assert [table["id"] for table in filtered["collections"]["stopwords"]["tables"]] == [
        "stopword-project",
        "builtin-stopwords-en",
    ]
    assert filtered["collections"]["synonym_map"]["tables"] == []
    assert tokens == ["graphics processing unit", "genai"]
    assert [audit["rule_type"] for audit in audits] == ["stopwords", "standard_terms", "stopwords"]


def test_overlay_dictionary_rules_node_applies_runtime_only_patch():
    dictionary_set = _build_dictionary_set()
    dictionary_set["collections"]["standard_terms"]["tables"] = []
    dictionary_set["sheets"]["standard_terms"]["entries"] = []
    context = _context(dictionary_set)

    result = execute_overlay_dictionary_rules(
        context,
        {
            "config": {
                "overlay_rows": [
                    {
                        "kind": "standard_terms",
                        "source": "llm",
                        "target": "large language model",
                        "enabled": True,
                    }
                ]
            }
        },
        {"dictionary_set_in": dictionary_set},
    )

    runtime_dictionary_set = result["dictionary_set"]
    runtime_state = build_dictionary_runtime_state(runtime_dictionary_set)
    mapped_tokens, audits = apply_dictionary(
        "DOC-001",
        ["llm"],
        runtime_dictionary_set,
        {"apply_standard_terms": True},
        runtime_state=runtime_state,
    )
    runtime_entry = runtime_dictionary_set["sheets"]["standard_terms"]["entries"][0]

    assert dictionary_set["sheets"]["standard_terms"]["entries"] == []
    assert runtime_entry["id"] == "runtime-standard_terms-1"
    assert runtime_entry["source"] == "llm"
    assert runtime_entry["target"] == "large language model"
    assert "runtime-overlay" in runtime_entry["tags"]
    assert mapped_tokens == ["large language model"]
    assert audits[0]["rule_type"] == "standard_terms"


def test_group_compare_node_emits_group_metric_table():
    context = _context()
    corpus = _filtered_token_corpus()

    result = execute_group_compare(
        context,
        {
            "config": {
                "group_field": "institution",
                "baseline_group": "OpenAI",
                "comparison_groups": ["Anthropic"],
            }
        },
        {"token_corpus_in": corpus},
    )

    rows = result["group_metric_table"]
    safety_row = next(row for row in rows if row["group_value"] == "Anthropic" and row["term"] == "safety")

    assert safety_row["term_count"] == 3
    assert safety_row["document_count"] == 2
    assert safety_row["normalized_frequency"] > 0
    assert safety_row["baseline_group"] == "OpenAI"
    assert safety_row["baseline_term_count"] == 0


def test_keyness_analysis_node_emits_llr_and_ratio_columns():
    context = _context()
    corpus = _filtered_token_corpus()

    result = execute_keyness_analysis(
        context,
        {
            "config": {
                "group_field": "institution",
                "baseline_group": "OpenAI",
                "comparison_group": "Anthropic",
                "min_frequency": 2,
            }
        },
        {"token_corpus_in": corpus},
    )

    rows = result["keyness_table"]
    safety_row = next(row for row in rows if row["term"] == "safety")

    assert all("llr" in row and "relative_ratio" in row for row in rows)
    assert "scale" not in {row["term"] for row in rows}
    assert safety_row["comparison_term_count"] == 3
    assert safety_row["baseline_term_count"] == 0
    assert safety_row["llr"] > 0
    assert safety_row["relative_ratio"] > 1
