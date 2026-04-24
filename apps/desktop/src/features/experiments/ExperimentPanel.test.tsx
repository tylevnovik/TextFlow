/* @vitest-environment jsdom */

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ExperimentPanel } from "./ExperimentPanel";

describe("ExperimentPanel", () => {
  it("renders experiment variants and a diff summary", () => {
    render(
      <ExperimentPanel
        experiments={[
          {
            experiment_id: "exp-1",
            name: "keyword-method-compare",
            workflow_id: "wf-default",
            variant_matrix: [
              {
                label: "baseline",
                node_overrides: {}
              },
              {
                label: "high-keywords",
                node_overrides: {
                  "node-keyword-extraction": {
                    top_k_project: 24
                  }
                }
              }
            ]
          }
        ]}
        selectedExperimentId="exp-1"
        latestDiff={{
          left_run_id: "run-1",
          right_run_id: "run-2",
          summary: "analysis +5 rows"
        }}
        loading={false}
        onSelectExperiment={vi.fn()}
        onRunExperiment={vi.fn()}
      />
    );

    expect(screen.getByText("Variants")).toBeInTheDocument();
    expect(screen.getByText("high-keywords")).toBeInTheDocument();
    expect(screen.getByText("analysis +5 rows")).toBeInTheDocument();
  });
});
