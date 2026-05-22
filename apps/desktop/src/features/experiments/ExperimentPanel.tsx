import type { ExperimentSpec } from "@textflow/shared-types";
import { Button } from "@fluentui/react-components";
import { Panel } from "../../ui";
import type { RunDiffSummary } from "../../bridge/desktopBridge";

export interface ExperimentPanelProps {
  experiments: ExperimentSpec[];
  selectedExperimentId?: string | null;
  latestDiff?: Pick<RunDiffSummary, "left_run_id" | "right_run_id" | "summary"> | null;
  loading?: boolean;
  onSelectExperiment: (experimentId: string) => void;
  onRunExperiment: (experimentId: string) => Promise<void> | void;
}

function variantLabel(variant: Record<string, unknown>, index: number): string {
  return String(variant.label || `variant-${index + 1}`);
}

function overrideCount(variant: Record<string, unknown>): number {
  const overrides = variant.node_overrides;
  if (!overrides || typeof overrides !== "object" || Array.isArray(overrides)) {
    return 0;
  }
  return Object.keys(overrides).length;
}

export function ExperimentPanel({
  experiments,
  selectedExperimentId,
  latestDiff,
  loading = false,
  onSelectExperiment,
  onRunExperiment
}: ExperimentPanelProps) {
  const selectedExperiment = experiments.find((item) => item.experiment_id === selectedExperimentId) ?? experiments[0] ?? null;

  return (
    <Panel
      title="Experiment Matrix"
      actions={
        <Button
          appearance="primary"
          onClick={() => selectedExperiment ? void onRunExperiment(selectedExperiment.experiment_id) : undefined}
          disabled={loading || !selectedExperiment}
        >
          Run Matrix
        </Button>
      }
    >
      {!experiments.length ? (
        <div className="status-panel">
          <strong>还没有实验规格</strong>
          <span className="muted">保存参数矩阵后，这里会显示 variants 并可直接运行对比。</span>
        </div>
      ) : (
        <div className="two-column">
          <div className="stack-list">
            {experiments.map((experiment) => (
              <Button
                appearance="subtle"
                key={experiment.experiment_id}
                className={`project-card ${experiment.experiment_id === selectedExperiment?.experiment_id ? "is-selected" : ""}`}
                onClick={() => onSelectExperiment(experiment.experiment_id)}
                disabled={loading}
              >
                <div className="run-head">
                  <strong>{experiment.name}</strong>
                  <span className="badge completed">{experiment.variant_matrix.length} variants</span>
                </div>
                <p className="muted">{experiment.workflow_id}</p>
              </Button>
            ))}
          </div>
          <div className="stack-list">
            <div className="status-panel">
              <strong>Variants</strong>
              <ul className="micro-list">
                {(selectedExperiment?.variant_matrix ?? []).map((variant, index) => {
                  const record = variant as Record<string, unknown>;
                  return (
                    <li key={`${selectedExperiment?.experiment_id}-${variantLabel(record, index)}`}>
                      <span>{variantLabel(record, index)}</span>: {overrideCount(record)} node overrides
                    </li>
                  );
                })}
              </ul>
            </div>
            {latestDiff ? (
              <div className="status-panel">
                <strong>Latest Diff</strong>
                <span>{latestDiff.summary}</span>
                {(latestDiff.left_run_id || latestDiff.right_run_id) && (
                  <span className="muted">
                    {latestDiff.left_run_id ?? "left"} vs {latestDiff.right_run_id ?? "right"}
                  </span>
                )}
              </div>
            ) : (
              <div className="status-panel">
                <strong>尚未生成 run diff</strong>
                <span className="muted">运行两个以上 variants 后，可在下方面板选择任意两次运行做对比。</span>
              </div>
            )}
          </div>
        </div>
      )}
    </Panel>
  );
}
