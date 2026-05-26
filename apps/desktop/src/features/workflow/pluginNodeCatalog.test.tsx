import { fireEvent, render, screen } from "@testing-library/react";
import type { RegisteredWorkflowNodeDefinition, WorkflowNodeInstance } from "@textflow/shared-types";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { demoWorkspace } from "../../data/demoProject";
import { addWorkflowNodeByType, buildBlankWorkflowFromRuntimeProfile, defaultWorkflowRuntimeProfile } from "../../workflow";
import {
  configureWorkflowNodeCatalog,
  workflowNodeDefinition,
  workflowToolboxDefinitions
} from "../../workflowNodeCatalog";
import type { WorkflowNodeEditorContext } from "../../workflowNodeRegistry";
import { DynamicNodeEditor } from "./DynamicNodeEditor";

const pluginDefinition: RegisteredWorkflowNodeDefinition = {
  type: "demo_plugin_node",
  title: "Demo Plugin Node",
  category: "analysis",
  description: "Plugin node with dynamic UI.",
  inputs: [],
  outputs: [{ port_id: "demo_table", port_type: "AnyTable", label: "Demo Table" }],
  params: [{ param_id: "limit", label: "Limit", kind: "number", default_value: 10 }],
  runtime: {
    step_id: "analysis",
    executor: "plugin.demo",
    cacheable: false,
    previewable: true,
    output_node: false
  },
  graph: {
    size: { w: 320, h: 220 },
    default_position: { x: 120, y: 220 },
    toolbox_order: 900
  },
  ui: {
    schema_version: "1.0",
    layout: [{ widget: "number", config_key: "limit", label: "Limit" }]
  }
};

function editorContextFor(node: WorkflowNodeInstance) {
  const updateNodeConfig = vi.fn();
  const context: WorkflowNodeEditorContext = {
    node,
    project: demoWorkspace.current_project!,
    snapshot: { corpus: demoWorkspace.corpus },
    draftRuntimeProfile: defaultWorkflowRuntimeProfile(),
    loading: false,
    nodeDefinitionsByType: new Map([[pluginDefinition.type, pluginDefinition]]),
    availableSources: [],
    availableInstitutions: [],
    availableCategories: [],
    documentPickerQuery: "",
    setDocumentPickerQuery: vi.fn(),
    setActivePage: vi.fn(),
    bindDictionaryTableToWorkflow: vi.fn(),
    runScopeForNode: () => ({
      mode: "all_documents",
      source_values: [],
      institution_values: [],
      category_values: [],
      year_from: null,
      year_to: null,
      selected_doc_ids: []
    }),
    runScopeSummary: () => "全部文档",
    corpusMatchesRunScope: () => true,
    updateNodeConfig,
    updateRunScope: vi.fn(),
    toggleScopeArrayValue: vi.fn(),
    toggleSelectedDocument: vi.fn(),
    enabledDictionaryEntryCount: () => 0
  };
  return { context, updateNodeConfig };
}

describe("plugin node catalog", () => {
  beforeEach(() => {
    configureWorkflowNodeCatalog([]);
  });

  it("adds plugin nodes to the toolbox and creates instances from backend metadata", () => {
    configureWorkflowNodeCatalog([pluginDefinition]);
    const runtimeProfile = defaultWorkflowRuntimeProfile();
    const workflow = buildBlankWorkflowFromRuntimeProfile("wf-plugin", "Plugin workflow", runtimeProfile);

    const updated = addWorkflowNodeByType(workflow, "demo_plugin_node", runtimeProfile);

    expect(workflowToolboxDefinitions().map((definition) => definition.type)).toEqual(["demo_plugin_node"]);
    expect(updated.nodes[0]).toMatchObject({
      node_type: "demo_plugin_node",
      label: "Demo Plugin Node",
      position: { x: 120, y: 220 },
      size: { w: 320, h: 220 },
      config: { limit: 10 }
    });
  });

  it("renders plugin node properties through the dynamic editor", () => {
    configureWorkflowNodeCatalog([pluginDefinition]);
    const runtimeProfile = defaultWorkflowRuntimeProfile();
    const workflow = buildBlankWorkflowFromRuntimeProfile("wf-plugin", "Plugin workflow", runtimeProfile);
    const node = addWorkflowNodeByType(workflow, "demo_plugin_node", runtimeProfile).nodes[0];
    const { context, updateNodeConfig } = editorContextFor(node);

    render(<DynamicNodeEditor context={context} definition={workflowNodeDefinition("demo_plugin_node") ?? undefined} />);
    fireEvent.change(screen.getByLabelText("Limit"), { target: { value: "24" } });

    expect(updateNodeConfig).toHaveBeenCalledWith(node.node_id, { limit: 24 });
  });
});
