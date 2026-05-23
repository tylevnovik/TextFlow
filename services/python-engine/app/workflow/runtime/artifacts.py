from __future__ import annotations

from typing import Any
from ..registry import NodeRegistry

def _definition_output_ports(definition: dict[str, Any]) -> list[dict[str, Any]]:
    outputs = definition.get("outputs")
    if not isinstance(outputs, list):
        return []
    return [output for output in outputs if isinstance(output, dict)]


def _definition_output_port(definition: dict[str, Any], port_id: str) -> dict[str, Any] | None:
    for output in _definition_output_ports(definition):
        if str(output.get("port_id") or "") == port_id:
            return output
    return None


def _result_key_for_output_port(definition: dict[str, Any], port_id: str) -> str | None:
    output_port = _definition_output_port(definition, port_id)
    if not isinstance(output_port, dict):
        return None
    result_key = str(output_port.get("result_bundle_key") or "").strip()
    return result_key or None


def _png_chart_ids_for_output_port(definition: dict[str, Any], port_id: str) -> set[str]:
    output_port = _definition_output_port(definition, port_id)
    if not isinstance(output_port, dict):
        return set()
    chart_ids = output_port.get("png_chart_ids")
    if not isinstance(chart_ids, list):
        return set()
    return {
        str(chart_id).strip()
        for chart_id in chart_ids
        if str(chart_id).strip()
    }


def _include_output_in_html_audit(definition: dict[str, Any], port_id: str) -> bool:
    output_port = _definition_output_port(definition, port_id)
    return bool(output_port and output_port.get("include_in_html_audit"))


def _result_bundle_bindings(definition: dict[str, Any]) -> list[tuple[str, str]]:
    bindings: list[tuple[str, str]] = []
    for output_port in _definition_output_ports(definition):
        port_id = str(output_port.get("port_id") or "")
        result_key = str(output_port.get("result_bundle_key") or "").strip()
        if port_id and result_key:
            bindings.append((port_id, result_key))
    return bindings


def _result_bundle_binding_map(
    workflow_definition: dict[str, Any],
    registry: NodeRegistry,
) -> dict[str, tuple[str, str]]:
    bindings: dict[str, tuple[str, str]] = {}
    for node in workflow_definition.get("nodes", []):
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("node_id") or "")
        node_type = str(node.get("node_type") or "")
        if not node_id or not node_type:
            continue
        definition = registry.definitions_by_type.get(node_type) or {}
        for _port_id, result_key in _result_bundle_bindings(definition):
            bindings[result_key] = (node_id, node_type)
    return bindings


def _artifact_kind_for_result_value(value: Any) -> str | None:
    if isinstance(value, list):
        return "table"
    if isinstance(value, dict):
        return "object"
    return None


def _explicit_artifact_output_bindings(definition: dict[str, Any]) -> list[tuple[str, str]]:
    outputs = definition.get("outputs") if isinstance(definition.get("outputs"), list) else []
    bindings: list[tuple[str, str]] = []
    for output_port in outputs:
        if not isinstance(output_port, dict):
            continue
        port_id = str(output_port.get("port_id") or "")
        artifact_kind = str(output_port.get("artifact_kind") or output_port.get("artifact_output_kind") or "")
        if port_id and artifact_kind:
            bindings.append((port_id, artifact_kind))
    return bindings


def _export_selection_from_active_graph(
    node_lookup: dict[str, dict[str, Any]],
    active_edges: list[dict[str, Any]],
    definitions_by_type: dict[str, dict[str, Any]],
) -> dict[str, set[str]]:
    selection = {
        "csv_tables": set(),
        "xlsx_tables": set(),
        "png_charts": set(),
        "html_result_keys": set(),
        "include_audit": set(),
    }
    for edge in active_edges:
        from_node = node_lookup.get(str(edge.get("from_node") or ""))
        to_node = node_lookup.get(str(edge.get("to_node") or ""))
        if not isinstance(from_node, dict) or not isinstance(to_node, dict):
            continue
        source_type = str(from_node.get("node_type") or "")
        sink_type = str(to_node.get("node_type") or "")
        source_port_id = str(edge.get("from_port") or "")
        source_definition = definitions_by_type.get(source_type) or {}
        result_key = _result_key_for_output_port(source_definition, source_port_id)
        sink_config = to_node.get("config") if isinstance(to_node.get("config"), dict) else {}
        include_sink_audit = bool(sink_config.get("include_audit", True))
        if sink_type == "save_csv" and result_key:
            selection["csv_tables"].add(result_key)
        if sink_type == "save_xlsx" and result_key:
            selection["xlsx_tables"].add(result_key)
        if sink_type == "save_png":
            selection["png_charts"].update(_png_chart_ids_for_output_port(source_definition, source_port_id))
        if sink_type == "save_html_report":
            if result_key and not _include_output_in_html_audit(source_definition, source_port_id):
                selection["html_result_keys"].add(result_key)
            if include_sink_audit and _include_output_in_html_audit(source_definition, source_port_id):
                selection["include_audit"].add("audit")
    return selection


def _audit_requested(export_selection: dict[str, set[str]]) -> bool:
    return any(
        (
            "audit" in set(export_selection.get("include_audit") or set()),
            "audit_table" in set(export_selection.get("csv_tables") or set()),
            "audit_table" in set(export_selection.get("xlsx_tables") or set()),
            "audit_table" in set(export_selection.get("html_result_keys") or set()),
        )
    )


def _artifact_step_for_node(definition: dict[str, Any]) -> str:
    runtime = definition.get("runtime") if isinstance(definition.get("runtime"), dict) else {}
    step_id = str(runtime.get("step_id") or "")
    if step_id in {"scope", "resource", "merge"}:
        return "ingestion"
    if step_id == "sink":
        return "export"
    if step_id == "utility":
        return "ingestion"
    return step_id or "analysis"

