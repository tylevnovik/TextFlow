import type { WorkflowNodeType } from "@textflow/shared-types";

export const WORKFLOW_WORKBENCH_ACTION_EVENT = "textflow:workflow-workbench-action";
export const WORKFLOW_NODE_TYPE_MIME = "application/x-textflow-workflow-node-type";

export type WorkflowWorkbenchCanvasAction =
  | "insert_recommended_starter"
  | "restore_recommended_edges"
  | "auto_layout"
  | "fit_view"
  | "validate_graph"
  | "clear_canvas";

export type WorkflowWorkbenchAction =
  | { type: "add_node"; nodeType: WorkflowNodeType }
  | { type: "canvas"; action: WorkflowWorkbenchCanvasAction };
