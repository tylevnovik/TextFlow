export type WorkflowCommandId =
  | "save_workflow"
  | "run_workflow"
  | "auto_layout"
  | "fit_view"
  | "validate_graph";

export interface WorkflowCommand {
  id: WorkflowCommandId;
  label: string;
  disabled?: boolean;
}

export interface WorkflowCommandState {
  loading: boolean;
  canRun: boolean;
  hasNodes: boolean;
}

export function buildWorkflowCommands(state: WorkflowCommandState): WorkflowCommand[] {
  return [
    {
      id: "save_workflow",
      label: "保存图",
      disabled: state.loading
    },
    {
      id: "run_workflow",
      label: "运行",
      disabled: state.loading || !state.canRun
    },
    {
      id: "auto_layout",
      label: "自动布局",
      disabled: state.loading || !state.hasNodes
    },
    {
      id: "fit_view",
      label: "适配视图",
      disabled: state.loading || !state.hasNodes
    },
    {
      id: "validate_graph",
      label: "校验",
      disabled: state.loading
    }
  ];
}
