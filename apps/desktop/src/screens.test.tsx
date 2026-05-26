import { createEvent, fireEvent, render, screen, within } from "@testing-library/react";
import type { RegisteredWorkflowNodeDefinition } from "@textflow/shared-types";
import { sourceProfileImportTemplates } from "@textflow/shared-types";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { demoWorkspace } from "./data/demoProject";
import { WORKFLOW_NODE_TYPE_MIME } from "./features/workflow/workflowWorkbenchActions";

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

const fallbackFrequencyDefinition: RegisteredWorkflowNodeDefinition = {
  type: "frequency_statistics",
  title: "词频统计",
  category: "analysis",
  description: "统计词项频率。",
  inputs: [{ port_id: "token_corpus_in", port_type: "FilteredTokenCorpus", label: "过滤后语料" }],
  outputs: [{ port_id: "frequency_table", port_type: "FrequencyTable", label: "词频表", result_bundle_key: "frequency_table" }],
  params: [{ param_id: "top_n", label: "Top N", kind: "number", default_value: 200 }],
  runtime: {
    step_id: "analysis",
    executor: "analysis.frequency_statistics",
    cacheable: true,
    previewable: true,
    output_node: false
  },
  graph: {
    size: { w: 280, h: 210 },
    default_position: { x: 3660, y: 40 },
    toolbox_order: 300
  },
  ui: {
    schema_version: "1.0",
    layout: [{ widget: "number", config_key: "top_n", label: "Top N" }]
  }
};

const cleanTextDefinition: RegisteredWorkflowNodeDefinition = {
  type: "clean_text",
  title: "基础清洗",
  category: "process",
  description: "清理 HTML、URL 与空白。",
  inputs: [{ port_id: "corpus_in", port_type: "CorpusTable", label: "语料输入" }],
  outputs: [{ port_id: "clean_corpus", port_type: "CleanCorpus", label: "清洗后语料" }],
  params: [
    { param_id: "strip_html", label: "去 HTML", kind: "boolean", default_value: true },
    { param_id: "strip_urls", label: "去 URL", kind: "boolean", default_value: true },
    { param_id: "normalize_whitespace", label: "统一空白", kind: "boolean", default_value: true },
    { param_id: "normalize_punctuation", label: "统一标点", kind: "boolean", default_value: true },
    { param_id: "remove_special_chars", label: "去特殊字符", kind: "boolean", default_value: false }
  ],
  runtime: {
    step_id: "cleaning",
    executor: "workflow.clean_text",
    cacheable: true,
    previewable: true,
    output_node: false
  },
  graph: {
    size: { w: 320, h: 230 },
    default_position: { x: 1500, y: 480 }
  },
  ui: {
    schema_version: "1.0",
    layout: [
      { widget: "switch", config_key: "strip_html", label: "去 HTML" },
      { widget: "switch", config_key: "strip_urls", label: "去 URL" },
      { widget: "switch", config_key: "normalize_whitespace", label: "统一空白" },
      { widget: "switch", config_key: "normalize_punctuation", label: "统一标点" },
      { widget: "switch", config_key: "remove_special_chars", label: "去特殊字符" }
    ]
  }
};

const dictionaryInputDefinition: RegisteredWorkflowNodeDefinition = {
  type: "dictionary_input",
  title: "词表输入",
  category: "input",
  description: "引用当前项目词表。",
  inputs: [],
  outputs: [{ port_id: "dictionary_set", port_type: "DictionarySet", label: "词表" }],
  params: [
    {
      param_id: "resource_mode",
      label: "资源来源",
      kind: "enum",
      default_value: "project_dictionary",
      options: [{ value: "project_dictionary", label: "项目词表" }]
    },
    { param_id: "resource_id", label: "资源 ID", kind: "string", default_value: "project:dictionary_set" },
    { param_id: "use_custom_lexicon", label: "使用自定义词典", kind: "boolean", default_value: true },
    { param_id: "use_phrase_lexicon", label: "使用短语词典", kind: "boolean", default_value: true },
    { param_id: "apply_regex_rules", label: "启用 Regex 规则", kind: "boolean", default_value: true },
    { param_id: "apply_standard_terms", label: "启用标准词", kind: "boolean", default_value: true },
    { param_id: "apply_synonym_map", label: "启用同义词", kind: "boolean", default_value: true },
    { param_id: "apply_near_synonym_map", label: "启用近义词", kind: "boolean", default_value: true },
    { param_id: "apply_stopwords", label: "启用停用词", kind: "boolean", default_value: true },
    { param_id: "apply_exclusion_terms", label: "启用排除词", kind: "boolean", default_value: true }
  ],
  runtime: {
    step_id: "resource",
    executor: "resource.load_dictionary",
    cacheable: true,
    previewable: true,
    output_node: false
  },
  graph: {
    size: { w: 360, h: 360 },
    default_position: { x: 120, y: 40 }
  },
  ui: {
    schema_version: "1.0",
    layout: [{ widget: "slot", component_id: "dictionary_binding_selector" }]
  }
};

const corpusInputDefinition: RegisteredWorkflowNodeDefinition = {
  type: "corpus_input",
  title: "语料输入",
  category: "input",
  description: "选择项目语料范围。",
  inputs: [],
  outputs: [{ port_id: "corpus", port_type: "CorpusTable", label: "语料" }],
  params: [
    {
      param_id: "resource_mode",
      label: "资源来源",
      kind: "enum",
      default_value: "project_corpus",
      options: [{ value: "project_corpus", label: "项目语料" }]
    },
    {
      param_id: "mode",
      label: "处理范围",
      kind: "enum",
      default_value: "all_documents",
      options: [
        { value: "all_documents", label: "全部文档" },
        { value: "filtered_subset", label: "筛选子集" },
        { value: "selected_documents", label: "指定文档" }
      ]
    },
    { param_id: "year_from", label: "起始年份", kind: "number", default_value: null },
    { param_id: "year_to", label: "结束年份", kind: "number", default_value: null }
  ],
  runtime: {
    step_id: "scope",
    executor: "scope.select_corpus",
    cacheable: false,
    previewable: true,
    output_node: false
  },
  graph: {
    size: { w: 420, h: 340 },
    default_position: { x: 120, y: 480 }
  },
  ui: {
    schema_version: "1.0",
    layout: [{ widget: "slot", component_id: "corpus_scope_selector" }]
  }
};

const workflowNodeDefinitions = [
  fallbackFrequencyDefinition,
  cleanTextDefinition,
  dictionaryInputDefinition,
  corpusInputDefinition
];

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
          node_definitions: workflowNodeDefinitions,
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
    expect(screen.getByText("节点图")).toBeInTheDocument();
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

  it("accepts toolbox node drops when node definitions come from the browser fallback catalog", () => {
    useWorkspaceMock.mockReturnValue(workflowWorkspace());

    render(<PageView page="workflow" />);

    const canvas = document.querySelector(".workflow-editor-canvas") as HTMLElement;
    const beforeCount = document.querySelectorAll(".workflow-node-card-canvas").length;
    const dropEvent = createEvent.drop(canvas);
    Object.defineProperty(dropEvent, "clientX", { value: 520 });
    Object.defineProperty(dropEvent, "clientY", { value: 320 });
    Object.defineProperty(dropEvent, "dataTransfer", {
      value: {
        getData: vi.fn((type: string) => type === WORKFLOW_NODE_TYPE_MIME ? "frequency_statistics" : "")
      }
    });

    fireEvent(canvas, dropEvent);

    expect(document.querySelectorAll(".workflow-node-card-canvas")).toHaveLength(beforeCount + 1);
    expect(screen.getAllByText("词频统计").length).toBeGreaterThan(0);
  });

  it("accepts toolbox node drops when WebView only preserves text/plain", () => {
    useWorkspaceMock.mockReturnValue(workflowWorkspace());

    render(<PageView page="workflow" />);

    const canvas = document.querySelector(".workflow-editor-canvas") as HTMLElement;
    const beforeCount = document.querySelectorAll(".workflow-node-card-canvas").length;
    const dropEvent = createEvent.drop(canvas);
    Object.defineProperty(dropEvent, "clientX", { value: 520 });
    Object.defineProperty(dropEvent, "clientY", { value: 320 });
    Object.defineProperty(dropEvent, "dataTransfer", {
      value: {
        types: ["text/plain"],
        getData: vi.fn((type: string) => type === "text/plain" ? "词频统计" : "")
      }
    });

    fireEvent(canvas, dropEvent);

    expect(document.querySelectorAll(".workflow-node-card-canvas")).toHaveLength(beforeCount + 1);
    expect(screen.getAllByText("词频统计").length).toBeGreaterThan(0);
  });

  it("renders compact inline controls for stable workflow node parameters", () => {
    useWorkspaceMock.mockReturnValue(workflowWorkspace());

    render(<PageView page="workflow" />);

    const frequencyNode = screen.getAllByText("词频统计")
      .map((element) => element.closest(".workflow-node-card"))
      .find(Boolean) as HTMLElement | undefined;
    expect(frequencyNode).toBeTruthy();

    const inlineConfig = frequencyNode?.querySelector(".workflow-node-inline-config");
    expect(inlineConfig).not.toBeNull();
    expect(within(frequencyNode as HTMLElement).getByText("Top N")).toBeInTheDocument();
    expect(within(frequencyNode as HTMLElement).getByRole("spinbutton")).toHaveValue(200);
  });

  it("inlines fixed-size workflow configs and summarizes data-growing selectors", () => {
    useWorkspaceMock.mockReturnValue(workflowWorkspace());

    render(<PageView page="workflow" />);

    const cardByTitle = (title: string) => screen.getAllByText(title)
      .map((element) => element.closest(".workflow-node-card"))
      .find(Boolean) as HTMLElement | undefined;

    const cleanNode = cardByTitle("基础清洗");
    expect(cleanNode?.querySelector(".workflow-node-inline-config")).not.toBeNull();
    expect(within(cleanNode as HTMLElement).getByText("去 HTML")).toBeInTheDocument();
    expect(within(cleanNode as HTMLElement).getByText("去特殊字符")).toBeInTheDocument();

    const dictionaryNode = cardByTitle("词表输入");
    expect(dictionaryNode?.querySelector(".workflow-node-inline-config")).not.toBeNull();
    expect(within(dictionaryNode as HTMLElement).getByText("资源 ID")).toBeInTheDocument();
    expect(within(dictionaryNode as HTMLElement).getByText("启用标准词")).toBeInTheDocument();

    const corpusNode = cardByTitle("语料输入");
    expect(corpusNode?.querySelector(".workflow-node-inline-config")).toBeNull();
    expect(corpusNode?.querySelector(".workflow-node-card-facts")).not.toBeNull();
  });
});

describe("Dictionaries page loading", () => {
  function dictionariesWorkspace(project = demoWorkspace.current_project) {
    return {
      state: {
        snapshot: {
          recent_projects: demoWorkspace.recent_projects,
          current_project: project,
          corpus: demoWorkspace.corpus,
        },
        loading: false,
      },
      exportDictionaryTable: vi.fn(async () => true),
      importDictionaryTable: vi.fn(async () => null),
      pickJsonFile: vi.fn(async () => null),
      saveJsonFilePath: vi.fn(async () => null),
      saveProject: vi.fn(async () => true),
      setActivePage: vi.fn(),
    };
  }

  it("keeps hook order stable when the dictionaries page is opened before project loading finishes", async () => {
    useWorkspaceMock.mockReturnValue({
      state: {
        snapshot: {
          recent_projects: [],
          corpus: [],
        },
        loading: true,
      },
      exportDictionaryTable: vi.fn(async () => true),
      importDictionaryTable: vi.fn(async () => null),
      pickJsonFile: vi.fn(async () => null),
      saveJsonFilePath: vi.fn(async () => null),
      saveProject: vi.fn(async () => true),
      setActivePage: vi.fn(),
    });

    const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const { rerender } = render(<PageView page="dictionaries" />);

    expect(screen.getByText("词表中心为空")).toBeInTheDocument();

    useWorkspaceMock.mockReturnValue(dictionariesWorkspace());
    expect(() => rerender(
      <PageView
        page="dictionaries"
        workbenchSelection={{ kind: "lexicon_kind", projectId: "project-1", dictionaryKind: "stopwords" }}
      />
    )).not.toThrow();
    expect(await screen.findByText("词库中心")).toBeInTheDocument();
    expect(consoleErrorSpy).not.toHaveBeenCalled();
    consoleErrorSpy.mockRestore();
  });
});
