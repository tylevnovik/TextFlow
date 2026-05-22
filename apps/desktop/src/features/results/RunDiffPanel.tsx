import { useEffect, useMemo, useState } from "react";
import { Button, Select } from "@fluentui/react-components";
import type { RunRecord } from "@textflow/shared-types";
import { Panel } from "../../ui";
import type { RunDiffSummary } from "../../bridge/desktopBridge";

export interface RunDiffPanelProps {
  runs: RunRecord[];
  diff?: RunDiffSummary | null;
  loading?: boolean;
  onCompareRuns: (leftRunId: string, rightRunId: string) => Promise<void> | void;
}

function runLabel(run: RunRecord): string {
  const variantLabel = (run as RunRecord & { variant_label?: string }).variant_label;
  return variantLabel ? `${variantLabel} (${run.run_id})` : run.run_id;
}

export function RunDiffPanel({ runs, diff, loading = false, onCompareRuns }: RunDiffPanelProps) {
  const orderedRuns = useMemo(() => [...runs].reverse(), [runs]);
  const [leftRunId, setLeftRunId] = useState(orderedRuns[1]?.run_id ?? orderedRuns[0]?.run_id ?? "");
  const [rightRunId, setRightRunId] = useState(orderedRuns[0]?.run_id ?? "");

  useEffect(() => {
    if (!orderedRuns.length) {
      setLeftRunId("");
      setRightRunId("");
      return;
    }
    setLeftRunId((current) => orderedRuns.some((run) => run.run_id === current) ? current : orderedRuns[1]?.run_id ?? orderedRuns[0].run_id);
    setRightRunId((current) => orderedRuns.some((run) => run.run_id === current) ? current : orderedRuns[0].run_id);
  }, [orderedRuns]);

  const canCompare = Boolean(leftRunId && rightRunId && leftRunId !== rightRunId);

  return (
    <Panel
      title="Run Diff"
      actions={
        <Button
          onClick={() => canCompare ? void onCompareRuns(leftRunId, rightRunId) : undefined}
          disabled={loading || !canCompare}
        >
          Compare
        </Button>
      }
    >
      <div className="two-column">
        <div className="stack-list">
          <label className="field">
            <span>Baseline run</span>
            <Select value={leftRunId} onChange={(event) => setLeftRunId(event.target.value)} disabled={loading || orderedRuns.length < 2}>
              {orderedRuns.map((run) => (
                <option key={`left-${run.run_id}`} value={run.run_id}>{runLabel(run)}</option>
              ))}
            </Select>
          </label>
          <label className="field">
            <span>Comparison run</span>
            <Select value={rightRunId} onChange={(event) => setRightRunId(event.target.value)} disabled={loading || orderedRuns.length < 2}>
              {orderedRuns.map((run) => (
                <option key={`right-${run.run_id}`} value={run.run_id}>{runLabel(run)}</option>
              ))}
            </Select>
          </label>
          {orderedRuns.length < 2 && (
            <div className="status-panel">
              <strong>至少需要两次运行</strong>
              <span className="muted">运行普通流程或实验矩阵后，这里会允许选择 baseline 和 comparison。</span>
            </div>
          )}
        </div>
        <div className="stack-list">
          {diff ? (
            <>
              <div className="status-panel">
                <strong>{diff.left_run_id} vs {diff.right_run_id}</strong>
                <span>{diff.summary}</span>
              </div>
              <ul className="micro-list">
                {(diff.artifact_diffs ?? []).slice(0, 8).map((artifact) => (
                  <li key={artifact.step}>
                    {artifact.step}: {artifact.record_count_delta > 0 ? "+" : ""}{artifact.record_count_delta} rows
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <div className="status-panel">
              <strong>尚未比较运行结果</strong>
              <span className="muted">选择两次运行并点击 Compare 后，会显示文档量、产物行数和输出文件差异。</span>
            </div>
          )}
        </div>
      </div>
    </Panel>
  );
}
