import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { RegisteredWorkflowNodeDefinition } from "@textflow/shared-types";
import { demoWorkspace } from "../../data/demoProject";
import { WorkflowInspector } from "./WorkflowInspector";
import { WorkflowWorkspace } from "./WorkflowWorkspace";
import { WORKFLOW_NODE_EDITOR_ACTION_EVENT } from "./workflowWorkbenchActions";

describe("WorkflowWorkspace", () => {
  it("renders workflow commands and forwards run action", () => {
    const onRunWorkflow = vi.fn();
    const project = demoWorkspace.current_project!;
    const workflow = project.workflow_definitions[0];

    render(
      <WorkflowWorkspace
        workflow={workflow}
        loading={false}
        canRun
        onSaveWorkflow={vi.fn()}
        onRunWorkflow={onRunWorkflow}
        onAutoLayout={vi.fn()}
        onFitView={vi.fn()}
        showToolbar
      >
        <div>节点画布</div>
      </WorkflowWorkspace>
    );

    expect(screen.getByRole("button", { name: "保存图" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "运行" })).toBeInTheDocument();
    expect(screen.getByText("节点画布")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "运行" }));

    expect(onRunWorkflow).toHaveBeenCalledTimes(1);
  });

  it("renders selected node parameters in workflow inspector", () => {
    const project = demoWorkspace.current_project!;
    const workflow = project.workflow_definitions[0];
    const node = workflow.nodes.find((item) => item.node_type === "clean_text")!;

    render(
      <WorkflowInspector
        selection={{
          kind: "workflow_node",
          projectId: project.id,
          workflowId: workflow.workflow_id,
          nodeId: node.node_id
        }}
        project={project}
        workflow={workflow}
      />
    );

    expect(screen.getByText("节点参数")).toBeInTheDocument();
    expect(screen.getAllByText("基础清洗").length).toBeGreaterThan(0);
    expect(screen.getByText("输入")).toBeInTheDocument();
    expect(screen.getByText("输出")).toBeInTheDocument();
  });

  it("renders editable node config in the inspector and dispatches updates", () => {
    const project = demoWorkspace.current_project!;
    const workflow = project.workflow_definitions[0];
    const node = workflow.nodes.find((item) => item.node_type === "clean_text")!;
    const listener = vi.fn();
    const cleanTextDefinition: RegisteredWorkflowNodeDefinition = {
      type: "clean_text",
      title: "基础清洗",
      category: "process",
      description: "清洗正文。",
      inputs: node.inputs,
      outputs: node.outputs,
      params: [
        { param_id: "strip_html", label: "去除 HTML", kind: "boolean", default_value: true }
      ],
      runtime: {
        step_id: "cleaning",
        executor: "textflow.clean_text",
        cacheable: true,
        previewable: true,
        output_node: false
      },
      ui: {
        schema_version: "1.0",
        layout: [{ widget: "switch", config_key: "strip_html", label: "去除 HTML" }]
      }
    };

    window.addEventListener(WORKFLOW_NODE_EDITOR_ACTION_EVENT, listener);
    render(
      <WorkflowInspector
        selection={{
          kind: "workflow_node",
          projectId: project.id,
          workflowId: workflow.workflow_id,
          nodeId: node.node_id,
          node
        }}
        project={project}
        workflow={workflow}
        snapshot={{ ...demoWorkspace, node_definitions: [cleanTextDefinition] }}
      />
    );

    fireEvent.click(screen.getByLabelText("去除 HTML"));

    expect(listener).toHaveBeenCalledTimes(1);
    expect((listener.mock.calls[0][0] as CustomEvent).detail).toMatchObject({
      type: "update_config",
      workflowId: workflow.workflow_id,
      nodeId: node.node_id,
      patch: { strip_html: false }
    });
    window.removeEventListener(WORKFLOW_NODE_EDITOR_ACTION_EVENT, listener);
  });
});
