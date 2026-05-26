from __future__ import annotations

import textwrap

from app.api.actions.dispatcher import action_get_node_catalog
from app.storage.projects import create_project, load_workspace_snapshot
from app.workflow.catalog import new_workflow_node
from app.workflow.runner import run_project_workflow


def _write_demo_plugin(plugin_root):
    plugin_root.mkdir(parents=True, exist_ok=True)
    (plugin_root / "demo_catalog_plugin.py").write_text(
        textwrap.dedent(
            """
            def _execute(_context, _node, _inputs):
                return {"demo_table": [{"term": "plugin"}]}


            def register_nodes(builder):
                builder.register_node(
                    {
                        "type": "demo_plugin_node",
                        "title": "Demo Plugin Node",
                        "category": "analysis",
                        "description": "Plugin node with dynamic UI.",
                        "inputs": [],
                        "outputs": [{"port_id": "demo_table", "port_type": "AnyTable", "label": "Demo Table"}],
                        "params": [
                            {"param_id": "limit", "label": "Limit", "kind": "number", "default_value": 10}
                        ],
                        "runtime": {
                            "step_id": "analysis",
                            "executor": "plugin.demo",
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
                            "layout": [{"widget": "number", "config_key": "limit", "label": "Limit"}],
                        },
                    },
                    executor=_execute,
                )
            """
        ),
        encoding="utf-8",
    )


def test_plugin_node_catalog_snapshot_defaults_and_runner(isolated_workspace, scratch_dir, monkeypatch):
    plugin_root = scratch_dir / "plugins" / "nodes"
    _write_demo_plugin(plugin_root)
    monkeypatch.setenv("TEXTFLOW_NODE_PLUGIN_DIR", str(plugin_root))

    catalog = action_get_node_catalog()
    plugin_definition = next(
        definition for definition in catalog["node_definitions"] if definition["type"] == "demo_plugin_node"
    )
    plugin_node = new_workflow_node("demo_plugin_node", "node-demo-plugin")
    snapshot = load_workspace_snapshot()

    assert catalog["plugin_errors"] == []
    assert plugin_definition["ui"]["layout"][0]["config_key"] == "limit"
    assert plugin_node["config"] == {"limit": 10}
    assert plugin_node["size"] == {"w": 320, "h": 220}
    assert any(definition["type"] == "demo_plugin_node" for definition in snapshot["node_definitions"])

    project_dir, manifest = create_project("plugin catalog run", "plugin node runner")
    manifest["workflow_definitions"] = [
        {
            "workflow_id": "wf-plugin-catalog",
            "name": "Plugin Catalog Workflow",
            "version": "1.0.0",
            "graph_mode": "dag",
            "source": "test",
            "meta": {},
            "nodes": [plugin_node],
            "edges": [],
            "groups": [],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
            "created_at": manifest["created_at"],
            "updated_at": manifest["updated_at"],
        }
    ]
    manifest["active_workflow_id"] = "wf-plugin-catalog"

    _updated_manifest, _corpus, run_record = run_project_workflow(project_dir, manifest, [])
    node_run = next(item for item in run_record["node_runs"] if item["node_id"] == "node-demo-plugin")

    assert run_record["status"] == "completed"
    assert node_run["output_ports"] == ["demo_table"]
    assert "demo_table" in node_run["output_summary"]
    assert any("plugin" in sample for sample in node_run["sample_outputs"])


def test_invalid_plugin_node_is_skipped_and_reported(isolated_workspace, scratch_dir, monkeypatch):
    plugin_root = scratch_dir / "plugins" / "nodes"
    plugin_root.mkdir(parents=True, exist_ok=True)
    (plugin_root / "invalid_catalog_plugin.py").write_text(
        textwrap.dedent(
            """
            def register_nodes(builder):
                builder.register_node(
                    {
                        "type": "invalid_plugin_node",
                        "title": "Invalid Plugin Node",
                        "category": "analysis",
                        "description": "Missing graph and ui.",
                        "inputs": [],
                        "outputs": [],
                        "params": [],
                        "runtime": {
                            "step_id": "analysis",
                            "executor": "plugin.invalid",
                            "cacheable": False,
                            "previewable": False,
                            "output_node": False,
                        },
                    },
                    executor=lambda *_args, **_kwargs: {},
                )
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("TEXTFLOW_NODE_PLUGIN_DIR", str(plugin_root))

    catalog = action_get_node_catalog()

    assert all(definition["type"] != "invalid_plugin_node" for definition in catalog["node_definitions"])
    assert any("invalid_catalog_plugin.py" in error for error in catalog["plugin_errors"])
    assert any("graph is required" in error for error in catalog["plugin_errors"])
