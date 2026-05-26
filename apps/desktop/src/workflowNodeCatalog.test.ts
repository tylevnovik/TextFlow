import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { RegisteredWorkflowNodeDefinition } from "@textflow/shared-types";
import { beforeEach, describe, expect, it } from "vitest";

import { addWorkflowNodeByType, buildBlankWorkflowFromRuntimeProfile, defaultWorkflowRuntimeProfile } from "./workflow";
import {
  configureWorkflowNodeCatalog,
  portCompatibilityRules,
  workflowNodeDefaultConfig,
  workflowNodeDefaultPosition,
  workflowNodeDefinition,
  workflowNodeFrameForType,
  workflowToolboxDefinitions
} from "./workflowNodeCatalog";

const saveXlsxDefinition: RegisteredWorkflowNodeDefinition = {
  type: "save_xlsx",
  title: "保存 XLSX",
  category: "output",
  description: "把上游表格结果整理成 Excel 文件。",
  inputs: [{ port_id: "table_in", port_type: "AnyTable", label: "表格输入", allow_multiple: true }],
  outputs: [{ port_id: "artifact", port_type: "ExportArtifact", label: "导出产物" }],
  params: [
    { param_id: "file_prefix", label: "文件名前缀", kind: "string", default_value: "tables" },
    { param_id: "export_xlsx", label: "启用 Excel 导出", kind: "boolean", default_value: true }
  ],
  runtime: {
    step_id: "export",
    executor: "export.save_xlsx",
    cacheable: false,
    previewable: true,
    output_node: true
  },
  graph: {
    size: { w: 280, h: 210 },
    default_position: { x: 5340, y: 360 },
    toolbox_order: 420
  },
  ui: {
    schema_version: "1.0",
    layout: [{ widget: "text", config_key: "file_prefix", label: "文件名前缀" }]
  }
};

describe("workflowNodeCatalog", () => {
  beforeEach(() => {
    configureWorkflowNodeCatalog([]);
  });

  it("starts empty until backend definitions are configured", () => {
    expect(workflowToolboxDefinitions()).toEqual([]);
    expect(workflowNodeDefinition("save_xlsx")).toBeNull();
  });

  it("derives frame, position, toolbox and default config from backend definitions", () => {
    configureWorkflowNodeCatalog([saveXlsxDefinition]);

    expect(workflowNodeFrameForType("save_xlsx")).toEqual({ w: 280, h: 210 });
    expect(workflowNodeDefaultPosition("save_xlsx")).toEqual({ x: 5340, y: 360 });
    expect(workflowNodeDefaultConfig(workflowNodeDefinition("save_xlsx"))).toEqual({
      file_prefix: "tables",
      export_xlsx: true
    });
    expect(workflowToolboxDefinitions().map((definition) => definition.type)).toEqual(["save_xlsx"]);
  });

  it("does not invent aggregate analysis bundle compatibility without a backend node", () => {
    configureWorkflowNodeCatalog([saveXlsxDefinition]);

    expect(portCompatibilityRules().renderable_sources).not.toContain("AnalysisBundle");
    expect(portCompatibilityRules().analysis_result_sources).not.toContain("AnalysisBundle");
  });

  it("creates workflow nodes from backend catalog definitions", () => {
    configureWorkflowNodeCatalog([saveXlsxDefinition]);
    const runtimeProfile = defaultWorkflowRuntimeProfile();
    const workflow = buildBlankWorkflowFromRuntimeProfile("wf-test", "Test", runtimeProfile);

    const updated = addWorkflowNodeByType(workflow, "save_xlsx", runtimeProfile);

    expect(updated.nodes).toHaveLength(1);
    expect(updated.nodes[0]).toMatchObject({
      node_type: "save_xlsx",
      label: "保存 XLSX",
      position: { x: 5340, y: 360 },
      size: { w: 280, h: 210 },
      config: {
        file_prefix: "tables",
        export_xlsx: true
      }
    });
  });

  it("keeps static builtin node schema out of frontend catalog scaffolding", () => {
    const catalogSource = readFileSync(resolve(__dirname, "workflowNodeCatalog.ts"), "utf-8");
    const registrySource = readFileSync(resolve(__dirname, "workflowNodeRegistry.tsx"), "utf-8");

    expect(catalogSource).not.toContain(`save_${"xlsx"}:`);
    expect(catalogSource).not.toContain(`corpus_${"input"}:`);
    expect(catalogSource).not.toContain(`generated${"BuiltinWorkflowNodeSchema"}`);
    expect(registrySource).not.toContain(`workflowNode${"InlineRenderers"}`);
  });
});
