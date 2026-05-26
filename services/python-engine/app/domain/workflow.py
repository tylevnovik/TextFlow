from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any

from .common import json_ready, utc_now_iso
from .runtime_profile import default_runtime_profile

def workflow_payload_hash(workflow_definition: dict[str, Any] | None) -> str:
    payload = workflow_execution_payload(workflow_definition)
    encoded = json.dumps(json_ready(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def workflow_execution_payload(workflow_definition: dict[str, Any] | None) -> dict[str, Any]:
    workflow = workflow_definition if isinstance(workflow_definition, dict) else {}
    return {
        "workflow_id": str(workflow.get("workflow_id") or ""),
        "version": str(workflow.get("version") or ""),
        "graph_mode": str(workflow.get("graph_mode") or ""),
        "source": str(workflow.get("source") or ""),
        "meta": deepcopy(workflow.get("meta") if isinstance(workflow.get("meta"), dict) else {}),
        "nodes": [
            workflow_node_execution_payload(node)
            for node in workflow.get("nodes", [])
            if isinstance(node, dict)
        ],
        "edges": [
            workflow_edge_execution_payload(edge)
            for edge in workflow.get("edges", [])
            if isinstance(edge, dict)
        ],
    }


def workflow_node_execution_payload(node: dict[str, Any] | None) -> dict[str, Any]:
    payload = node if isinstance(node, dict) else {}
    ui_state = payload.get("ui_state") if isinstance(payload.get("ui_state"), dict) else {}
    return {
        "node_id": str(payload.get("node_id") or ""),
        "node_type": str(payload.get("node_type") or ""),
        "config": deepcopy(payload.get("config") if isinstance(payload.get("config"), dict) else {}),
        "ui_state": {
            "bypassed": bool(ui_state.get("bypassed")),
        },
        "runtime_meta": deepcopy(payload.get("runtime_meta") if isinstance(payload.get("runtime_meta"), dict) else {}),
        "inputs": [
            workflow_port_execution_payload(port)
            for port in payload.get("inputs", [])
            if isinstance(port, dict)
        ],
        "outputs": [
            workflow_port_execution_payload(port)
            for port in payload.get("outputs", [])
            if isinstance(port, dict)
        ],
    }


def workflow_port_execution_payload(port: dict[str, Any] | None) -> dict[str, Any]:
    payload = port if isinstance(port, dict) else {}
    normalized = {
        "port_id": str(payload.get("port_id") or ""),
        "port_type": str(payload.get("port_type") or ""),
    }
    if payload.get("allow_multiple"):
        normalized["allow_multiple"] = True
    return normalized


def workflow_edge_execution_payload(edge: dict[str, Any] | None) -> dict[str, Any]:
    payload = edge if isinstance(edge, dict) else {}
    return {
        "from_node": str(payload.get("from_node") or ""),
        "from_port": str(payload.get("from_port") or ""),
        "to_node": str(payload.get("to_node") or ""),
        "to_port": str(payload.get("to_port") or ""),
    }


def default_workflow_definition(
    runtime_profile: dict[str, Any] | None = None,
    *,
    workflow_id: str = "wf-default",
    name: str = "默认工作流",
    source: str = "system_default",
) -> dict[str, Any]:
    from ..workflow.catalog import new_workflow_node

    runtime_profile_definition = deepcopy(runtime_profile if isinstance(runtime_profile, dict) else default_runtime_profile())
    enabled_steps = set(runtime_profile_definition.get("enabled_steps") or [])
    timestamp = utc_now_iso()
    export_definition = deepcopy(runtime_profile_definition.get("export") or {})
    run_scope_definition = deepcopy(runtime_profile_definition.get("run_scope") or {})

    def node_id_for_type(node_type: str) -> str:
        return f"node-{node_type.replace('_', '-')}"

    def make_node(node_type: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
        return new_workflow_node(
            node_type,
            node_id_for_type(node_type),
            runtime_profile=runtime_profile_definition,
            config=config,
        )

    filtered_sequence: list[str] = ["corpus_input"]
    if "cleaning" in enabled_steps:
        filtered_sequence.append("clean_text")
    if "normalization" in enabled_steps:
        filtered_sequence.append("normalize_text")
    filtered_sequence.append("tokenize")
    if "dictionary_application" in enabled_steps:
        filtered_sequence.append("apply_dictionary_rules")
    if "filtering" in enabled_steps:
        filtered_sequence.append("filter_terms")

    starter_nodes: list[dict[str, Any]] = [
        make_node(
            "corpus_input",
            {
                "resource_id": "project:corpus",
                **run_scope_definition,
            },
        ),
        make_node("dictionary_input"),
    ]

    for node_type in filtered_sequence[1:]:
        starter_nodes.append(make_node(node_type))

    for node_type in [
        "frequency_statistics",
        "term_document_analysis",
        "term_year_analysis",
        "cooccurrence_analysis",
        "feature_term_selection",
        "keyword_extraction",
        "keyword_clustering",
        "institution_keyword_analysis",
        "institution_topic_analysis",
        "document_clustering",
    ]:
        starter_nodes.append(make_node(node_type))

    if bool(export_definition.get("export_csv", True)):
        starter_nodes.append(make_node("save_csv"))
    if bool(export_definition.get("export_xlsx", True)):
        starter_nodes.append(make_node("save_xlsx"))
    if bool(export_definition.get("export_png", True)):
        starter_nodes.append(make_node("save_png"))
    if bool(export_definition.get("export_html_report", True)):
        starter_nodes.append(make_node("save_html_report"))

    node_by_type = {str(node["node_type"]): node for node in starter_nodes}
    edges: list[dict[str, Any]] = []
    edge_counter = 1

    def make_edge(
        edge_id: str,
        from_node: str,
        from_port: str,
        to_node: str,
        to_port: str,
    ) -> dict[str, Any]:
        return {
            "edge_id": edge_id,
            "from_node": from_node,
            "from_port": from_port,
            "to_node": to_node,
            "to_port": to_port,
        }

    def single_output_port(node_type: str) -> str | None:
        node = node_by_type.get(node_type)
        outputs = node.get("outputs") if isinstance(node, dict) else []
        if not isinstance(outputs, list) or not outputs:
            return None
        first_port = outputs[0]
        return str(first_port.get("port_id") or "") if isinstance(first_port, dict) else None

    def add_edge(from_type: str, from_port: str, to_type: str, to_port: str) -> None:
        nonlocal edge_counter
        from_node = node_by_type.get(from_type)
        to_node = node_by_type.get(to_type)
        if not from_node or not to_node:
            return
        if workflow_find_port(from_node, from_port, "outputs") is None:
            raise ValueError(f"Default workflow edge references missing output port: {from_type}.{from_port}")
        if workflow_find_port(to_node, to_port, "inputs") is None:
            raise ValueError(f"Default workflow edge references missing input port: {to_type}.{to_port}")
        edges.append(
            make_edge(
                f"edge-{edge_counter}",
                str(from_node["node_id"]),
                from_port,
                str(to_node["node_id"]),
                to_port,
            )
        )
        edge_counter += 1

    for from_type, to_type in zip(filtered_sequence, filtered_sequence[1:]):
        from_port = single_output_port(from_type)
        to_node = node_by_type.get(to_type)
        inputs = to_node.get("inputs") if isinstance(to_node, dict) else []
        to_port = str(inputs[0].get("port_id") or "") if isinstance(inputs, list) and inputs and isinstance(inputs[0], dict) else ""
        if from_port and to_port:
            add_edge(from_type, from_port, to_type, to_port)

    if "dictionary_input" in node_by_type and "apply_dictionary_rules" in node_by_type:
        add_edge("dictionary_input", "dictionary_set", "apply_dictionary_rules", "dictionary_set_in")

    last_process_type = next(
        (node_type for node_type in ["filter_terms", "apply_dictionary_rules", "tokenize", "normalize_text", "clean_text", "corpus_input"] if node_type in node_by_type),
        None,
    )

    for analysis_type in [
        "frequency_statistics",
        "term_document_analysis",
        "term_year_analysis",
        "cooccurrence_analysis",
        "feature_term_selection",
        "keyword_extraction",
        "keyword_clustering",
        "institution_keyword_analysis",
        "institution_topic_analysis",
        "document_clustering",
    ]:
        if analysis_type not in node_by_type:
            continue
        if analysis_type == "keyword_clustering":
            add_edge("feature_term_selection", "feature_term_table", analysis_type, "feature_term_table_in")
            continue
        if analysis_type == "institution_keyword_analysis":
            add_edge("keyword_extraction", "keyword_table", analysis_type, "keyword_table_in")
            continue
        if analysis_type == "institution_topic_analysis":
            add_edge("keyword_clustering", "keyword_cluster_table", analysis_type, "keyword_cluster_table_in")
            continue
        if last_process_type:
            from_port = single_output_port(last_process_type)
            to_node = node_by_type[analysis_type]
            inputs = to_node.get("inputs") if isinstance(to_node, dict) else []
            to_port = str(inputs[0].get("port_id") or "") if isinstance(inputs, list) and inputs and isinstance(inputs[0], dict) else ""
            if from_port and to_port:
                add_edge(last_process_type, from_port, analysis_type, to_port)

    sink_mappings = {
        "save_csv": [
            "frequency_statistics",
            "term_document_analysis",
            "term_year_analysis",
            "cooccurrence_analysis",
            "feature_term_selection",
            "keyword_extraction",
            "keyword_clustering",
            "institution_keyword_analysis",
            "institution_topic_analysis",
            "document_clustering",
        ],
        "save_xlsx": [
            "frequency_statistics",
            "term_document_analysis",
            "term_year_analysis",
            "cooccurrence_analysis",
            "feature_term_selection",
            "keyword_extraction",
            "keyword_clustering",
            "institution_keyword_analysis",
            "institution_topic_analysis",
            "document_clustering",
        ],
        "save_png": [
            "frequency_statistics",
            "keyword_extraction",
            "keyword_clustering",
            "institution_topic_analysis",
            "document_clustering",
        ],
        "save_html_report": [
            "frequency_statistics",
            "term_document_analysis",
            "term_year_analysis",
            "cooccurrence_analysis",
            "feature_term_selection",
            "keyword_extraction",
            "keyword_clustering",
            "institution_keyword_analysis",
            "institution_topic_analysis",
            "document_clustering",
        ],
    }

    for sink_type, source_types in sink_mappings.items():
        sink_node = node_by_type.get(sink_type)
        inputs = sink_node.get("inputs") if isinstance(sink_node, dict) else []
        sink_port = str(inputs[0].get("port_id") or "") if isinstance(inputs, list) and inputs and isinstance(inputs[0], dict) else ""
        if not sink_port:
            continue
        for source_type in source_types:
            from_port = single_output_port(source_type)
            if source_type in node_by_type and from_port:
                add_edge(source_type, from_port, sink_type, sink_port)
        if sink_type == "save_html_report" and "apply_dictionary_rules" in node_by_type:
            add_edge("apply_dictionary_rules", "audit_table", sink_type, sink_port)

    return {
        "workflow_id": workflow_id,
        "name": name,
        "version": "2.0.0",
        "graph_mode": "dag",
        "source": source,
        "meta": {
            "template_id": str(runtime_profile_definition.get("recipe_id") or "standard_analysis"),
            "output_bundle_id": str(runtime_profile_definition.get("output_bundle_id") or "full_report"),
        },
        "nodes": starter_nodes,
        "edges": edges,
        "groups": [],
        "viewport": {
            "x": 0,
            "y": 0,
            "zoom": 0.82,
        },
        "created_at": timestamp,
        "updated_at": timestamp,
    }

def workflow_port_compatible(source_type: str, target_type: str) -> bool:
    if source_type == target_type:
        return True
    table_source_types = {
        "FrequencyTable",
        "TermDocumentTable",
        "TermYearTable",
        "CooccurrenceTable",
        "FeatureTermTable",
        "KeywordTable",
        "KeywordClusterTable",
        "InstitutionKeywordTable",
        "InstitutionTopicTable",
        "DocumentClusterTable",
        "AuditTable",
        "MetadataAuditTable",
        "GraphNodeTable",
        "GraphEdgeTable",
        "GraphMetricTable",
        "CommunityTable",
        "MainPathTable",
        "LinkPredictionTable",
        "TechnologyIndicatorTable",
        "TechnologyClassificationTable",
    }
    renderable_source_types = {
        "FrequencyTable",
        "KeywordTable",
        "TermYearTable",
        "CooccurrenceTable",
        "DocumentClusterTable",
        "KeywordClusterTable",
        "InstitutionTopicTable",
        "AnyTable",
    }
    analysis_result_types = set(table_source_types) | {"AnyTable"}
    if target_type == "AnyTable" and source_type in table_source_types:
        return True
    if target_type == "AnyRenderable" and source_type in renderable_source_types:
        return True
    if target_type == "AnyAnalysisResult" and source_type in analysis_result_types:
        return True
    corpus_port_order = [
        "CorpusTable",
        "ProjectCorpus",
        "ScopedCorpus",
        "CleanCorpus",
        "NormalizedCorpus",
        "TokenCorpus",
        "FilteredTokenCorpus",
    ]
    try:
        source_index = corpus_port_order.index(source_type)
        target_index = corpus_port_order.index(target_type)
    except ValueError:
        if source_type in {"ProjectCorpus", "ScopedCorpus"} and target_type == "CorpusTable":
            return True
        if source_type == "CorpusTable" and target_type in {"ProjectCorpus", "ScopedCorpus"}:
            return True
        return False
    return source_index <= target_index


def workflow_find_port(node: dict[str, Any] | None, port_id: str, direction: str) -> dict[str, Any] | None:
    if not isinstance(node, dict):
        return None
    ports = node.get(direction)
    if not isinstance(ports, list):
        return None
    for port in ports:
        if isinstance(port, dict) and str(port.get("port_id")) == port_id:
            return port
    return None


def normalize_workflow_edges(
    workflow_definition: dict[str, Any] | None,
    nodes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    edge_rows = workflow_definition.get("edges") if isinstance(workflow_definition, dict) else []
    if not isinstance(edge_rows, list):
        return []

    node_lookup = {
        str(node.get("node_id")): node
        for node in nodes
        if isinstance(node, dict) and node.get("node_id")
    }
    normalized: list[dict[str, Any]] = []

    for edge in edge_rows:
        if not isinstance(edge, dict):
            continue
        from_node_id = str(edge.get("from_node") or "")
        to_node_id = str(edge.get("to_node") or "")
        from_port_id = str(edge.get("from_port") or "")
        to_port_id = str(edge.get("to_port") or "")
        if not from_node_id or not to_node_id or from_node_id == to_node_id:
            continue
        from_node = node_lookup.get(from_node_id)
        to_node = node_lookup.get(to_node_id)
        from_port = workflow_find_port(from_node, from_port_id, "outputs")
        to_port = workflow_find_port(to_node, to_port_id, "inputs")
        if not isinstance(from_port, dict) or not isinstance(to_port, dict):
            continue
        if not workflow_port_compatible(str(from_port.get("port_type") or ""), str(to_port.get("port_type") or "")):
            continue

        target_allows_multiple = bool(to_port.get("allow_multiple"))
        if not target_allows_multiple:
            normalized = [
                existing
                for existing in normalized
                if not (
                    str(existing.get("to_node")) == to_node_id
                    and str(existing.get("to_port")) == to_port_id
                )
            ]
        if any(
            str(existing.get("from_node")) == from_node_id
            and str(existing.get("from_port")) == from_port_id
            and str(existing.get("to_node")) == to_node_id
            and str(existing.get("to_port")) == to_port_id
            for existing in normalized
        ):
            continue
        normalized.append(deepcopy(edge))

    return normalized


def workflow_reachable_node_ids(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> set[str]:
    incoming: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        key = (str(edge.get("to_node") or ""), str(edge.get("to_port") or ""))
        if not all(key):
            continue
        incoming.setdefault(key, []).append(edge)

    reachable = set()
    for node in nodes:
        if not isinstance(node, dict) or not node.get("node_id"):
            continue
        inputs = node.get("inputs")
        if isinstance(inputs, list) and not inputs:
            reachable.add(str(node["node_id"]))

    changed = True
    while changed:
        changed = False
        for node in nodes:
            if not isinstance(node, dict) or not node.get("node_id"):
                continue
            node_id = str(node["node_id"])
            if node_id in reachable:
                continue
            inputs = node.get("inputs")
            if not isinstance(inputs, list) or not inputs:
                continue
            if all(
                any(str(edge.get("from_node") or "") in reachable for edge in incoming.get((node_id, str(port.get("port_id") or "")), []))
                for port in inputs
                if isinstance(port, dict)
            ):
                reachable.add(node_id)
                changed = True
    return reachable


def workflow_active_node_ids_from_sinks(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    reachable_node_ids: set[str],
) -> set[str]:
    sink_node_types = {"save_csv", "save_xlsx", "save_png", "save_html_report"}
    incoming_by_key: dict[str, list[dict[str, Any]]] = {}
    node_lookup = {str(node.get("node_id") or ""): node for node in nodes if isinstance(node, dict)}
    for edge in edges:
        to_node_id = str(edge.get("to_node") or "")
        to_port_id = str(edge.get("to_port") or "")
        incoming_by_key.setdefault(f"{to_node_id}:{to_port_id}", []).append(edge)

    sink_ids: list[str] = []
    for node in nodes:
        node_id = str(node.get("node_id") or "")
        if node_id not in reachable_node_ids:
            continue
        if str(node.get("node_type") or "") not in sink_node_types:
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, list):
            continue
        if all(incoming_by_key.get(f"{node_id}:{str(port.get('port_id') or '')}") for port in inputs if isinstance(port, dict)):
            sink_ids.append(node_id)

    active_ids = set(sink_ids)
    stack = sink_ids[:]
    while stack:
        current_id = stack.pop()
        current_node = node_lookup.get(current_id)
        if not isinstance(current_node, dict):
            continue
        inputs = current_node.get("inputs")
        if not isinstance(inputs, list):
            continue
        for port in inputs:
            if not isinstance(port, dict):
                continue
            for edge in incoming_by_key.get(f"{current_id}:{str(port.get('port_id') or '')}", []):
                from_node_id = str(edge.get("from_node") or "")
                if from_node_id and from_node_id not in active_ids:
                    active_ids.add(from_node_id)
                    stack.append(from_node_id)
    return active_ids
