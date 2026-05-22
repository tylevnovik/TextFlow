import type { ExperimentSpec, RunRecord } from "@textflow/shared-types";
import { Button } from "@fluentui/react-components";
import { MiniMetric, Panel } from "../../ui";
import {
  runArtifactKey,
  runArtifactSummaryDetail,
  runArtifactSummaryLabel
} from "../../runArtifacts";
import type { ReviewTaskRecord } from "../review/reviewTypes";

type ExperimentRunRecord = RunRecord & {
  experiment_id?: string;
  experiment_name?: string;
  variant_label?: string;
};

export interface RunHistoryPanelProps {
  runs: RunRecord[];
  reviewTasks: ReviewTaskRecord[];
  experiments: ExperimentSpec[];
  loading?: boolean;
  onOpenRun?: (run: RunRecord) => void;
  onCompareRuns?: (leftRunId: string, rightRunId: string) => Promise<void> | void;
}

function experimentLabel(run: ExperimentRunRecord, experiments: ExperimentSpec[]): string | null {
  if (!run.experiment_id) {
    return null;
  }
  const experiment = experiments.find((item) => item.experiment_id === run.experiment_id);
  return experiment?.name ?? run.experiment_name ?? run.experiment_id;
}

export function RunHistoryPanel({
  runs,
  reviewTasks,
  experiments,
  loading = false,
  onOpenRun,
  onCompareRuns
}: RunHistoryPanelProps) {
  const recentRuns = runs.slice().reverse().slice(0, 24);
  const openReviewCount = reviewTasks.filter((task) => task.status === "open").length;
  const latestRun = recentRuns[0];
  const previousRun = recentRuns[1];

  return (
    <Panel
      title="历史运行记录"
      className="run-history-panel"
      actions={
        <Button
          appearance="subtle"
          onClick={() => latestRun && previousRun ? void onCompareRuns?.(previousRun.run_id, latestRun.run_id) : undefined}
          disabled={loading || !onCompareRuns || !latestRun || !previousRun}
        >
          比较最近两次
        </Button>
      }
    >
      <div className="surface-metric-row">
        <MiniMetric label="运行" value={String(runs.length)} />
        <MiniMetric label="实验" value={String(experiments.length)} />
        <MiniMetric label="复核" value={`${openReviewCount} open`} />
      </div>
      <div className="stack-list">
        {recentRuns.map((run) => {
          const extendedRun = run as ExperimentRunRecord;
          const label = experimentLabel(extendedRun, experiments);
          const showVariantLabel = extendedRun.variant_label
            && !run.run_id.toLowerCase().includes(extendedRun.variant_label.toLowerCase());
          return (
            <article key={run.run_id} className="run-card run-history-card">
              <div className="run-head">
                <strong>{run.run_id}</strong>
                <div className="button-row">
                  {onOpenRun && (
                    <Button size="small" appearance="subtle" onClick={() => onOpenRun(run)} disabled={loading}>
                      打开
                    </Button>
                  )}
                  {openReviewCount > 0 && <span className="badge warning">{openReviewCount} open review</span>}
                  <span className={`badge ${run.status}`}>{run.status}</span>
                </div>
              </div>
              <p>{run.params_snapshot_path}</p>
              <p className="muted">{run.run_scope_summary ?? "处理对象：项目内全部资料"}</p>
              <div className="run-history-tags">
                {label && <span className="pill">{label}</span>}
                {showVariantLabel && <span className="pill">{extendedRun.variant_label}</span>}
                <span className="pill">{run.processed_document_count} docs</span>
                <span className="pill">{run.artifacts.length} step artifacts</span>
              </div>
              <ul className="micro-list">
                {run.artifacts.map((artifact, index) => (
                  <li key={`${run.run_id}-${runArtifactKey(artifact, index)}`}>
                    {runArtifactSummaryLabel(artifact)}: {runArtifactSummaryDetail(artifact)}
                  </li>
                ))}
              </ul>
            </article>
          );
        })}
        {!recentRuns.length && (
          <div className="status-panel">
            <strong>还没有运行记录</strong>
            <span className="muted">运行工作流后，这里会显示审计日志、实验标签和复核提醒。</span>
          </div>
        )}
      </div>
    </Panel>
  );
}
