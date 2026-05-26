import { fireEvent, render, screen } from "@testing-library/react";
import type { RegisteredWorkflowNodeDefinition, WorkflowNodeInstance } from "@textflow/shared-types";
import { describe, expect, it, vi } from "vitest";

import { demoWorkspace } from "../../data/demoProject";
import { DynamicNodeEditor } from "./DynamicNodeEditor";
import type { WorkflowNodeEditorContext } from "../../workflowNodeRegistry";

const baseDefinition: RegisteredWorkflowNodeDefinition = {
  type: "demo_dynamic",
  title: "Demo Dynamic",
  category: "analysis",
  description: "Dynamic editor fixture.",
  inputs: [],
  outputs: [],
  params: [
    { param_id: "mode", label: "Mode", kind: "enum", default_value: "basic", options: [
      { value: "basic", label: "Basic" },
      { value: "advanced", label: "Advanced" }
    ] }
  ],
  runtime: {
    step_id: "analysis",
    executor: "demo.dynamic",
    cacheable: false,
    previewable: true,
    output_node: false
  },
  ui: {
    schema_version: "1.0",
    layout: []
  }
};

function contextFor(nodePatch: Partial<WorkflowNodeInstance> = {}) {
  const updateNodeConfig = vi.fn();
  const updateRunScope = vi.fn();
  const toggleScopeArrayValue = vi.fn();
  const toggleSelectedDocument = vi.fn();
  const node: WorkflowNodeInstance = {
    node_id: "node-demo",
    node_type: "demo_dynamic",
    label: "Demo Dynamic",
    position: { x: 0, y: 0 },
    inputs: [],
    outputs: [],
    config: {
      title: "Initial",
      count: 3,
      enabled: true,
      mode: "basic"
    },
    ui_state: { collapsed: false, bypassed: false },
    runtime_meta: { step_id: "analysis", node_impl_version: "1.0.0" },
    ...nodePatch
  };
  const context: WorkflowNodeEditorContext = {
    node,
    project: demoWorkspace.current_project!,
    snapshot: { corpus: demoWorkspace.corpus },
    draftRuntimeProfile: {} as WorkflowNodeEditorContext["draftRuntimeProfile"],
    loading: false,
    nodeDefinitionsByType: new Map(),
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
    updateRunScope,
    toggleScopeArrayValue,
    toggleSelectedDocument,
    enabledDictionaryEntryCount: () => 0
  };
  return { context, updateNodeConfig, updateRunScope, toggleScopeArrayValue, toggleSelectedDocument };
}

describe("DynamicNodeEditor", () => {
  it("binds string, number, boolean and enum widgets to node config", () => {
    const definition: RegisteredWorkflowNodeDefinition = {
      ...baseDefinition,
      ui: {
        schema_version: "1.0",
        layout: [
          { widget: "text", config_key: "title", label: "Title" },
          { widget: "number", config_key: "count", label: "Count" },
          { widget: "switch", config_key: "enabled", label: "Enabled" },
          { widget: "select", config_key: "mode", label: "Mode" }
        ]
      }
    };
    const { context, updateNodeConfig } = contextFor();

    render(<DynamicNodeEditor context={context} definition={definition} />);

    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Updated" } });
    fireEvent.change(screen.getByLabelText("Count"), { target: { value: "8" } });
    fireEvent.click(screen.getByLabelText("Enabled"));
    fireEvent.change(screen.getByLabelText("Mode"), { target: { value: "advanced" } });

    expect(updateNodeConfig).toHaveBeenCalledWith("node-demo", { title: "Updated" });
    expect(updateNodeConfig).toHaveBeenCalledWith("node-demo", { count: 8 });
    expect(updateNodeConfig).toHaveBeenCalledWith("node-demo", { enabled: false });
    expect(updateNodeConfig).toHaveBeenCalledWith("node-demo", { mode: "advanced" });
  });

  it("uses the condition DSL to hide and show widgets", () => {
    const definition: RegisteredWorkflowNodeDefinition = {
      ...baseDefinition,
      ui: {
        schema_version: "1.0",
        layout: [
          { widget: "text", config_key: "visible", label: "Visible", condition: { field: "mode", op: "eq", value: "basic" } },
          { widget: "text", config_key: "hidden", label: "Hidden", condition: { field: "mode", op: "eq", value: "advanced" } }
        ]
      }
    };
    const { context } = contextFor();

    render(<DynamicNodeEditor context={context} definition={definition} />);

    expect(screen.getByLabelText("Visible")).toBeInTheDocument();
    expect(screen.queryByLabelText("Hidden")).not.toBeInTheDocument();
  });

  it("renders only whitelisted slot components", () => {
    const definition: RegisteredWorkflowNodeDefinition = {
      ...baseDefinition,
      ui: {
        schema_version: "1.0",
        layout: [
          { widget: "slot", component_id: "dictionary_binding_selector" },
          { widget: "slot", component_id: "unknown_slot" }
        ]
      }
    };
    const { context } = contextFor();

    render(<DynamicNodeEditor context={context} definition={definition} />);

    expect(screen.getByText("自定义词典")).toBeInTheDocument();
    expect(screen.getByText("未注册的属性组件：unknown_slot")).toBeInTheDocument();
  });

  it("falls back to generic param controls when layout omits a parameter", () => {
    const definition: RegisteredWorkflowNodeDefinition = {
      ...baseDefinition,
      params: [
        ...baseDefinition.params,
        { param_id: "limit", label: "Limit", kind: "number", default_value: 5 }
      ],
      ui: {
        schema_version: "1.0",
        layout: [
          { widget: "help", description: "Layout help only" }
        ]
      }
    };
    const { context, updateNodeConfig } = contextFor();

    render(<DynamicNodeEditor context={context} definition={definition} />);

    fireEvent.change(screen.getByLabelText("Limit"), { target: { value: "12" } });

    expect(screen.getByText("Layout help only")).toBeInTheDocument();
    expect(updateNodeConfig).toHaveBeenCalledWith("node-demo", { limit: 12 });
  });

  it("renders corpus scope filtering and selected document controls from the slot", () => {
    const definition: RegisteredWorkflowNodeDefinition = {
      ...baseDefinition,
      type: "corpus_input",
      params: [
        { param_id: "mode", label: "处理范围", kind: "enum", default_value: "all_documents" },
        { param_id: "year_from", label: "起始年份", kind: "number", default_value: null }
      ],
      ui: {
        schema_version: "1.0",
        layout: [{ widget: "slot", component_id: "corpus_scope_selector" }]
      }
    };
    const { context, updateRunScope, toggleScopeArrayValue, toggleSelectedDocument } = contextFor({
      node_type: "corpus_input",
      config: { mode: "filtered_subset", source_values: [] }
    });
    context.availableSources = ["Journal A"];
    context.runScopeForNode = () => ({
      mode: "filtered_subset",
      source_values: [],
      institution_values: [],
      category_values: [],
      year_from: null,
      year_to: null,
      selected_doc_ids: []
    });

    const { rerender } = render(<DynamicNodeEditor context={context} definition={definition} />);

    fireEvent.change(screen.getByLabelText("起始年"), { target: { value: "2024" } });
    fireEvent.click(screen.getByRole("button", { name: "Journal A" }));

    expect(updateRunScope).toHaveBeenCalledWith("node-demo", { year_from: 2024 });
    expect(toggleScopeArrayValue).toHaveBeenCalledWith("node-demo", "source_values", "Journal A");

    context.runScopeForNode = () => ({
      mode: "selected_documents",
      source_values: [],
      institution_values: [],
      category_values: [],
      year_from: null,
      year_to: null,
      selected_doc_ids: []
    });
    rerender(<DynamicNodeEditor context={context} definition={definition} />);

    fireEvent.click(screen.getAllByRole("checkbox")[0]);

    expect(toggleSelectedDocument).toHaveBeenCalled();
  });

  it("shows a read-only message when a node has no UI layout and no params", () => {
    const { context } = contextFor();

    render(<DynamicNodeEditor context={context} definition={{ ...baseDefinition, params: [], ui: undefined }} />);

    expect(screen.getByText("该节点没有可编辑参数")).toBeInTheDocument();
  });
});
