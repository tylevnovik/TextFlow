import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { PageId } from "@textflow/shared-types";
import { demoWorkspace } from "../data/demoProject";
import { WORKFLOW_NODE_TYPE_MIME } from "../features/workflow/workflowWorkbenchActions";
import { AppShell } from "./AppShell";
import { ProjectWorkbench, type WorkbenchProgressInfo } from "./ProjectWorkbench";

const useWorkspaceMock = vi.fn();

vi.mock("../store/workspaceStore", () => ({
  useWorkspace: () => useWorkspaceMock(),
  useTaskProgress: () => ({
    action: "",
    status: "idle",
    value: 0,
    message: "",
  })
}));

function renderWorkbench(activePage: PageId = "project") {
  const setActivePage = vi.fn();
  const progress: WorkbenchProgressInfo = {
    status: "idle",
    value: 0,
    headline: "后台空闲"
  };

  function Harness() {
    const [page, setPage] = useState<PageId>(activePage);
    const handleSetActivePage = (nextPage: PageId) => {
      setActivePage(nextPage);
      setPage(nextPage);
    };

    useWorkspaceMock.mockReturnValue({
      state: {
        snapshot: demoWorkspace,
        loading: false,
        statusLine: "测试工作区已加载",
        uiScale: 1
      },
      setActivePage: handleSetActivePage,
      saveProject: vi.fn(async () => true),
      runWorkflow: vi.fn(async () => null),
      loadArtifactPreview: vi.fn(async () => null),
    });

    return (
      <AppShell uiScale={1}>
        <ProjectWorkbench
          activePage={page}
          snapshot={demoWorkspace}
          loading={false}
          statusLine="测试工作区已加载"
          progress={progress}
          setActivePage={handleSetActivePage}
          onRunWorkflow={vi.fn()}
          onExportArtifacts={vi.fn()}
        />
      </AppShell>
    );
  }

  const renderResult = render(<Harness />);

  return { setActivePage, ...renderResult };
}

describe("ProjectWorkbench", () => {
  beforeEach(() => {
    vi.stubGlobal("ResizeObserver", class {
      observe() {}
      unobserve() {}
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

  it("renders the three core project object groups", () => {
    renderWorkbench();

    const objectTree = screen.getByLabelText("项目对象树");
    expect(screen.getByText("项目对象")).toBeInTheDocument();
    expect(within(objectTree).getByText("语料")).toBeInTheDocument();
    expect(within(objectTree).getByText("词库")).toBeInTheDocument();
    expect(within(objectTree).getByText("节点图")).toBeInTheDocument();
  });

  it("opens the matching work surface when a top-level object group is selected", () => {
    const { setActivePage } = renderWorkbench();

    const objectTree = screen.getByLabelText("项目对象树");
    fireEvent.click(within(objectTree).getByText("语料"));

    expect(setActivePage).toHaveBeenCalledWith("data");
    expect(screen.getByRole("heading", { name: "管理导入批次、字段映射、主文本和文档视图" })).toBeInTheDocument();
  });

  it("selects a corpus object and updates the inspector", () => {
    const { setActivePage } = renderWorkbench("data");

    const objectTree = screen.getByLabelText("项目对象树");
    fireEvent.click(within(objectTree).getByText("全部语料"));

    expect(setActivePage).toHaveBeenCalledWith("data");
    const inspector = screen.getByLabelText("属性检查器");
    expect(screen.getByText("语料集合")).toBeInTheDocument();
    expect(within(inspector).getByText("全部语料")).toBeInTheDocument();
  });

  it("shows artifact support content in the bottom pane", () => {
    renderWorkbench("results");

    const bottomPane = screen.getByLabelText("运行状态面板");
    fireEvent.click(within(bottomPane).getByRole("tab", { name: "产物列表" }));

    expect(within(bottomPane).getByText("artifact-demo-frequency")).toBeInTheDocument();
  });

  it("collapses the bottom grid row on pages without a support pane", () => {
    const { unmount } = renderWorkbench("home");

    const homeShell = document.querySelector(".textflow-workbench-shell");
    expect(homeShell).toHaveClass("is-bottom-pane-collapsed");
    expect(screen.queryByLabelText("运行状态面板")).not.toBeInTheDocument();

    unmount();
    renderWorkbench("results");

    const resultsShell = document.querySelector(".textflow-workbench-shell");
    expect(resultsShell).not.toHaveClass("is-bottom-pane-collapsed");
    expect(screen.getByLabelText("运行状态面板")).toBeInTheDocument();
  });

  it("updates the inspector when a corpus document is selected in the workspace", () => {
    renderWorkbench("data");

    fireEvent.click(screen.getByRole("gridcell", { name: /^Patent intelligence mining for battery supply chains Battery/ }));

    const inspector = screen.getByLabelText("属性检查器");
    expect(within(inspector).getByText("语料文档")).toBeInTheDocument();
    expect(within(inspector).getByText("DOC-002")).toBeInTheDocument();
  });

  it("updates the inspector when a lexicon table is selected in the workspace", () => {
    renderWorkbench("dictionaries");

    fireEvent.click(screen.getByRole("button", { name: /中文通用停用词/ }));

    const inspector = screen.getByLabelText("属性检查器");
    expect(within(inspector).getByText("词库资源表")).toBeInTheDocument();
    expect(within(inspector).getByText("中文通用停用词（stopwords-iso）")).toBeInTheDocument();
  });

  it("updates the inspector when a workflow node is selected in the canvas", () => {
    renderWorkbench("workflow");

    const cleanNode = screen.getAllByText("基础清洗")
      .map((element) => element.closest(".workflow-node-card"))
      .find(Boolean);
    expect(cleanNode).not.toBeNull();
    fireEvent.click(cleanNode as HTMLElement);

    const inspector = screen.getByLabelText("属性检查器");
    expect(within(inspector).getByText("节点参数")).toBeInTheDocument();
    expect(within(inspector).getByRole("heading", { name: "基础清洗" })).toBeInTheDocument();
  });

  it("nests workflow node types inside the toolbox drawer and keeps them draggable", () => {
    renderWorkbench("workflow");

    const objectTree = screen.getByLabelText("项目对象树");
    const graphItem = objectTree.querySelector('[data-fui-tree-item-value="workflow-active"]');
    const toolboxItem = objectTree.querySelector('[data-fui-tree-item-value="workflow-toolbox"]');

    expect(graphItem).not.toBeNull();
    expect(toolboxItem).not.toBeNull();
    expect(within(graphItem as HTMLElement).queryByText("词频统计")).not.toBeInTheDocument();
    expect(within(toolboxItem as HTMLElement).getByText("词频统计")).toBeInTheDocument();

    const frequencyItem = within(toolboxItem as HTMLElement).getByText("词频统计").closest('[role="treeitem"]') as HTMLElement;
    const dataTransfer = {
      effectAllowed: "",
      setData: vi.fn()
    };

    fireEvent.dragStart(frequencyItem, { dataTransfer });

    expect(frequencyItem).toHaveAttribute("draggable", "true");
    expect(dataTransfer.effectAllowed).toBe("copy");
    expect(dataTransfer.setData).toHaveBeenCalledWith(WORKFLOW_NODE_TYPE_MIME, "frequency_statistics");
    expect(dataTransfer.setData).toHaveBeenCalledWith("text/plain", "词频统计");
  });

  it("leaves the workflow surface from the outer object navigation", () => {
    const { setActivePage } = renderWorkbench("workflow");

    const objectNav = screen.getByRole("navigation", { name: "主对象导航" });
    fireEvent.click(within(objectNav).getByRole("button", { name: "语料" }));

    expect(setActivePage).toHaveBeenCalledWith("data");
    expect(screen.getByRole("heading", { name: "管理导入批次、字段映射、主文本和文档视图" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "保存图" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("运行状态面板")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "项目管理" }));

    expect(setActivePage).toHaveBeenCalledWith("home");
    expect(screen.getByRole("heading", { name: "管理本地项目仓库" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "运行节点图" })).not.toBeInTheDocument();
  });
});
