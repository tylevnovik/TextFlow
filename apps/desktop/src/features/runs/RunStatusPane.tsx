import { Button, ProgressBar } from "@fluentui/react-components";
import { PanelBottomRegular } from "@fluentui/react-icons";
import type { ArtifactRecord, RunRecord, WorkspaceSnapshot } from "@textflow/shared-types";
import type { WorkbenchBottomTab } from "../../app/workbenchLayoutState";

export interface RunProgressInfo {
  status: "idle" | "pending" | "running" | "completed" | "failed";
  value: number;
  headline: string;
  detail?: string;
}

export function RunStatusPane({
  activeTab,
  onTabChange,
  snapshot,
  progress,
  onOpenRun,
  onOpenArtifact,
  onCollapse
}: {
  activeTab: WorkbenchBottomTab;
  onTabChange: (tab: WorkbenchBottomTab) => void;
  snapshot: WorkspaceSnapshot;
  progress: RunProgressInfo;
  onOpenRun?: (run: RunRecord) => void;
  onOpenArtifact?: (artifact: ArtifactRecord) => void;
  onCollapse?: () => void;
}) {
  const project = snapshot.current_project;
  const latestRun = latestProjectRun(project?.run_history ?? []);
  const nodeRuns = latestRun?.node_runs ?? [];
  const artifacts = latestRun
    ? (project?.artifact_records.filter((artifact) => artifact.run_id === latestRun.run_id) ?? [])
    : (project?.artifact_records ?? []);
  const recentArtifacts = (artifacts.length ? artifacts : project?.artifact_records ?? []).slice(-8).reverse();
  const warnings = latestRun?.warnings ?? [];
  const errors = latestRun?.errors ?? [];
  const failedNodes = nodeRuns.filter((nodeRun) => nodeRun.status === "failed");

  return (
    <section className="workbench-bottom-pane run-status-pane" aria-label="运行状态面板">
      <div className="workbench-bottom-header">
        <div className="workbench-bottom-tablist" role="tablist" aria-label="运行状态视图">
          <BottomTabButton activeTab={activeTab} tab="progress" label="进度" ariaLabel="运行进度" onTabChange={onTabChange} />
          <BottomTabButton activeTab={activeTab} tab="logs" label="日志" ariaLabel="节点日志" onTabChange={onTabChange} />
          <BottomTabButton activeTab={activeTab} tab="issues" label="问题" ariaLabel="校验问题" onTabChange={onTabChange} />
          <BottomTabButton activeTab={activeTab} tab="artifacts" label="产物" ariaLabel="产物列表" onTabChange={onTabChange} />
        </div>
        {onCollapse && (
          <Button
            appearance="subtle"
            size="small"
            aria-label="折叠底部面板"
            title="折叠底部面板"
            icon={<PanelBottomRegular />}
            onClick={onCollapse}
          />
        )}
      </div>
      <div className="workbench-bottom-content">
        {activeTab === "progress" && (
          <div className="run-status-stack">
            <div className="run-status-progress">
              <div className="workbench-progress-copy">
                <strong>{progress.status === "idle" ? "空闲" : progress.headline}</strong>
                <span>{Math.round(progress.value * 100)}%</span>
              </div>
              <ProgressBar value={progress.value} thickness="medium" />
              {progress.detail && <p>{progress.detail}</p>}
            </div>
            <StatusStrip
              rows={[
                ["最近运行", latestRun?.status ?? "暂无运行", latestRun ? () => onOpenRun?.(latestRun) : undefined],
                ["运行节点", `${nodeRuns.length} 个摘要`],
                ["产物", `${project?.artifact_records.length ?? 0} 个`],
                ["审计命中", `${project?.results.audit_table.length ?? 0} 条`]
              ]}
            />
          </div>
        )}
        {activeTab === "logs" && (
          <div className="workbench-log-list">
            {nodeRuns.slice(-8).reverse().map((nodeRun) => (
              <button
                type="button"
                key={`${nodeRun.node_id}-${nodeRun.started_at}`}
                className="workbench-log-row"
                onClick={() => latestRun && onOpenRun?.(latestRun)}
                disabled={!latestRun || !onOpenRun}
              >
                <strong>{nodeRun.label}</strong>
                <span>{nodeRun.status} · {nodeRun.output_summary || nodeRun.error || "暂无输出摘要"}</span>
              </button>
            ))}
            {!nodeRuns.length && latestRun?.logs.slice(-8).reverse().map((log) => (
              <button
                type="button"
                key={`${log.timestamp}-${log.step}-${log.message}`}
                className="workbench-log-row"
                onClick={() => onOpenRun?.(latestRun)}
                disabled={!onOpenRun}
              >
                <strong>{log.step}</strong>
                <span>{log.level} · {log.message}</span>
              </button>
            ))}
            {!nodeRuns.length && !latestRun?.logs.length && <p>还没有节点日志。运行节点图后这里会显示最近节点状态。</p>}
          </div>
        )}
        {activeTab === "issues" && (
          <div className="run-status-stack">
            <StatusStrip
              rows={[
                ["错误", `${errors.length}`],
                ["警告", `${warnings.length}`],
                ["失败节点", `${failedNodes.length}`],
                ["规则审计", `${project?.results.audit_table.length ?? 0} 条命中`]
              ]}
            />
            <div className="workbench-log-list">
              {[...errors, ...warnings].slice(0, 8).map((message, index) => (
                <p key={`${message}-${index}`}>
                  <strong>{index < errors.length ? "错误" : "警告"}</strong>
                  <span>{message}</span>
                </p>
              ))}
              {!errors.length && !warnings.length && <p>当前最近运行没有错误或警告。</p>}
            </div>
          </div>
        )}
        {activeTab === "artifacts" && (
          <div className="workbench-artifact-strip">
            {recentArtifacts.map((artifact) => (
              <button
                type="button"
                key={artifact.artifact_id}
                className="workbench-artifact-card"
                onClick={() => onOpenArtifact?.(artifact)}
                disabled={!onOpenArtifact}
              >
                <strong>{artifact.artifact_id}</strong>
                <span>{artifact.node_id} · {artifact.kind} · {artifact.row_count ?? "未知"} 行</span>
              </button>
            ))}
            {!recentArtifacts.length && <p>暂无产物。输出节点运行后会在这里出现表格、图表或报告。</p>}
          </div>
        )}
      </div>
    </section>
  );
}

function BottomTabButton({
  activeTab,
  tab,
  label,
  ariaLabel,
  onTabChange
}: {
  activeTab: WorkbenchBottomTab;
  tab: WorkbenchBottomTab;
  label: string;
  ariaLabel: string;
  onTabChange: (tab: WorkbenchBottomTab) => void;
}) {
  const selected = activeTab === tab;
  return (
    <Button
      appearance={selected ? "primary" : "subtle"}
      size="small"
      role="tab"
      aria-label={ariaLabel}
      aria-selected={selected}
      tabIndex={selected ? 0 : -1}
      onClick={() => onTabChange(tab)}
    >
      {label}
    </Button>
  );
}

function latestProjectRun(runs: RunRecord[]): RunRecord | undefined {
  return runs.at(-1) ?? runs[0];
}

function StatusStrip({ rows }: { rows: Array<[string, string, (() => void)?]> }) {
  return (
    <div className="workbench-status-strip">
      {rows.map(([label, value, onClick]) => {
        const content = (
          <>
            <span>{label}</span>
            <strong>{value}</strong>
          </>
        );

        return onClick ? (
          <button type="button" key={label} onClick={onClick} className="workbench-status-card">
            {content}
          </button>
        ) : (
          <article key={label}>
            {content}
          </article>
        );
      })}
    </div>
  );
}
