from app.domain.defaults import workflow_port_compatible
from app.workflow.definitions.builtin import build_builtin_node_definitions


def test_all_analysis_output_ports_are_compatible_with_any_table_or_renderable():
    definitions = build_builtin_node_definitions()
    table_targets = {"AnyTable", "AnyAnalysisResult"}
    renderable_targets = {"AnyRenderable", "AnyAnalysisResult"}
    missing: list[tuple[str, str]] = []

    for definition in definitions:
        category = str(definition.get("category") or "")
        if category != "analysis":
            continue
        node_type = str(definition.get("type") or "")
        for port in definition.get("outputs", []):
            if not isinstance(port, dict):
                continue
            port_type = str(port.get("port_type") or "")
            if port_type in {"CorpusTable", "CleanCorpus", "NormalizedCorpus", "TokenCorpus", "FilteredTokenCorpus"}:
                continue
            can_table = any(workflow_port_compatible(port_type, t) for t in table_targets)
            can_render = any(workflow_port_compatible(port_type, t) for t in renderable_targets)
            if not can_table and not can_render:
                missing.append((node_type, port_type))

    assert not missing, f"Missing workflow_port_compatible mapping for: {missing}"


def test_technology_indicators_declares_graph_metric_input():
    definitions = {
        str(definition.get("type") or ""): definition
        for definition in build_builtin_node_definitions()
    }
    technology_inputs = {
        str(port.get("port_id") or ""): str(port.get("port_type") or "")
        for port in definitions["technology_indicators"].get("inputs", [])
        if isinstance(port, dict)
    }

    assert technology_inputs["term_year_table_in"] == "TermYearTable"
    assert technology_inputs["graph_metric_table_in"] == "GraphMetricTable"
