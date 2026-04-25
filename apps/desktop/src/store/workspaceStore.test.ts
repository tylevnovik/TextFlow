import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ProjectManifest, RunRecord, WorkflowNodeRuntimeState } from "@textflow/shared-types";
import type { EngineProgressEvent } from "../bridge/desktopBridge";
import { createSimulatedRun, demoWorkspace } from "../data/demoProject";

const { desktopBridgeMock } = vi.hoisted(() => ({
  desktopBridgeMock: {
    loadWorkspace: vi.fn(),
    subscribeProgress: vi.fn(),
    runWorkflow: vi.fn(),
  }
}));

vi.mock("../bridge/desktopBridge", () => ({
  desktopBridge: desktopBridgeMock,
}));

import { WorkspaceProvider, useTaskProgress, useWorkspace, workspaceStoreTestables } from "./workspaceStore";

function cloneJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function runtimeState(
  nodeId: string,
  label: string,
  status: WorkflowNodeRuntimeState["status"],
  nodeIndex: number,
  overrides: Partial<WorkflowNodeRuntimeState> = {}
): WorkflowNodeRuntimeState {
  return {
    node_id: nodeId,
    node_type: overrides.node_type ?? "clean_text",
    label,
    status,
    node_index: nodeIndex,
    total_nodes: 2,
    progress: status === "running" ? 0.6 : 1,
    detail: status === "running" ? `正在执行节点：${label}` : `${label} 已完成`,
    output_summary: overrides.output_summary ?? "",
    ...overrides
  };
}

function workflowRunDetail(
  overrides: Partial<Extract<NonNullable<EngineProgressEvent["detail"]>, { kind: "workflow_run" }>> = {}
): Extract<NonNullable<EngineProgressEvent["detail"]>, { kind: "workflow_run" }> {
  return {
    kind: "workflow_run",
    run_id: "run-progress",
    workflow_id: "wf-default",
    workflow_name: "关键词与主题工作流",
    stage: "running",
    total_nodes: 2,
    completed_nodes: 0,
    current_node_id: "node-clean",
    current_node_label: "基础清洗",
    current_node_index: 1,
    last_completed_node_id: undefined,
    detail: "正在执行节点：基础清洗",
    node_states: {},
    node_state_delta: {},
    full_node_state_sync: true,
    ...overrides
  };
}

function ProgressProbe() {
  const progress = useTaskProgress();
  const { runWorkflow } = useWorkspace();

  return createElement(
    "div",
    null,
    createElement(
      "button",
      {
        type: "button",
        onClick: () => {
          void runWorkflow();
        }
      },
      "run workflow"
    ),
    createElement("pre", { "data-testid": "progress" }, JSON.stringify(progress))
  );
}

function readProgress(): {
  action: string;
  status: string;
  value: number;
  message: string;
  detail?: Extract<NonNullable<EngineProgressEvent["detail"]>, { kind: "workflow_run" }>;
} {
  return JSON.parse(screen.getByTestId("progress").textContent || "{}") as {
    action: string;
    status: string;
    value: number;
    message: string;
    detail?: Extract<NonNullable<EngineProgressEvent["detail"]>, { kind: "workflow_run" }>;
  };
}

function completedRunWithNodeStates(): RunRecord {
  const run = createSimulatedRun();
  run.run_id = "run-missing-final-event";
  run.workflow_id = demoWorkspace.current_project!.active_workflow_id;
  run.workflow_name = demoWorkspace.current_project!.workflow_definitions[0].name;
  run.node_runs = [
    {
      node_id: "node-clean",
      node_type: "clean_text",
      label: "基础清洗",
      status: "completed",
      started_at: "2026-04-25T16:20:00+08:00",
      ended_at: "2026-04-25T16:20:01+08:00",
      duration_ms: 150,
      cache_hit: false,
      output_ports: ["clean_corpus"],
      output_summary: "120 条记录",
      sample_outputs: []
    },
    {
      node_id: "node-tokenize",
      node_type: "tokenize",
      label: "切词",
      status: "completed",
      started_at: "2026-04-25T16:20:01+08:00",
      ended_at: "2026-04-25T16:20:03+08:00",
      duration_ms: 420,
      cache_hit: false,
      output_ports: ["token_corpus"],
      output_summary: "120 条记录",
      sample_outputs: []
    }
  ];
  return run;
}

describe("workspaceStore workflow progress", () => {
  let progressListener: ((event: EngineProgressEvent) => void) | null = null;

  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    progressListener = null;
    desktopBridgeMock.loadWorkspace.mockResolvedValue(cloneJson(demoWorkspace));
    desktopBridgeMock.subscribeProgress.mockImplementation(async (listener: (event: EngineProgressEvent) => void) => {
      progressListener = listener;
      return () => {
        progressListener = null;
      };
    });
    desktopBridgeMock.runWorkflow.mockResolvedValue({
      run: completedRunWithNodeStates(),
      project: cloneJson(demoWorkspace.current_project!),
    });
  });

  it("merges workflow state deltas without losing completed nodes", () => {
    const previous = workflowRunDetail({
      completed_nodes: 1,
      current_node_id: "node-tokenize",
      current_node_label: "切词",
      current_node_index: 2,
      node_states: {
        "node-clean": runtimeState("node-clean", "基础清洗", "completed", 1),
        "node-tokenize": runtimeState("node-tokenize", "切词", "running", 2, { node_type: "tokenize", progress: 0.25 })
      }
    });
    const incoming = workflowRunDetail({
      completed_nodes: 1,
      current_node_id: "node-tokenize",
      current_node_label: "切词",
      current_node_index: 2,
      node_states: {},
      node_state_delta: {
        "node-tokenize": runtimeState("node-tokenize", "切词", "running", 2, { node_type: "tokenize", progress: 0.75 })
      },
      full_node_state_sync: false
    });

    const merged = workspaceStoreTestables.mergeWorkflowRunDetail(previous, incoming);
    expect(merged?.kind).toBe("workflow_run");
    if (merged?.kind !== "workflow_run") {
      throw new Error("Expected workflow_run detail");
    }
    expect(merged.node_states["node-clean"].status).toBe("completed");
    expect(merged.node_states["node-tokenize"].status).toBe("running");
    expect(merged.node_states["node-tokenize"].progress).toBe(0.75);
  });

  it("replaces stale node states when a full sync arrives", () => {
    const previous = workflowRunDetail({
      node_states: {
        "node-stale": runtimeState("node-stale", "旧节点", "completed", 1),
        "node-clean": runtimeState("node-clean", "基础清洗", "completed", 1)
      }
    });
    const incoming = workflowRunDetail({
      current_node_id: "node-tokenize",
      current_node_label: "切词",
      current_node_index: 2,
      node_states: {
        "node-clean": runtimeState("node-clean", "基础清洗", "completed", 1),
        "node-tokenize": runtimeState("node-tokenize", "切词", "running", 2, { node_type: "tokenize", progress: 0.4 })
      },
      node_state_delta: {},
      full_node_state_sync: true
    });

    const merged = workspaceStoreTestables.mergeWorkflowRunDetail(previous, incoming);
    expect(merged?.kind).toBe("workflow_run");
    if (merged?.kind !== "workflow_run") {
      throw new Error("Expected workflow_run detail");
    }
    expect(merged.node_states["node-stale"]).toBeUndefined();
    expect(merged.node_states["node-tokenize"].status).toBe("running");
  });

  it("marks the active node completed when the final workflow detail is missing", () => {
    const previousState = {
      action: "run-workflow",
      status: "running" as const,
      value: 0.92,
      message: "正在执行节点：切词",
      detail: workflowRunDetail({
        completed_nodes: 1,
        current_node_id: "node-tokenize",
        current_node_label: "切词",
        current_node_index: 2,
        last_completed_node_id: "node-clean",
        node_states: {
          "node-clean": runtimeState("node-clean", "基础清洗", "completed", 1),
          "node-tokenize": runtimeState("node-tokenize", "切词", "running", 2, { node_type: "tokenize", progress: 0.9 })
        }
      })
    };

    const detail = workspaceStoreTestables.normalizeProgressDetail(
      {
        action: "run-workflow",
        status: "completed",
        progress: 1,
        message: "运行流程完成"
      },
      previousState
    );

    expect(detail?.kind).toBe("workflow_run");
    if (detail?.kind !== "workflow_run") {
      throw new Error("Expected workflow_run detail");
    }
    expect(detail.stage).toBe("completed");
    expect(detail.completed_nodes).toBe(2);
    expect(detail.current_node_id).toBeUndefined();
    expect(detail.node_states["node-tokenize"].status).toBe("completed");
    expect(detail.node_states["node-tokenize"].progress).toBe(1);
  });

  it("falls back to the resolved run record when the final progress event never arrives", async () => {
    const responseRun = completedRunWithNodeStates();
    const responseProject = cloneJson(demoWorkspace.current_project!) as ProjectManifest;
    responseProject.run_history = [...responseProject.run_history, cloneJson(responseRun)];

    let resolveRun:
      | ((value: { run: RunRecord; project: ProjectManifest }) => void)
      | null = null;
    desktopBridgeMock.runWorkflow.mockImplementation(
      () =>
        new Promise<{ run: RunRecord; project: ProjectManifest }>((resolve) => {
          resolveRun = resolve;
        })
    );

    render(createElement(WorkspaceProvider, null, createElement(ProgressProbe)));

    await waitFor(() => expect(desktopBridgeMock.loadWorkspace).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(desktopBridgeMock.subscribeProgress).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole("button", { name: /run workflow/i }));

    await waitFor(() => {
      const progress = readProgress();
      expect(progress.action).toBe("run-workflow");
      expect(progress.status).toBe("running");
    });

    act(() => {
      progressListener?.({
        action: "run-workflow",
        status: "running",
        progress: 0.74,
        message: "正在执行节点：切词",
        detail: workflowRunDetail({
          run_id: responseRun.run_id,
          completed_nodes: 1,
          current_node_id: "node-tokenize",
          current_node_label: "切词",
          current_node_index: 2,
          last_completed_node_id: "node-clean",
          node_states: {
            "node-clean": runtimeState("node-clean", "基础清洗", "completed", 1),
            "node-tokenize": runtimeState("node-tokenize", "切词", "running", 2, { node_type: "tokenize", progress: 0.74 })
          }
        })
      });
    });

    await act(async () => {
      resolveRun?.({ run: responseRun, project: responseProject });
    });

    await waitFor(() => {
      const progress = readProgress();
      expect(progress.status).toBe("completed");
      expect(progress.value).toBe(1);
    });

    const progress = readProgress();
    expect(progress.detail?.kind).toBe("workflow_run");
    if (progress.detail?.kind !== "workflow_run") {
      throw new Error("Expected workflow_run detail");
    }
    expect(progress.detail.stage).toBe("completed");
    expect(progress.detail.current_node_id).toBeUndefined();
    expect(progress.detail.last_completed_node_id).toBe("node-tokenize");
    expect(progress.detail.completed_nodes).toBe(2);
    expect(progress.detail.node_states["node-tokenize"].status).toBe("completed");
    expect(progress.detail.node_states["node-tokenize"].output_summary).toBe("120 条记录");
  });
});
