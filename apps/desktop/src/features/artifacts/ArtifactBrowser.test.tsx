import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ArtifactRecord, ExperimentSpec, RunRecord } from "@textflow/shared-types";
import { createSimulatedRun } from "../../data/demoProject";
import type { ReviewTaskRecord } from "../review/reviewTypes";
import { ArtifactBrowser } from "./ArtifactBrowser";
import { RunHistoryPanel } from "../results/RunHistoryPanel";

describe("ArtifactBrowser", () => {
  it("loads artifact preview rows lazily", async () => {
    const artifacts: ArtifactRecord[] = [
      {
        artifact_id: "artifact-frequency",
        run_id: "run-1",
        node_id: "node-frequency",
        kind: "table",
        path: "runs/run-1/artifacts/frequency.json",
        preview_path: "runs/run-1/artifacts/frequency.preview.json",
        row_count: 2
      }
    ];
    const loadArtifactPreview = vi.fn().mockResolvedValue({
      artifact_id: "artifact-frequency",
      columns: ["term", "tf"],
      rows: [{ term: "large language model", tf: 12 }],
      row_count: 2
    });

    render(<ArtifactBrowser artifacts={artifacts} loading={false} onLoadPreview={loadArtifactPreview} />);

    expect(screen.getByText("artifact-frequency")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /加载预览/i }));

    await waitFor(() => expect(loadArtifactPreview).toHaveBeenCalledWith("artifact-frequency"));
    expect(await screen.findByText("large language model")).toBeInTheDocument();
  });
});

describe("RunHistoryPanel", () => {
  it("shows review badges and experiment links in run history", () => {
    const run = {
      ...createSimulatedRun(),
      run_id: "run-baseline",
      experiment_id: "exp-keywords",
      variant_label: "baseline"
    } as RunRecord & { experiment_id: string; variant_label: string };
    const reviewTasks: ReviewTaskRecord[] = [
      {
        review_id: "review-1",
        project_id: "project-demo",
        review_type: "keyword_merge",
        status: "open",
        target_ref: { term: "LLM" },
        title: "Merge LLM"
      }
    ];
    const experiments: ExperimentSpec[] = [
      {
        experiment_id: "exp-keywords",
        name: "Keyword variants",
        workflow_id: "workflow-default",
        variant_matrix: [{ label: "baseline", node_overrides: {} }]
      }
    ];

    render(<RunHistoryPanel runs={[run]} reviewTasks={reviewTasks} experiments={experiments} />);

    expect(screen.getByText("run-baseline")).toBeInTheDocument();
    expect(screen.getByText(/1 open review/i)).toBeInTheDocument();
    expect(screen.getByText(/Keyword variants/i)).toBeInTheDocument();
    expect(screen.getByText(/baseline/i)).toBeInTheDocument();
  });

  it("renders real artifact handles without assuming step summaries", () => {
    const run = {
      ...createSimulatedRun(),
      run_id: "run-real-artifacts",
      artifacts: [
        {
          artifact_id: "artifact-html-report",
          run_id: "run-real-artifacts",
          node_id: "node-save-html",
          kind: "export",
          path: "runs/run-real-artifacts/report/report.html",
          preview_path: "",
          row_count: 1
        }
      ]
    } as RunRecord;

    render(<RunHistoryPanel runs={[run]} reviewTasks={[]} experiments={[]} />);

    expect(screen.getByText("run-real-artifacts")).toBeInTheDocument();
    expect(screen.getByText(/node-save-html/i)).toBeInTheDocument();
    expect(screen.getByText(/runs\/run-real-artifacts\/report\/report\.html/i)).toBeInTheDocument();
  });
});
