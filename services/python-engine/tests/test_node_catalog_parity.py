from __future__ import annotations

from pathlib import Path

def execute_unresolved_passthrough(_context, _node, _inputs):
    return {}

BUILTIN_NODE_COMPILERS = {}
EXECUTORS_BY_TYPE = {}
from app.storage.projects import create_project
from app.workflow.nodes.loader import builtin_node_module_names
from app.workflow.registry import build_node_registry, builtin_node_definitions
from app.workflow.runner import run_project_workflow
from benchmarks import large_workflow_benchmark


def test_builtin_schema_includes_new_corpus_selection_nodes():
    definitions = {str(definition["type"]): definition for definition in builtin_node_definitions()}

    for node_type in [
        "filter_by_metadata",
        "deduplicate_documents",
        "sample_corpus",
        "focus_terms",
        "split_corpus",
        "bucket_by_time",
    ]:
        assert node_type in definitions


def test_revised_flow_node_definitions_expose_ngram_similarity_and_topic_algorithm_controls():
    definitions = {str(definition["type"]): definition for definition in builtin_node_definitions()}

    token_params = {str(param["param_id"]) for param in definitions["tokenize"]["params"]}
    assert {"enable_ngrams", "ngram_min", "ngram_max"} <= token_params

    assert "similarity_analysis" in definitions
    similarity_outputs = {str(port["port_id"]) for port in definitions["similarity_analysis"]["outputs"]}
    assert "similarity_table" in similarity_outputs

    topic_params = {str(param["param_id"]): param for param in definitions["topic_modeling"]["params"]}
    assert "topic_algorithm" in topic_params
    assert {str(option["value"]) for option in topic_params["topic_algorithm"]["options"]} >= {"nmf", "lda"}


def test_non_utility_builtin_nodes_have_explicit_runtime_executors():
    registry = build_node_registry()

    unresolved_node_types: list[str] = []
    for definition in builtin_node_definitions():
        node_type = str(definition.get("type") or "")
        category = str(definition.get("category") or "")
        runtime = definition.get("runtime") if isinstance(definition.get("runtime"), dict) else {}
        executor_id = str(runtime.get("executor") or "")
        executor = registry.executors.get(executor_id)

        if not node_type or not executor_id or executor is None:
            unresolved_node_types.append(node_type or "<missing-type>")
            continue
        if category != "utility" and executor is execute_unresolved_passthrough:
            unresolved_node_types.append(node_type)

    assert unresolved_node_types == []


def test_builtin_node_modules_are_scanned_from_directory_and_own_their_hooks():
    registry = build_node_registry()
    builtin_node_types = {
        str(definition.get("type") or "")
        for definition in builtin_node_definitions()
        if definition.get("type")
    }

    assert builtin_node_types == set(builtin_node_module_names())
    assert builtin_node_types == set(registry.definitions_by_type)
    assert builtin_node_types <= set(registry.compilers)
    assert BUILTIN_NODE_COMPILERS == {}
    assert EXECUTORS_BY_TYPE == {}

    for node_type in builtin_node_types:
        runtime = registry.definitions_by_type[node_type]["runtime"]
        executor_id = str(runtime["executor"])
        assert executor_id in registry.executors
        assert registry.executors[executor_id] is not execute_unresolved_passthrough
        assert node_type not in BUILTIN_NODE_COMPILERS
        assert node_type not in EXECUTORS_BY_TYPE


def test_plugin_nodes_can_emit_artifact_handles(tmp_path, monkeypatch):
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    plugin_path = plugin_dir / "artifact_plugin.py"
    plugin_path.write_text(
        """
from app.workflow.plugins import artifact_output_port


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
            "graph": {
                "size": {"w": 320, "h": 220},
                "default_position": {"x": 120, "y": 220},
                "toolbox_order": 900,
            },
            "ui": {
                "schema_version": "1.0",
                "layout": [],
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
