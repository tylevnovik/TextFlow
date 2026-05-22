import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { demoWorkspace } from "../../data/demoProject";
import { WorkflowInspector } from "./WorkflowInspector";
import { WorkflowWorkspace } from "./WorkflowWorkspace";

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
});
