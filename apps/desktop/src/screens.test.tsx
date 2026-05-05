import { fireEvent, render, screen } from "@testing-library/react";
import { sourceProfileImportTemplates } from "@textflow/shared-types";
import { beforeEach, describe, expect, it, vi } from "vitest";

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

import { PageView } from "./screens";

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
