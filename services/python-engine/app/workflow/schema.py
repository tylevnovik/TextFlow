from __future__ import annotations

from copy import deepcopy
from typing import Any

NODE_CATEGORIES = {"input", "process", "analysis", "output", "utility"}
PARAM_KINDS = {"boolean", "number", "string", "enum"}
WIDGET_KINDS = {
    "text",
    "textarea",
    "number",
    "switch",
    "select",
    "multi_text",
    "condition_rows",
    "key_value_rows",
    "group",
    "row",
    "help",
    "slot",
}
CONDITION_OPS = {"eq", "neq", "in", "not_in", "truthy", "falsy"}
SLOT_COMPONENTS = {
    "corpus_scope_selector",
    "dictionary_binding_selector",
    "dictionary_table_selector",
    "overlay_rule_grid",
    "metadata_condition_builder",
    "named_split_editor",
    "result_table_selector",
    "review_task_selector",
    "threshold_gate_editor",
}
CORPUS_PORT_ORDER = [
    "CorpusTable",
    "ProjectCorpus",
    "ScopedCorpus",
    "CleanCorpus",
    "NormalizedCorpus",
    "TokenCorpus",
    "FilteredTokenCorpus",
]


def default_config_from_params(definition: dict[str, Any]) -> dict[str, Any]:
    config: dict[str, Any] = {}
    params = definition.get("params") if isinstance(definition.get("params"), list) else []
    for param in params:
        if not isinstance(param, dict):
            continue
        param_id = str(param.get("param_id") or "").strip()
        if param_id and "default_value" in param:
            config[param_id] = deepcopy(param.get("default_value"))
    return config


def port_compatibility_from_definitions(definitions: list[dict[str, Any]]) -> dict[str, list[str]]:
    table_sources: list[str] = []
    renderable_sources: list[str] = []
    output_types: list[str] = []

    def append_unique(items: list[str], value: str) -> None:
        if value and value not in items:
            items.append(value)

    for definition in definitions:
        outputs = definition.get("outputs") if isinstance(definition.get("outputs"), list) else []
        for output in outputs:
            if not isinstance(output, dict):
                continue
            port_type = str(output.get("port_type") or "")
            if not port_type:
                continue
            append_unique(output_types, port_type)
            if output.get("result_bundle_key") or port_type == "AnyTable":
                append_unique(table_sources, port_type)
            if output.get("png_chart_ids") or port_type == "AnyRenderable":
                append_unique(renderable_sources, port_type)

    if "AnalysisBundle" in output_types:
        append_unique(renderable_sources, "AnalysisBundle")

    analysis_result_sources: list[str] = []
    for port_type in [*table_sources, "AnalysisBundle"]:
        if port_type == "AnalysisBundle" and port_type not in output_types:
            continue
        append_unique(analysis_result_sources, port_type)

    return {
        "table_sources": table_sources,
        "renderable_sources": renderable_sources,
        "analysis_result_sources": analysis_result_sources,
        "corpus_order": list(CORPUS_PORT_ORDER),
    }


def validate_node_definition(definition: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    node_type = str(definition.get("type") or "").strip()
    if not node_type:
        errors.append("type is required")
    if str(definition.get("category") or "") not in NODE_CATEGORIES:
        errors.append(f"{node_type}: category is invalid")
    if not isinstance(definition.get("inputs"), list):
        errors.append(f"{node_type}: inputs must be a list")
    if not isinstance(definition.get("outputs"), list):
        errors.append(f"{node_type}: outputs must be a list")
    if not isinstance(definition.get("params"), list):
        errors.append(f"{node_type}: params must be a list")
    else:
        errors.extend(_validate_params(node_type, definition.get("params")))
    if not isinstance(definition.get("runtime"), dict):
        errors.append(f"{node_type}: runtime must be an object")
    graph_definition = definition.get("graph")
    if not isinstance(graph_definition, dict):
        errors.append(f"{node_type}: graph is required")
    else:
        size = graph_definition.get("size")
        position = graph_definition.get("default_position")
        if (
            not isinstance(size, dict)
            or _positive_int(size.get("w")) is None
            or _positive_int(size.get("h")) is None
        ):
            errors.append(f"{node_type}: graph.size must contain positive w/h")
        if not isinstance(position, dict) or "x" not in position or "y" not in position:
            errors.append(f"{node_type}: graph.default_position must contain x/y")
    ui_definition = definition.get("ui")
    if not isinstance(ui_definition, dict):
        errors.append(f"{node_type}: ui is required")
    else:
        errors.extend(_validate_layout(node_type, ui_definition.get("layout"), path="ui.layout"))
    return errors


def _positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _validate_params(node_type: str, params: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(params, list):
        return [f"{node_type}: params must be a list"]
    for index, param in enumerate(params):
        item_path = f"params[{index}]"
        if not isinstance(param, dict):
            errors.append(f"{node_type}: {item_path} must be an object")
            continue
        if not str(param.get("param_id") or "").strip():
            errors.append(f"{node_type}: {item_path}.param_id is required")
        if str(param.get("kind") or "") not in PARAM_KINDS:
            errors.append(f"{node_type}: {item_path}.kind is invalid")
    return errors


def _validate_layout(node_type: str, layout: Any, *, path: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(layout, list):
        return [f"{node_type}: {path} must be a list"]
    for index, item in enumerate(layout):
        item_path = f"{path}[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{node_type}: {item_path} must be an object")
            continue
        widget = str(item.get("widget") or "")
        if widget not in WIDGET_KINDS:
            errors.append(f"{node_type}: {item_path}.widget is invalid")
        if widget in {"group", "row"}:
            errors.extend(_validate_layout(node_type, item.get("children"), path=f"{item_path}.children"))
        if widget == "slot" and str(item.get("component_id") or "") not in SLOT_COMPONENTS:
            errors.append(f"{node_type}: {item_path}.component_id is not registered")
        condition = item.get("condition")
        if condition is not None:
            errors.extend(_validate_condition(node_type, condition, path=f"{item_path}.condition"))
    return errors


def _validate_condition(node_type: str, condition: Any, *, path: str) -> list[str]:
    if not isinstance(condition, dict):
        return [f"{node_type}: {path} must be an object"]
    if not str(condition.get("field") or "").strip():
        return [f"{node_type}: {path}.field is required"]
    if str(condition.get("op") or "eq") not in CONDITION_OPS:
        return [f"{node_type}: {path}.op is invalid"]
    return []
