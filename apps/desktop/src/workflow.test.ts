import type { RegisteredWorkflowNodeDefinition, WorkflowDefinition, WorkflowNodeInstance } from "@textflow/shared-types";
import { beforeEach, describe, expect, it } from "vitest";

import { configureWorkflowNodeCatalog } from "./workflowNodeCatalog";
import { validateWorkflowGraph, workflowPortCompatible } from "./workflow";
import { demoWorkspace } from "./data/demoProject";

const sourceDefinition: RegisteredWorkflowNodeDefinition = {
  type: "demo_table_source",
  title: "Demo Table Source",
  category: "analysis",
  description: "Produces a table.",
  inputs: [],
  outputs: [{ port_id: "table", port_type: "FrequencyTable", label: "Table" }],
  params: [],
  runtime: {
    step_id: "analysis",
    executor: "demo.source",
    cacheable: false,
    previewable: true,
    output_node: false
  },
  graph: {
    size: { w: 280, h: 210 },
    default_position: { x: 120, y: 220 }
  },
  ui: {
    schema_version: "1.0",
    layout: []
  }
};

const sinkDefinition: RegisteredWorkflowNodeDefinition = {
  type: "demo_output_sink",
  title: "Demo Output Sink",
  category: "output",
  description: "Consumes a table.",
  inputs: [{ port_id: "table_in", port_type: "AnyTable", label: "Table In" }],
  outputs: [{ port_id: "artifact", port_type: "ExportArtifact", label: "Artifact" }],
  params: [],
  runtime: {
    step_id: "export",
    executor: "demo.sink",
    cacheable: false,
    previewable: true,
    output_node: true
  },
  graph: {
    size: { w: 280, h: 210 },
    default_position: { x: 480, y: 220 }
  },
  ui: {
    schema_version: "1.0",
    layout: []
  }
};

function nodeFromDefinition(definition: RegisteredWorkflowNodeDefinition, nodeId: string): WorkflowNodeInstance {
  return {
    node_id: nodeId,
    node_type: definition.type,
    label: definition.title,
    position: { ...definition.graph!.default_position },
    size: { ...definition.graph!.size },
    inputs: definition.inputs.map((port) => ({ ...port })),
    outputs: definition.outputs.map((port) => ({ ...port })),
    config: {},
    ui_state: { collapsed: false, bypassed: false },
    runtime_meta: { step_id: definition.runtime.step_id, node_impl_version: "1.0.0" }
  };
}

function workflowFixture(nodes: WorkflowNodeInstance[]): WorkflowDefinition {
  return {
    workflow_id: "wf-port-compatibility",
    name: "Port compatibility",
    version: "1.0.0",
    graph_mode: "dag",
    source: "manual",
    meta: {
      template_id: "custom",
      output_bundle_id: "custom"
    },
    nodes,
    edges: [
      {
        edge_id: "edge-table-sink",
        from_node: "node-source",
        from_port: "table",
        to_node: "node-sink",
        to_port: "table_in"
      }
    ],
    groups: [],
    viewport: { x: 0, y: 0, zoom: 1 },
    created_at: "2026-05-24T00:00:00.000Z",
    updated_at: "2026-05-24T00:00:00.000Z"
  };
}

describe("workflow port compatibility", () => {
  beforeEach(() => {
    configureWorkflowNodeCatalog([]);
  });

  it("only allows exact port matches before a backend catalog is configured", () => {
    expect(workflowPortCompatible("FrequencyTable", "AnyTable")).toBe(false);
    expect(workflowPortCompatible("FrequencyTable", "FrequencyTable")).toBe(true);
  });

  it("uses backend port compatibility for generic table and renderable targets", () => {
    configureWorkflowNodeCatalog([sourceDefinition, sinkDefinition], {
      table_sources: ["FrequencyTable"],
      renderable_sources: ["FrequencyTable"],
      analysis_result_sources: ["FrequencyTable"],
      corpus_order: ["CorpusTable", "ProjectCorpus", "ScopedCorpus", "CleanCorpus", "NormalizedCorpus", "TokenCorpus", "FilteredTokenCorpus"]
    });

    expect(workflowPortCompatible("FrequencyTable", "AnyTable")).toBe(true);
    expect(workflowPortCompatible("FrequencyTable", "AnyRenderable")).toBe(true);
    expect(workflowPortCompatible("FrequencyTable", "AnyAnalysisResult")).toBe(true);
  });

  it("uses backend runtime metadata to classify custom sink nodes", () => {
    configureWorkflowNodeCatalog([sourceDefinition, sinkDefinition], {
      table_sources: ["FrequencyTable"],
      renderable_sources: [],
      analysis_result_sources: ["FrequencyTable"],
      corpus_order: []
    });
    const workflow = workflowFixture([
      nodeFromDefinition(sourceDefinition, "node-source"),
      nodeFromDefinition(sinkDefinition, "node-sink")
    ]);

    const validation = validateWorkflowGraph(workflow);

    expect(validation.sink_node_ids).toEqual(["node-sink"]);
    expect(validation.active_node_ids).toContain("node-source");
    expect(validation.active_node_ids).toContain("node-sink");
  });
});

describe("demo workflow catalog shape", () => {
  it("uses only current node types in the browser fallback project", () => {
    const unpublishedNodeTypes = new Set([
      "load_project_corpus",
      "filter_corpus",
      "project_dictionary_set",
      "analyze_corpus",
      "export_results"
    ]);
    const demoNodeTypes = demoWorkspace.current_project!.workflow_definitions
      .flatMap((workflow) => workflow.nodes.map((node) => node.node_type));

    expect(demoNodeTypes.filter((nodeType) => unpublishedNodeTypes.has(nodeType))).toEqual([]);
  });
});
