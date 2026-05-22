import { useTaskProgress, useWorkspace } from "./store/workspaceStore";
import { AppShell } from "./app/AppShell";
import { ProjectWorkbench } from "./app/ProjectWorkbench";

export function App() {
  const {
    state: { activePage, snapshot, loading, statusLine, uiScale },
    setActivePage,
    runWorkflow,
    exportProject
  } = useWorkspace();
  const progress = useTaskProgress();

  const workflowRunDetail = progress.detail?.kind === "workflow_run" ? progress.detail : undefined;
  const currentNodeLabel = workflowRunDetail?.current_node_label
    ?? (progress.detail?.kind === "node" ? progress.detail.node_label : undefined);
  const progressHeadline = workflowRunDetail?.stage === "saving"
    ? "正在整理运行结果"
    : workflowRunDetail?.stage === "exporting"
      ? "正在写出运行产物"
      : currentNodeLabel
        ? `当前节点：${currentNodeLabel}`
        : progress.message || "后台正在处理";
  const progressScopeLabel = workflowRunDetail
    ? `已完成 ${workflowRunDetail.completed_nodes}/${workflowRunDetail.total_nodes} 个节点`
    : undefined;
  const progressDetail = [progressScopeLabel, workflowRunDetail?.detail, currentNodeLabel && progress.message !== `正在执行节点：${currentNodeLabel}` ? progress.message : progress.detail?.detail]
    .filter(Boolean)
    .join(" · ");

  return (
    <AppShell uiScale={uiScale}>
      <ProjectWorkbench
        activePage={activePage}
        snapshot={snapshot}
        loading={loading}
        statusLine={statusLine}
        progress={{
          status: progress.status,
          value: progress.value,
          headline: progressHeadline,
          detail: progressDetail || undefined
        }}
        setActivePage={setActivePage}
        onRunWorkflow={() => void runWorkflow()}
        onExportArtifacts={(formats = ["csv", "xlsx", "html", "png"]) => void exportProject(formats)}
      />
    </AppShell>
  );
}
