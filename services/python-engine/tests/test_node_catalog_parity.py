from __future__ import annotations

from pathlib import Path
import re

from app.project_store import create_project
from app.node_definitions import build_builtin_node_definitions
from app.workflow_runner import run_project_workflow
from benchmarks import large_workflow_benchmark


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


def test_builtin_schema_includes_new_corpus_selection_nodes():
    definitions = {str(definition["type"]): definition for definition in build_builtin_node_definitions()}

    for node_type in [
        "filter_by_metadata",
        "deduplicate_documents",
        "sample_corpus",
        "split_corpus",
        "bucket_by_time",
    ]:
        assert node_type in definitions


def test_plugin_nodes_can_emit_artifact_handles(tmp_path, monkeypatch):
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    plugin_path = plugin_dir / "artifact_plugin.py"
    plugin_path.write_text(
        """
from app.node_plugins import artifact_output_port


def _execute(_context, _node, _inputs):
    return {"plugin_table": [{"term": "plugin", "score": 1.0}]}


def register_nodes(builder):
    builder.register_node(
        {
            "type": "demo_artifact_plugin",
            "title": "Demo Artifact Plugin",
            "category": "analysis",
            "description": "Emits an artifact-backed table.",
            "inputs": [],
            "outputs": [artifact_output_port("plugin_table", label="Plugin Table", artifact_kind="table")],
            "params": [],
            "runtime": {
                "step_id": "analysis",
                "executor": "plugin.demo_artifact",
                "cacheable": False,
                "previewable": True,
                "output_node": False,
            },
        },
        executor=_execute,
    )
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("TEXTFLOW_WORKSPACE_ROOT", str(tmp_path / "workspace"))
    monkeypatch.setenv("TEXTFLOW_NODE_PLUGIN_DIR", str(plugin_dir))

    project_dir, manifest = create_project("plugin-artifact-contract", "plugin artifact contract test")
    manifest["workflow_definitions"] = [
        {
            "workflow_id": "wf-plugin-artifact",
            "name": "Plugin artifact workflow",
            "version": "1.0.0",
            "graph_mode": "dag",
            "source": "test",
            "meta": {},
            "nodes": [
                {
                    "node_id": "node-plugin",
                    "node_type": "demo_artifact_plugin",
                    "label": "Demo Artifact Plugin",
                    "position": {"x": 0, "y": 0},
                    "inputs": [],
                    "outputs": [{"port_id": "plugin_table", "port_type": "AnyTable"}],
                    "config": {},
                    "ui_state": {"collapsed": False, "bypassed": False},
                    "runtime_meta": {"step_id": "analysis", "node_impl_version": "1.0.0"},
                },
                {
                    "node_id": "node-save",
                    "node_type": "save_csv",
                    "label": "Save CSV",
                    "position": {"x": 240, "y": 0},
                    "inputs": [{"port_id": "table_in", "port_type": "AnyTable"}],
                    "outputs": [{"port_id": "artifact", "port_type": "ExportArtifact"}],
                    "config": {},
                    "ui_state": {"collapsed": False, "bypassed": False},
                    "runtime_meta": {"step_id": "export", "node_impl_version": "1.0.0"},
                },
            ],
            "edges": [
                {
                    "edge_id": "edge-plugin-save",
                    "from_node": "node-plugin",
                    "from_port": "plugin_table",
                    "to_node": "node-save",
                    "to_port": "table_in",
                }
            ],
            "groups": [],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
            "created_at": manifest["created_at"],
            "updated_at": manifest["updated_at"],
        }
    ]
    manifest["active_workflow_id"] = "wf-plugin-artifact"

    updated_manifest, _corpus, run_record = run_project_workflow(project_dir, manifest, [])

    plugin_artifacts = [
        record
        for record in updated_manifest.get("artifact_records", [])
        if record.get("node_id") == "node-plugin"
    ]
    assert run_record["status"] == "completed"
    assert plugin_artifacts
    assert plugin_artifacts[0]["kind"] == "table"
    assert any(handle.get("node_id") == "node-plugin" for handle in run_record.get("artifacts", []))


def test_benchmark_workflow_runs_with_artifact_store_enabled():
    benchmark_source = Path(large_workflow_benchmark.__file__).read_text(encoding="utf-8")

    assert large_workflow_benchmark.BENCHMARK_REQUIRES_ARTIFACT_STORE is True
    assert '"artifact_store_enabled": True' in benchmark_source
    assert '"artifact_record_count": len(manifest.get("artifact_records", []))' in benchmark_source
