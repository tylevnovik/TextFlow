import { Toolbar, ToolbarButton, Tooltip } from "@fluentui/react-components";
import {
  ArrowDownloadRegular,
  BranchCompareRegular,
  HistoryRegular
} from "@fluentui/react-icons";
import type { ExportFormat, ProjectManifest, RunRecord } from "@textflow/shared-types";
import { coerceReviewTasks } from "../review/reviewTypes";
import { RunHistoryPanel } from "../results/RunHistoryPanel";
import { buildRunCommands, type RunCommandId } from "./runCommands";

export function RunHistoryWorkspace({
  project,
  loading,
  onSelectRun,
  onCompareRuns,
  onExportFormats
}: {
  project: ProjectManifest;
  loading: boolean;
  onSelectRun?: (run: RunRecord) => void;
  onCompareRuns?: (leftRunId: string, rightRunId: string) => void | Promise<void>;
  onExportFormats?: (formats: ExportFormat[]) => void | Promise<void>;
}) {
  const orderedRuns = [...project.run_history].reverse();
  const latestRun = orderedRuns[0];
  const previousRun = orderedRuns[1];
  const commands = buildRunCommands({
    loading,
    run: latestRun,
    canCompare: Boolean(latestRun && previousRun && onCompareRuns)
  }).filter((command) => command.id !== "open_artifact");

  const runCommand = (id: RunCommandId, formats?: ExportFormat[]) => {
    switch (id) {
      case "open_run":
        if (latestRun) {
          onSelectRun?.(latestRun);
        }
        return;
      case "compare_latest":
        if (latestRun && previousRun) {
          return onCompareRuns?.(previousRun.run_id, latestRun.run_id);
        }
        return;
      case "export_csv":
      case "export_xlsx":
      case "export_html":
      case "export_png":
        if (formats?.length) {
          return onExportFormats?.(formats);
        }
        return;
      default:
        return;
    }
  };

  return (
    <div className="run-history-workspace">
      <section className="run-workspace-toolbar" aria-label="运行命令栏">
        <Toolbar>
          {commands.map((command) => (
            <Tooltip key={command.id} content={command.label} relationship="label">
              <ToolbarButton
                icon={commandIcon(command.id)}
                appearance={command.id === "open_run" ? "primary" : "subtle"}
                disabled={command.disabled}
                onClick={() => void runCommand(command.id, command.formats)}
              >
                {command.label}
              </ToolbarButton>
            </Tooltip>
          ))}
        </Toolbar>
      </section>

      <section className="run-workspace-summary" aria-label="运行摘要">
        <article>
          <span>运行记录</span>
          <strong>{project.run_history.length}</strong>
        </article>
        <article>
          <span>最近状态</span>
          <strong>{latestRun?.status ?? "暂无"}</strong>
        </article>
        <article>
          <span>节点产物</span>
          <strong>{project.artifact_records.length}</strong>
        </article>
        <article>
          <span>审计命中</span>
          <strong>{project.results.audit_table.length}</strong>
        </article>
      </section>

      <RunHistoryPanel
        runs={project.run_history}
        reviewTasks={coerceReviewTasks(project)}
        experiments={project.experiment_specs}
        loading={loading}
        onOpenRun={onSelectRun}
        onCompareRuns={onCompareRuns}
      />
    </div>
  );
}

function commandIcon(id: RunCommandId) {
  switch (id) {
    case "open_run":
      return <HistoryRegular />;
    case "compare_latest":
      return <BranchCompareRegular />;
    default:
      return <ArrowDownloadRegular />;
  }
}
