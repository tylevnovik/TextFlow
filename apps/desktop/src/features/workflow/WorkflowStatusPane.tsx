import { ProgressBar } from "@fluentui/react-components";
import type { RunRecord, WorkflowDefinition, WorkflowNodeRuntimeState } from "@textflow/shared-types";

export function WorkflowStatusPane({
  workflow,
  validationIssues,
  latestRun,
  runtimeStates,
  progress
}: {
  workflow: WorkflowDefinition;
  validationIssues: string[];
  latestRun?: RunRecord;
  runtimeStates?: Record<string, WorkflowNodeRuntimeState>;
  progress?: number;
}) {
  const runtimeRows = workflow.nodes
    .map((node) => runtimeStates?.[node.node_id])
    .filter((state): state is WorkflowNodeRuntimeState => Boolean(state));
  const completedNodes = runtimeRows.filter((state) => state.status !== "pending" && state.status !== "running").length;
  const progressValue = progress ?? (runtimeRows.length ? completedNodes / Math.max(runtimeRows.length, 1) : 0);

  return (
    <section className="workflow-status-pane" aria-label="节点图状态">
      <div className="workflow-status-pane-head">
        <div>
          <p className="workbench-kicker">运行态</p>
          <strong>{latestRun?.status ?? "尚未运行"}</strong>
        </div>
        <span>{workflow.nodes.length} 节点</span>
      </div>
      <ProgressBar value={progressValue} thickness="medium" />
      <div className="workflow-status-pane-grid">
        <article>
          <span>连线</span>
          <strong>{workflow.edges.length}</strong>
        </article>
        <article>
          <span>校验问题</span>
          <strong>{validationIssues.length}</strong>
        </article>
        <article>
          <span>节点摘要</span>
          <strong>{latestRun?.node_runs?.length ?? runtimeRows.length}</strong>
        </article>
      </div>
    </section>
  );
}
