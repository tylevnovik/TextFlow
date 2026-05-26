import { describe, expect, it } from "vitest";
import type { RegisteredWorkflowNodeDefinition, WorkflowNodeInstance } from "@textflow/shared-types";
import { demoWorkspace } from "../../data/demoProject";
import { defaultWorkflowRuntimeProfile } from "../../workflow";
import { workflowNodeConfigFacts } from "./workflowNodeConfigFacts";

describe("workflowNodeConfigFacts", () => {
  const project = demoWorkspace.current_project!;
  const workflow = project.workflow_definitions[0];
  const runtimeProfile = defaultWorkflowRuntimeProfile();

  it("summarizes dictionary input with real enabled rule counts", () => {
    const node = workflow.nodes.find((item) => item.node_type === "dictionary_input")!;
    const facts = workflowNodeConfigFacts({ node, runtimeProfile, project });

    expect(facts).toEqual(expect.arrayContaining([
      expect.objectContaining({ label: "规则", value: "8/8 类" }),
      expect.objectContaining({ label: "资源表", value: "全部表" })
    ]));
    expect(facts.find((fact) => fact.label === "词表")?.value).toContain("条启用");
  });

  it("does not mark no-parameter analysis nodes as waiting for configuration", () => {
    const baseNode = workflow.nodes.find((item) => item.node_type === "frequency_statistics")!;
    const node: WorkflowNodeInstance = {
      ...baseNode,
      node_id: "node-term-document-analysis",
      node_type: "term_document_analysis",
      label: "词项文档分析",
      config: {}
    };
    const definition: RegisteredWorkflowNodeDefinition = {
      type: node.node_type,
      title: "词项文档分析",
      category: "analysis",
      inputs: node.inputs,
      outputs: node.outputs,
      params: [],
      runtime: {
        step_id: "analysis",
        executor: "analysis.term_document",
        cacheable: true,
        previewable: true,
        output_node: false
      },
      ui: { schema_version: "1.0", layout: [] }
    };

    expect(workflowNodeConfigFacts({ node, definition, runtimeProfile, project })).toEqual([
      { label: "配置", value: "无需配置", tone: "muted" }
    ]);
  });
});
