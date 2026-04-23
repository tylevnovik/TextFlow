/* @vitest-environment jsdom */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ReviewQueuePanel } from "./ReviewQueuePanel";
import type { ReviewTaskRecord } from "./reviewTypes";

const reviewTasks: ReviewTaskRecord[] = [
  {
    review_id: "review-1",
    project_id: "project-1",
    review_type: "keyword_merge",
    status: "open",
    target_ref: {
      source_term: "AIGC",
      target_term: "生成式 AI"
    },
    title: "合并关键词 AIGC",
    payload: {
      source_term: "AIGC",
      target_term: "生成式 AI"
    }
  }
];

describe("ReviewQueuePanel", () => {
  it("renders open review tasks and resolves one", () => {
    const onResolve = vi.fn();
    const onReject = vi.fn();

    render(
      <ReviewQueuePanel
        tasks={reviewTasks}
        onResolve={onResolve}
        onReject={onReject}
      />
    );

    expect(screen.getByText("Open")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Resolve" }));

    expect(onResolve).toHaveBeenCalledWith(
      "review-1",
      expect.objectContaining({
        decision: "resolve"
      })
    );
  });
});
