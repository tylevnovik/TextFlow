from __future__ import annotations

from app.workflow.registry import builtin_node_definitions
from app.workflow.templates import build_new_flow_workflow


def _catalog_node_sizes() -> dict[str, tuple[int, int]]:
    sizes: dict[str, tuple[int, int]] = {}
    for definition in builtin_node_definitions():
        graph = definition.get("graph") if isinstance(definition.get("graph"), dict) else {}
        size = graph.get("size") if isinstance(graph.get("size"), dict) else {}
        sizes[str(definition["type"])] = (int(size["w"]), int(size["h"]))
    return sizes


def test_new_flow_workflow_positions_do_not_overlap_frontend_node_sizes():
    workflow = build_new_flow_workflow("layout-review", "Layout review")
    catalog_sizes = _catalog_node_sizes()
    rects: list[tuple[str, int, int, int, int]] = []
    for node in workflow["nodes"]:
        node_type = str(node["node_type"])
        position = node["position"]
        size = catalog_sizes.get(node_type) or (int(node["size"]["w"]), int(node["size"]["h"]))
        rects.append((node_type, int(position["x"]), int(position["y"]), size[0], size[1]))

    overlaps: list[str] = []
    for index, left in enumerate(rects):
        for right in rects[index + 1 :]:
            overlap_x = min(left[1] + left[3], right[1] + right[3]) - max(left[1], right[1])
            overlap_y = min(left[2] + left[4], right[2] + right[4]) - max(left[2], right[2])
            if overlap_x > 0 and overlap_y > 0:
                overlaps.append(f"{left[0]}<->{right[0]}:{overlap_x}x{overlap_y}")

    assert overlaps == []
