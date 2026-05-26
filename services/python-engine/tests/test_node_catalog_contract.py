from __future__ import annotations

from app.workflow.registry import builtin_node_definitions
from app.workflow.schema import default_config_from_params, validate_node_definition


def test_catalog_definitions_are_serializable_and_have_unique_types():
    definitions = builtin_node_definitions()
    node_types = [str(item["type"]) for item in definitions]

    assert len(node_types) == len(set(node_types))


def test_ui_enabled_definitions_pass_contract_validation():
    errors: list[str] = []
    for definition in builtin_node_definitions():
        if "ui" in definition or "graph" in definition:
            errors.extend(validate_node_definition(definition))

    assert errors == []


def test_all_builtin_nodes_have_graph_and_ui_schema():
    errors: list[str] = []
    for definition in builtin_node_definitions():
        errors.extend(validate_node_definition(definition))

    assert errors == []


def test_default_config_is_derived_from_param_defaults():
    definition = {
        "params": [
            {"param_id": "file_prefix", "default_value": "tables"},
            {"param_id": "export_xlsx", "default_value": True},
        ]
    }

    assert default_config_from_params(definition) == {"file_prefix": "tables", "export_xlsx": True}


def test_catalog_does_not_publish_unreleased_legacy_nodes():
    definitions = {str(definition["type"]): definition for definition in builtin_node_definitions()}
    unpublished_legacy_types = {
        "load_project_corpus",
        "filter_corpus",
        "project_dictionary_set",
        "analyze_corpus",
        "export_results",
    }

    assert unpublished_legacy_types.isdisjoint(definitions)
    assert {str(definition["category"]) for definition in definitions.values()}.isdisjoint({"legacy"})
