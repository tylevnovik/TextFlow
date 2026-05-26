from __future__ import annotations

import os
from collections import defaultdict
from typing import Any
from ..registry import NodeRegistry, build_node_registry

UTILITY_NODE_TYPES = {"note", "group"}
DEFAULT_DAG_PARALLEL_WORKERS = 4

def _topological_active_node_batches(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    node_lookup = {str(node.get("node_id") or ""): node for node in nodes}
    node_order = {
        str(node.get("node_id") or ""): index
        for index, node in enumerate(nodes)
        if node.get("node_id")
    }
    indegree = {node_id: 0 for node_id in node_lookup}
    outgoing: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        from_node_id = str(edge.get("from_node") or "")
        to_node_id = str(edge.get("to_node") or "")
        if from_node_id not in node_lookup or to_node_id not in node_lookup:
            continue
        outgoing[from_node_id].append(to_node_id)
        indegree[to_node_id] += 1

    ready = sorted(
        [node_id for node_id, degree in indegree.items() if degree == 0],
        key=lambda node_id: node_order.get(node_id, 0),
    )
    batches: list[list[dict[str, Any]]] = []
    order_count = 0
    while ready:
        current_batch = list(ready)
        batches.append([node_lookup[node_id] for node_id in current_batch])
        order_count += len(current_batch)
        next_ready: list[str] = []
        for node_id in current_batch:
            for target_id in sorted(outgoing.get(node_id, []), key=lambda item: node_order.get(item, 0)):
                indegree[target_id] -= 1
                if indegree[target_id] == 0:
                    next_ready.append(target_id)
        ready = sorted(next_ready, key=lambda node_id: node_order.get(node_id, 0))
    if order_count != len(node_lookup):
        raise ValueError("Workflow graph contains an unsupported cycle")
    return batches


def _topological_active_nodes(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    batches = _topological_active_node_batches(nodes, edges)
    return [node for batch in batches for node in batch]


def _node_runtime_parallel_safe(definition: dict[str, Any]) -> bool:
    runtime = definition.get("runtime") if isinstance(definition.get("runtime"), dict) else {}
    if "parallel_safe" in runtime:
        return bool(runtime.get("parallel_safe"))
    category = str(definition.get("category") or "")
    node_type = str(definition.get("type") or "")
    return category in {"analysis", "output"}


def dag_parallel_worker_count(
    nodes: list[dict[str, Any]],
    definitions_by_type: dict[str, dict[str, Any]],
) -> int:
    if os.environ.get("TEXTFLOW_DISABLE_DAG_PARALLEL") == "1":
        return 1

    override = os.environ.get("TEXTFLOW_DAG_WORKERS")
    if override is not None:
        try:
            requested = max(1, int(override))
        except ValueError:
            requested = 1
        parallel_candidates = sum(
            1
            for node in nodes
            if _node_runtime_parallel_safe(definitions_by_type.get(str(node.get("node_type") or ""), {}))
        )
        return max(1, min(requested, max(parallel_candidates, 1)))

    cpu_count = os.cpu_count() or 1
    if cpu_count <= 1:
        return 1
    parallel_candidates = sum(
        1
        for node in nodes
        if _node_runtime_parallel_safe(definitions_by_type.get(str(node.get("node_type") or ""), {}))
    )
    if parallel_candidates < 2:
        return 1
    return max(1, min(parallel_candidates, min(DEFAULT_DAG_PARALLEL_WORKERS, cpu_count)))


def supports_native_execution(workflow_definition: dict[str, Any] | None, registry: NodeRegistry | None = None) -> bool:
    if not isinstance(workflow_definition, dict):
        return False
    nodes = workflow_definition.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        return False
    registry = registry or build_node_registry()
    definition_map = registry.definitions_by_type
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_type = str(node.get("node_type") or "")
        if not node_type or node_type in UTILITY_NODE_TYPES:
            continue
        definition = definition_map.get(node_type)
        if not isinstance(definition, dict):
            return False
        runtime = definition.get("runtime") if isinstance(definition.get("runtime"), dict) else {}
        executor_id = str(runtime.get("executor") or "")
        if executor_id not in registry.executors:
            return False
    return True
