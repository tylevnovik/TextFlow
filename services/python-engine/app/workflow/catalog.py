from __future__ import annotations

from copy import deepcopy
from typing import Any

from .registry import builtin_node_definitions
from .schema import default_config_from_params


def definition_by_type(runtime_profile: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    return {
        str(definition["type"]): definition
        for definition in builtin_node_definitions(runtime_profile)
        if definition.get("type")
    }


def default_node_config(definition: dict[str, Any]) -> dict[str, Any]:
    return default_config_from_params(definition)


def catalog_position(node_type: str, runtime_profile: dict[str, Any] | None = None) -> dict[str, int]:
    definition = definition_by_type(runtime_profile)[node_type]
    graph = definition.get("graph") if isinstance(definition.get("graph"), dict) else {}
    position = graph.get("default_position") if isinstance(graph.get("default_position"), dict) else {}
    return {"x": int(position.get("x", 0) or 0), "y": int(position.get("y", 0) or 0)}


def catalog_size(node_type: str, runtime_profile: dict[str, Any] | None = None) -> dict[str, int]:
    definition = definition_by_type(runtime_profile)[node_type]
    graph = definition.get("graph") if isinstance(definition.get("graph"), dict) else {}
    size = graph.get("size") if isinstance(graph.get("size"), dict) else {}
    return {"w": int(size.get("w", 280) or 280), "h": int(size.get("h", 210) or 210)}


def new_workflow_node(
    node_type: str,
    node_id: str,
    runtime_profile: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    definition = definition_by_type(runtime_profile)[node_type]
    runtime = definition.get("runtime") if isinstance(definition.get("runtime"), dict) else {}
    return {
        "node_id": node_id,
        "node_type": node_type,
        "label": str(definition.get("title") or node_type),
        "position": catalog_position(node_type, runtime_profile),
        "size": catalog_size(node_type, runtime_profile),
        "inputs": deepcopy(definition.get("inputs") if isinstance(definition.get("inputs"), list) else []),
        "outputs": deepcopy(definition.get("outputs") if isinstance(definition.get("outputs"), list) else []),
        "config": {
            **default_node_config(definition),
            **deepcopy(config or {}),
        },
        "ui_state": {"collapsed": False, "bypassed": False},
        "runtime_meta": {
            "step_id": str(runtime.get("step_id") or definition.get("category") or "manual"),
            "node_impl_version": "2.0.0",
        },
    }
