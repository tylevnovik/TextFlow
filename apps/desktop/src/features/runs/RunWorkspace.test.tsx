import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { demoWorkspace } from "../../data/demoProject";
import { ArtifactWorkspace } from "./ArtifactWorkspace";
import { RunHistoryWorkspace } from "./RunHistoryWorkspace";
import { RunStatusPane } from "./RunStatusPane";

describe("RunStatusPane", () => {
  it("uses compact unique tab names", () => {
    render(
      <RunStatusPane
        activeTab="progress"
        onTabChange={vi.fn()}
        snapshot={demoWorkspace}
        progress={{
          status: "idle",
          value: 0,
          headline: "空闲"
        }}
      />
    );

    expect(screen.getByRole("tab", { name: "运行进度" })).toHaveTextContent("进度");
    expect(screen.getByRole("tab", { name: "节点日志" })).toHaveTextContent("日志");
    expect(screen.getByRole("tab", { name: "校验问题" })).toHaveTextContent("问题");
    expect(screen.getByRole("tab", { name: "产物列表" })).toHaveTextContent("产物");
    expect(screen.queryByRole("tab", { name: "节点日志 节点日志" })).not.toBeInTheDocument();
  });

  it("opens artifacts from the bottom support pane", () => {
    const onOpenArtifact = vi.fn();

    render(
      <RunStatusPane
        activeTab="artifacts"
        onTabChange={vi.fn()}
        snapshot={demoWorkspace}
        progress={{
          status: "idle",
          value: 0,
          headline: "空闲"
        }}
        onOpenArtifact={onOpenArtifact}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /artifact-demo-report/i }));

    expect(onOpenArtifact).toHaveBeenCalledWith(expect.objectContaining({ artifact_id: "artifact-demo-report" }));
  });
});

describe("RunHistoryWorkspace", () => {
  it("opens the latest run and exposes export commands", () => {
    const onSelectRun = vi.fn();
    const project = demoWorkspace.current_project!;

    render(
      <RunHistoryWorkspace
        project={project}
        loading={false}
        onSelectRun={onSelectRun}
        onCompareRuns={vi.fn()}
        onExportFormats={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "打开运行" }));

    expect(onSelectRun).toHaveBeenCalledWith(expect.objectContaining({ run_id: "run-20260416-1810" }));
    expect(screen.getByRole("button", { name: "导出 CSV" })).toBeInTheDocument();
    expect(screen.getByText("运行记录")).toBeInTheDocument();
  });
});

describe("ArtifactWorkspace", () => {
  it("loads the selected artifact preview and forwards export commands", async () => {
    const project = demoWorkspace.current_project!;
    const onLoadPreview = vi.fn().mockResolvedValue({
      artifact_id: "artifact-demo-frequency",
      columns: ["term", "tf"],
      rows: [{ term: "AI", tf: 10 }],
      row_count: 1
    });
    const onExportFormats = vi.fn();

    render(
      <ArtifactWorkspace
        project={project}
        artifacts={project.artifact_records}
        loading={false}
        selectedArtifactId="artifact-demo-frequency"
        onLoadPreview={onLoadPreview}
        onExportFormats={onExportFormats}
      />
    );

    await waitFor(() => expect(onLoadPreview).toHaveBeenCalledWith("artifact-demo-frequency"));
    expect(await screen.findByText("AI")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "导出 HTML" }));

    expect(onExportFormats).toHaveBeenCalledWith(["html"]);
  });
});
