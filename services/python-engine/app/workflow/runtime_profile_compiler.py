from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..domain.runtime_profile import default_runtime_profile
from ..domain.workflow import (
    normalize_workflow_edges,
    workflow_active_node_ids_from_sinks,
    workflow_reachable_node_ids,
)
from .nodes._common import ANALYSIS_OUTPUT_FLAGS
from .registry import NodeCompileContext, NodeRegistry


def classify_output_bundle(export_config: dict[str, Any]) -> str:
    if (
        export_config.get("export_csv")
        and export_config.get("export_xlsx")
        and export_config.get("export_png")
        and export_config.get("export_html_report")
        and export_config.get("include_audit")
    ):
        return "full_report"
    if (
        export_config.get("export_csv")
        and export_config.get("export_xlsx")
        and not export_config.get("export_png")
        and not export_config.get("export_html_report")
        and export_config.get("include_audit")
    ):
        return "tables_only"
    if (
        not export_config.get("export_csv")
        and not export_config.get("export_xlsx")
        and export_config.get("export_png")
        and export_config.get("export_html_report")
        and not export_config.get("include_audit")
    ):
        return "charts_and_report"
    if (
        export_config.get("export_csv")
        and not export_config.get("export_xlsx")
        and not export_config.get("export_png")
        and not export_config.get("export_html_report")
        and export_config.get("include_audit")
    ):
        return "audit_archive"
    return "custom"


def compile_runtime_profile_from_workflow(
    workflow_definition: dict[str, Any] | None,
    runtime_profile: dict[str, Any] | None = None,
    *,
    registry: NodeRegistry | None = None,
) -> dict[str, Any]:
    if registry is None:
        from .registry import build_node_registry

        registry = build_node_registry(runtime_profile)

    compiled = deepcopy(runtime_profile if isinstance(runtime_profile, dict) else default_runtime_profile())
    execution_order = list(compiled.get("execution_order") or default_runtime_profile()["execution_order"])
    nodes = workflow_definition.get("nodes") if isinstance(workflow_definition, dict) else []
    normalized_nodes = [node for node in nodes if isinstance(node, dict) and node.get("node_id")] if isinstance(nodes, list) else []
    normalized_edges = normalize_workflow_edges(workflow_definition, normalized_nodes)
    reachable_node_ids = workflow_reachable_node_ids(normalized_nodes, normalized_edges)
    active_node_ids = workflow_active_node_ids_from_sinks(normalized_nodes, normalized_edges, reachable_node_ids)
    if not active_node_ids:
        active_node_ids = set(reachable_node_ids)

    export_config = deepcopy(compiled.get("export") or {})
    export_config.update(
        {
            "export_csv": False,
            "export_xlsx": False,
            "export_png": False,
            "export_html_report": False,
        }
    )
    context = NodeCompileContext(
        compiled=compiled,
        enabled_steps={"ingestion"},
        export_config=export_config,
        active_node_ids=set(active_node_ids),
        active_node_types=set(),
        execution_order=execution_order,
        workflow_definition=workflow_definition if isinstance(workflow_definition, dict) else None,
    )

    active_nodes: list[dict[str, Any]] = []
    for node in normalized_nodes:
        node_id = str(node.get("node_id") or "")
        if node_id not in context.active_node_ids:
            continue
        ui_state = node.get("ui_state")
        if isinstance(ui_state, dict) and bool(ui_state.get("bypassed")):
            continue
        active_nodes.append(node)
        context.active_node_types.add(str(node.get("node_type") or ""))

    context.merge_section("analysis", {flag_name: False for flag_name in ANALYSIS_OUTPUT_FLAGS})

    for node in active_nodes:
        compiler = registry.compilers.get(str(node.get("node_type") or ""))
        if compiler is not None:
            compiler(context, node)

    compiled["export"] = context.export_config

    meta = workflow_definition.get("meta") if isinstance(workflow_definition, dict) else {}
    meta_output_bundle_id = ""
    if isinstance(meta, dict):
        compiled["recipe_id"] = str(meta.get("template_id") or compiled.get("recipe_id") or "standard_analysis")
        meta_output_bundle_id = str(meta.get("output_bundle_id") or "")

    compiled["enabled_steps"] = [
        step_id
        for step_id in execution_order
        if step_id == "ingestion" or step_id in context.enabled_steps
    ]
    compiled["execution_order"] = execution_order
    compiled["output_bundle_id"] = meta_output_bundle_id or classify_output_bundle(compiled.get("export") or {})
    return compiled
