from __future__ import annotations

from pathlib import Path
import re

from app.new_flow_workflow import build_new_flow_workflow


def _frontend_node_sizes() -> dict[str, tuple[int, int]]:
    catalog_path = Path(__file__).resolve().parents[3] / "apps" / "desktop" / "src" / "workflowNodeCatalog.ts"
    sizes: dict[str, tuple[int, int]] = {}
    current: str | None = None
    for line in catalog_path.read_text(encoding="utf-8").splitlines():
        node_match = re.match(r"^  ([a-zA-Z0-9_]+): \{$", line)
        if node_match:
            current = node_match.group(1)
            continue
        if current is None:
            continue
        size_match = re.match(r"^    size: \{ w: (\d+), h: (\d+) \},?$", line)
        if size_match:
            sizes[current] = (int(size_match.group(1)), int(size_match.group(2)))
        if line.startswith("  },") or line.startswith("  }"):
            current = None
    return sizes


def test_new_flow_workflow_positions_do_not_overlap_frontend_node_sizes():
    workflow = build_new_flow_workflow("layout-review", "Layout review")
    frontend_sizes = _frontend_node_sizes()
    rects: list[tuple[str, int, int, int, int]] = []
    for node in workflow["nodes"]:
        node_type = str(node["node_type"])
        position = node["position"]
        size = frontend_sizes.get(node_type) or (int(node["size"]["w"]), int(node["size"]["h"]))
        rects.append((node_type, int(position["x"]), int(position["y"]), size[0], size[1]))

    overlaps: list[str] = []
    for index, left in enumerate(rects):
        for right in rects[index + 1 :]:
            overlap_x = min(left[1] + left[3], right[1] + right[3]) - max(left[1], right[1])
            overlap_y = min(left[2] + left[4], right[2] + right[4]) - max(left[2], right[2])
            if overlap_x > 0 and overlap_y > 0:
                overlaps.append(f"{left[0]}<->{right[0]}:{overlap_x}x{overlap_y}")

    assert overlaps == []
