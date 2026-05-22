import type { ReactNode } from "react";
import { Toolbar, ToolbarButton, Tooltip } from "@fluentui/react-components";
import {
  ArrowFitRegular,
  CheckmarkCircleRegular,
  PlayRegular,
  SaveRegular,
  TableLightningRegular,
  WandRegular
} from "@fluentui/react-icons";
import type { WorkflowDefinition } from "@textflow/shared-types";
import { buildWorkflowCommands, type WorkflowCommandId } from "./workflowCommands";

export function WorkflowWorkspace({
  workflow,
  loading,
  canRun,
  onSaveWorkflow,
  onRunWorkflow,
  onAutoLayout,
  onFitView,
  onValidateGraph,
  showToolbar = false,
  children
}: {
  workflow: WorkflowDefinition;
  loading: boolean;
  canRun: boolean;
  onSaveWorkflow: () => void | Promise<void>;
  onRunWorkflow: () => void | Promise<void>;
  onAutoLayout: () => void;
  onFitView: () => void;
  onValidateGraph?: () => void;
  showToolbar?: boolean;
  children: ReactNode;
}) {
  const commands = showToolbar
    ? buildWorkflowCommands({
        loading,
        canRun,
        hasNodes: workflow.nodes.length > 0
      })
    : [];

  const runCommand = (id: WorkflowCommandId) => {
    switch (id) {
      case "save_workflow":
        return onSaveWorkflow();
      case "run_workflow":
        return onRunWorkflow();
      case "auto_layout":
        return onAutoLayout();
      case "fit_view":
        return onFitView();
      case "validate_graph":
        return onValidateGraph?.();
      default:
        return undefined;
    }
  };

  return (
    <div className="workflow-workspace">
      {showToolbar && (
        <section className="workflow-workspace-toolbar" aria-label="节点图命令栏">
          <Toolbar>
            {commands.map((command) => (
              <Tooltip key={command.id} content={command.label} relationship="label">
                <ToolbarButton
                  icon={commandIcon(command.id)}
                  appearance={command.id === "run_workflow" ? "primary" : "subtle"}
                  disabled={command.disabled}
                  onClick={() => void runCommand(command.id)}
                >
                  {command.label}
                </ToolbarButton>
              </Tooltip>
            ))}
          </Toolbar>
        </section>
      )}

      {children}
    </div>
  );
}

function commandIcon(id: WorkflowCommandId) {
  switch (id) {
    case "save_workflow":
      return <SaveRegular />;
    case "run_workflow":
      return <PlayRegular />;
    case "auto_layout":
      return <WandRegular />;
    case "fit_view":
      return <ArrowFitRegular />;
    case "validate_graph":
      return <CheckmarkCircleRegular />;
    default:
      return <TableLightningRegular />;
  }
}
