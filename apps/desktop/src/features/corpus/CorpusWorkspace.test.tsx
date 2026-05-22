import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { demoWorkspace } from "../../data/demoProject";
import { CorpusWorkspace } from "./CorpusWorkspace";

describe("CorpusWorkspace", () => {
  it("renders corpus commands and forwards send-to-workflow", () => {
    const onSendToWorkflow = vi.fn();

    render(
      <CorpusWorkspace
        project={demoWorkspace.current_project!}
        corpus={demoWorkspace.corpus}
        loading={false}
        canSaveImportSpec
        canCreateView
        onImportFiles={vi.fn()}
        onSaveImportSpec={vi.fn()}
        onCreateCorpusView={vi.fn()}
        onSendToWorkflow={onSendToWorkflow}
        showToolbar
      >
        <div>语料表内容</div>
      </CorpusWorkspace>
    );

    expect(screen.getByRole("button", { name: "导入文件" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存导入规范" })).toBeInTheDocument();
    expect(screen.getByText("语料表内容")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "发送到节点图" }));

    expect(onSendToWorkflow).toHaveBeenCalledTimes(1);
  });
});
