from __future__ import annotations

from pathlib import Path
import re

from app.node_definitions import build_builtin_node_definitions


NODE_KEY_PATTERN = re.compile(r"^  ([a-z_]+): \{$", re.MULTILINE)


def _workflow_node_schema_path() -> Path:
    return Path(__file__).resolve().parents[3] / "apps" / "desktop" / "src" / "generatedBuiltinWorkflowNodeSchema.ts"


def _ts_node_blocks(source: str) -> dict[str, str]:
    matches = list(NODE_KEY_PATTERN.finditer(source))
    if not matches:
        raise AssertionError("generatedBuiltinWorkflowNodeSchema.ts does not contain builtinWorkflowNodeSchema entries")
    object_end = source.index("\n};", matches[-1].end())
    blocks: dict[str, str] = {}
    for index, match in enumerate(matches):
        block_end = matches[index + 1].start() if index + 1 < len(matches) else object_end
        blocks[match.group(1)] = source[match.start():block_end]
    return blocks


def _extract_bracket_block(source: str, anchor: str) -> str:
    start = source.index(anchor)
    bracket_start = source.index("[", start)
    depth = 0
    for index in range(bracket_start, len(source)):
        char = source[index]
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return source[bracket_start : index + 1]
    raise AssertionError(f"Could not extract bracket block for anchor: {anchor}")


def _ts_port_blocks(node_block: str, field_name: str) -> list[str]:
    port_array = _extract_bracket_block(node_block, f"{field_name}:")
    return re.findall(r"\{.*?\}", port_array, re.DOTALL)


def _ts_output_port_block(node_block: str, port_id: str) -> str:
    port_match = re.search(rf"\{{\s*port_id: \"{re.escape(port_id)}\".*?\}}", node_block, re.DOTALL)
    if not port_match:
        raise AssertionError(f"generatedBuiltinWorkflowNodeSchema.ts missing output port '{port_id}' in block:\n{node_block}")
    return port_match.group(0)


def _ts_string_field(block: str, field_name: str) -> str | None:
    match = re.search(rf'{re.escape(field_name)}:\s*"([^"]*)"', block)
    return match.group(1) if match else None


def _ts_boolean_field(block: str, field_name: str) -> bool:
    return bool(re.search(rf"{re.escape(field_name)}:\s*true\b", block))


def _ts_string_array_field(block: str, field_name: str) -> list[str]:
    match = re.search(rf"{re.escape(field_name)}:\s*\[(.*?)\]", block, re.DOTALL)
    if not match:
        return []
    return re.findall(r'"([^"]+)"', match.group(1))


def _normalize_python_port(port: dict[str, object]) -> dict[str, object]:
    return {
        "port_id": str(port.get("port_id") or ""),
        "port_type": str(port.get("port_type") or ""),
        "label": str(port.get("label") or ""),
        "allow_multiple": bool(port.get("allow_multiple")),
        "result_bundle_key": str(port.get("result_bundle_key") or ""),
        "png_chart_ids": [str(item) for item in (port.get("png_chart_ids") or []) if str(item)],
        "include_in_html_audit": bool(port.get("include_in_html_audit")),
    }


def _normalize_ts_port(port_block: str) -> dict[str, object]:
    return {
        "port_id": _ts_string_field(port_block, "port_id") or "",
        "port_type": _ts_string_field(port_block, "port_type") or "",
        "label": _ts_string_field(port_block, "label") or "",
        "allow_multiple": _ts_boolean_field(port_block, "allow_multiple"),
        "result_bundle_key": _ts_string_field(port_block, "result_bundle_key") or "",
        "png_chart_ids": _ts_string_array_field(port_block, "png_chart_ids"),
        "include_in_html_audit": _ts_boolean_field(port_block, "include_in_html_audit"),
    }


def test_ts_generated_workflow_node_schema_matches_builtin_python_definitions():
    ts_source = _workflow_node_schema_path().read_text(encoding="utf-8")
    ts_node_blocks = _ts_node_blocks(ts_source)
    python_definitions = build_builtin_node_definitions()
    python_node_types = {str(definition["type"]) for definition in python_definitions}

    assert set(ts_node_blocks) == python_node_types

    for definition in python_definitions:
        node_type = str(definition["type"])
        node_block = ts_node_blocks[node_type]
        runtime = definition.get("runtime") if isinstance(definition.get("runtime"), dict) else {}

        assert _ts_string_field(node_block, "label") == str(definition.get("title") or "")
        assert _ts_string_field(node_block, "description") == str(definition.get("description") or "")
        assert _ts_string_field(node_block, "category") == str(definition.get("category") or "")
        assert _ts_boolean_field(node_block, "hidden_from_toolbox") == bool(definition.get("hidden_from_toolbox"))
        assert _ts_string_field(node_block, "stepId") == str(runtime.get("step_id") or "")

        expected_inputs = [
            _normalize_python_port(port)
            for port in (definition.get("inputs") if isinstance(definition.get("inputs"), list) else [])
            if isinstance(port, dict)
        ]
        actual_inputs = [_normalize_ts_port(port_block) for port_block in _ts_port_blocks(node_block, "inputs")]
        assert actual_inputs == expected_inputs

        outputs = definition.get("outputs") if isinstance(definition.get("outputs"), list) else []
        expected_outputs = [
            _normalize_python_port(port)
            for port in outputs
            if isinstance(port, dict)
        ]
        actual_outputs = [_normalize_ts_port(port_block) for port_block in _ts_port_blocks(node_block, "outputs")]
        assert actual_outputs == expected_outputs

        for output_port in outputs:
            if not isinstance(output_port, dict):
                continue
            port_id = str(output_port.get("port_id") or "")
            if not port_id:
                continue
            assert _normalize_ts_port(_ts_output_port_block(node_block, port_id)) == _normalize_python_port(output_port)
