import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ProjectManifest } from "@textflow/shared-types";
import { demoWorkspace } from "../../data/demoProject";
import { ResourceBrowser } from "./ResourceBrowser";

describe("ResourceBrowser", () => {
  it("renders corpus views and can open one", () => {
    const project = {
      ...demoWorkspace.current_project!,
      corpus_resources: [
        {
          id: "resource-literature",
          name: "Literature CSV",
          source_files: ["source-1"],
          fingerprint: "sha256:resource"
        }
      ],
      corpus_views: [
        {
          id: "view-openai",
          name: "OpenAI View",
          resource_ids: ["resource-literature"],
          filter_spec: { institution: ["OpenAI"] },
          doc_ids: ["doc-1"]
        }
      ],
      ingestion_specs: [
        {
          id: "ingest-literature",
          name: "Literature CSV Profile",
          source_profile: "literature",
          field_mappings: [],
          text_build: { mode: "concat_fields" },
          dedupe_rules: { keys: ["title", "year"] }
        }
      ]
    } satisfies ProjectManifest;
    const onOpenCorpusView = vi.fn();

    render(<ResourceBrowser project={project} corpus={demoWorkspace.corpus} onOpenCorpusView={onOpenCorpusView} />);

    expect(screen.getByText("OpenAI View")).toBeInTheDocument();
    expect(screen.getByText("Literature CSV Profile")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /打开视图/i }));

    expect(onOpenCorpusView).toHaveBeenCalledWith(project.corpus_views[0]);
  });
});
