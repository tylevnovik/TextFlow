import { fireEvent, render, screen, within } from "@testing-library/react";
import { sourceProfileImportTemplates } from "@textflow/shared-types";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { demoWorkspace } from "./data/demoProject";

const useWorkspaceMock = vi.fn();

vi.mock("./store/workspaceStore", () => ({
  useWorkspace: () => useWorkspaceMock(),
  useTaskProgress: () => ({
    action: "",
    status: "idle",
    value: 0,
    message: "",
  }),
}));

import { PageView, WorkflowEditorPage } from "./screens";

describe("DataPage advanced mapping editor", () => {
  beforeEach(() => {
    const incopatTemplate = {
      id: "template-incopat",
      source_profile: "incopat" as const,
      name: sourceProfileImportTemplates.incopat.name,
      description: sourceProfileImportTemplates.incopat.description,
      field_mappings: sourceProfileImportTemplates.incopat.field_mappings.map((rule) => ({
        ...rule,
        aliases: [...(rule.aliases ?? [])],
      })),
      text_build: {
        ...sourceProfileImportTemplates.incopat.text_build,
        fields: [...sourceProfileImportTemplates.incopat.text_build.fields],
      },
    };

    useWorkspaceMock.mockReturnValue({
      state: {
        snapshot: {
          recent_projects: [],
          current_project: {
            id: "project-1",
            updated_at: "2026-04-28T10:00:00Z",
            import_template: incopatTemplate,
          },
          corpus: [],
        },
        loading: false,
      },
      deleteCorpusDocument: vi.fn(),
      pickImportFiles: vi.fn(async () => []),
      importProjectFiles: vi.fn(async () => null),
      saveProject: vi.fn(async () => true),
      updateCorpusDocument: vi.fn(async () => null),
    });
  });

  it("keeps the source field input focused while typing", () => {
    render(<PageView page="data" />);

    fireEvent.click(screen.getByRole("button", { name: "展开高级字段设置" }));

    const originalInput = screen.getAllByPlaceholderText("源字段名")[0] as HTMLInputElement;
    const updatedValue = `${originalInput.value}X`;

    originalInput.focus();
    expect(originalInput).toHaveFocus();

    fireEvent.change(originalInput, { target: { value: updatedValue } });

    const updatedInput = screen.getAllByPlaceholderText("源字段名")[0] as HTMLInputElement;
    expect(updatedInput).toHaveValue(updatedValue);
    expect(updatedInput).toHaveFocus();
  });
});

describe("Workflow page loading and previews", () => {
  beforeEach(() => {
    vi.stubGlobal("ResizeObserver", class {
      observe() {}
      disconnect() {}
    });
    Object.defineProperty(window, "requestAnimationFrame", {
      configurable: true,
      value: (callback: FrameRequestCallback) => window.setTimeout(() => callback(Date.now()), 0),
    });
    Object.defineProperty(window, "cancelAnimationFrame", {
      configurable: true,
      value: (id: number) => window.clearTimeout(id),
    });
    window.localStorage.clear();
  });

  function workflowWorkspace(project = demoWorkspace.current_project, corpus = demoWorkspace.corpus) {
    return {
      state: {
        snapshot: {
          recent_projects: demoWorkspace.recent_projects,
          current_project: project,
          corpus,
          node_definitions: [],
        },
        loading: false,
      },
      saveProject: vi.fn(async () => true),
      runWorkflow: vi.fn(async () => null),
      setActivePage: vi.fn(),
      loadArtifactPreview: vi.fn(async () => null),
    };
  }

  it("keeps hook order stable when the workflow page is opened before project loading finishes", () => {
    useWorkspaceMock.mockReturnValue({
      state: {
        snapshot: {
          recent_projects: [],
          corpus: [],
          node_definitions: [],
        },
        loading: true,
      },
      saveProject: vi.fn(async () => true),
      runWorkflow: vi.fn(async () => null),
      setActivePage: vi.fn(),
      loadArtifactPreview: vi.fn(async () => null),
    });

    const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const { rerender } = render(<WorkflowEditorPage />);

    expect(screen.getByText("流程配置待初始化")).toBeInTheDocument();

    useWorkspaceMock.mockReturnValue(workflowWorkspace());
    expect(() => rerender(<WorkflowEditorPage />)).not.toThrow();
    expect(screen.getByText("Node Workflow")).toBeInTheDocument();
    expect(consoleErrorSpy).not.toHaveBeenCalled();
    consoleErrorSpy.mockRestore();
  });

  it("shows persisted node output previews after reopening when a node has no artifact", async () => {
    const reopenedProject = JSON.parse(JSON.stringify(demoWorkspace.current_project));
    const reopenedCorpus = JSON.parse(JSON.stringify(demoWorkspace.corpus)).map((item: Record<string, unknown>) => ({
      ...item,
      clean_text: "",
      normalized_text: "",
      tokens: [],
      phrase_hits: [],
      filtered_tokens: [],
    }));
    reopenedProject.artifact_records = reopenedProject.artifact_records.filter(
      (artifact: { node_id: string }) => artifact.node_id !== "node-clean-text"
    );
    reopenedProject.run_history = [
      {
        ...reopenedProject.run_history[0],
        node_runs: [
          {
            node_id: "node-clean-text",
            node_type: "clean_text",
            label: "基础清洗",
            status: "completed",
            started_at: "2026-04-16T18:10:00+08:00",
            ended_at: "2026-04-16T18:10:01+08:00",
            duration_ms: 120,
            cache_hit: false,
            output_ports: ["clean_corpus"],
            output_summary: "clean_corpus：3 条记录",
            sample_outputs: ["clean_corpus · DOC-001"],
            output_previews: {
              clean_corpus: {
                kind: "table",
                row_count: 3,
                rows: [
                  {
                    doc_id: "DOC-001",
                    title: "生成式 AI 在学术写作支持中的应用边界",
                    clean_text: "persisted clean preview after reopen",
                  },
                ],
              },
            },
          },
        ],
      },
    ];

    useWorkspaceMock.mockReturnValue(workflowWorkspace(reopenedProject, reopenedCorpus));

    render(<PageView page="workflow" />);
    const cleanNode = screen.getAllByText("基础清洗")
      .map((element) => element.closest(".workflow-node-card"))
      .find(Boolean);
    expect(cleanNode).not.toBeNull();
    fireEvent.click(within(cleanNode as HTMLElement).getByRole("button", { name: "预览" }));

    expect(await screen.findByText("persisted clean preview after reopen")).toBeInTheDocument();
  });
});
