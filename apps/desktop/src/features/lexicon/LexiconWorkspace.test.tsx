import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { demoWorkspace } from "../../data/demoProject";
import { LexiconWorkspace } from "./LexiconWorkspace";

describe("LexiconWorkspace", () => {
  it("renders lexicon commands and forwards binding to workflow", () => {
    const onBindToWorkflow = vi.fn();
    const dictionarySet = demoWorkspace.current_project!.dictionary_set;
    const currentTable = dictionarySet.collections.stopwords.tables[0];

    render(
      <LexiconWorkspace
        dictionarySet={dictionarySet}
        activeKind="stopwords"
        currentTable={currentTable}
        loading={false}
        onImportTable={vi.fn()}
        onExportTable={vi.fn()}
        onAddTable={vi.fn()}
        onDuplicateTable={vi.fn()}
        onBindToWorkflow={onBindToWorkflow}
        showToolbar
      >
        <div>词库条目内容</div>
      </LexiconWorkspace>
    );

    expect(screen.getByRole("button", { name: "导入词表" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "导出词表" })).toBeInTheDocument();
    expect(screen.getByText("词库条目内容")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "绑定到节点" }));

    expect(onBindToWorkflow).toHaveBeenCalledTimes(1);
  });
});
