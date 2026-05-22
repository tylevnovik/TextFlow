import type {
  DictionaryKind,
  PageId,
  WorkflowEdge,
  WorkflowNodeInstance,
  WorkflowNodeType
} from "@textflow/shared-types";
import type { WorkflowWorkbenchCanvasAction } from "../features/workflow/workflowWorkbenchActions";

export type WorkbenchSelection =
  | { kind: "project"; projectId: string }
  | { kind: "corpus_collection"; projectId: string; collectionId: string }
  | { kind: "corpus_document"; projectId: string; docId: string }
  | { kind: "ingestion_spec"; projectId: string; specId: string }
  | { kind: "lexicon_kind"; projectId: string; dictionaryKind: DictionaryKind }
  | { kind: "lexicon_table"; projectId: string; dictionaryKind: DictionaryKind; tableId: string }
  | { kind: "lexicon_entry"; projectId: string; dictionaryKind: DictionaryKind; tableId: string; entryId: string }
  | { kind: "workflow"; projectId: string; workflowId: string }
  | { kind: "workflow_toolbox"; projectId: string; workflowId: string }
  | { kind: "workflow_action"; projectId: string; workflowId: string; action: WorkflowWorkbenchCanvasAction }
  | { kind: "workflow_library"; projectId: string; workflowId: string; nodeType: WorkflowNodeType }
  | { kind: "workflow_node"; projectId: string; workflowId: string; nodeId: string; nodeType?: WorkflowNodeType; node?: WorkflowNodeInstance }
  | { kind: "workflow_edge"; projectId: string; workflowId: string; edgeId: string; edge?: WorkflowEdge }
  | { kind: "run"; projectId: string; runId: string }
  | { kind: "artifact"; projectId: string; artifactId: string };

export type WorkbenchSelectionAction =
  | { type: "select"; selection: WorkbenchSelection }
  | { type: "clear"; projectId?: string };

export const WORKBENCH_SELECTION_MIME = "application/x-textflow-workbench-selection";

const fallbackProjectId = "no-project";

export function serializeWorkbenchSelection(selection: WorkbenchSelection): string {
  return JSON.stringify(selection);
}

export function parseWorkbenchSelectionPayload(payload: string): WorkbenchSelection | null {
  try {
    const parsed = JSON.parse(payload) as Partial<WorkbenchSelection>;
    if (!parsed || typeof parsed !== "object" || typeof parsed.kind !== "string" || typeof parsed.projectId !== "string") {
      return null;
    }
    return parsed as WorkbenchSelection;
  } catch {
    return null;
  }
}

export function selectionFromPage(page: PageId, projectId = fallbackProjectId): WorkbenchSelection {
  switch (page) {
    case "data":
      return { kind: "corpus_collection", projectId, collectionId: "all-corpus" };
    case "dictionaries":
      return { kind: "lexicon_kind", projectId, dictionaryKind: "stopwords" };
    case "workflow":
      return { kind: "workflow", projectId, workflowId: "active-workflow" };
    case "results":
      return { kind: "run", projectId, runId: "latest-run" };
    case "report":
      return { kind: "artifact", projectId, artifactId: "report-preview" };
    default:
      return { kind: "project", projectId };
  }
}

export function workbenchSelectionReducer(
  state: WorkbenchSelection,
  action: WorkbenchSelectionAction
): WorkbenchSelection {
  switch (action.type) {
    case "select":
      return action.selection;
    case "clear":
      return { kind: "project", projectId: action.projectId ?? state.projectId };
    default:
      return state;
  }
}

export function selectionToPage(selection: WorkbenchSelection): PageId {
  switch (selection.kind) {
    case "corpus_collection":
    case "corpus_document":
    case "ingestion_spec":
      return "data";
    case "lexicon_kind":
    case "lexicon_table":
    case "lexicon_entry":
      return "dictionaries";
    case "workflow":
    case "workflow_toolbox":
    case "workflow_action":
    case "workflow_library":
    case "workflow_node":
    case "workflow_edge":
      return "workflow";
    case "run":
    case "artifact":
      return selection.kind === "artifact" && selection.artifactId === "report-preview" ? "report" : "results";
    default:
      return "project";
  }
}

export function selectionKey(selection: WorkbenchSelection): string {
  switch (selection.kind) {
    case "project":
      return `project:${selection.projectId}`;
    case "corpus_collection":
      return `corpus:${selection.collectionId}`;
    case "corpus_document":
      return `doc:${selection.docId}`;
    case "ingestion_spec":
      return `ingestion:${selection.specId}`;
    case "lexicon_kind":
      return `lexicon:${selection.dictionaryKind}`;
    case "lexicon_table":
      return `lexicon-table:${selection.dictionaryKind}:${selection.tableId}`;
    case "lexicon_entry":
      return `lexicon-entry:${selection.dictionaryKind}:${selection.tableId}:${selection.entryId}`;
    case "workflow":
      return `workflow:${selection.workflowId}`;
    case "workflow_toolbox":
      return `workflow-toolbox:${selection.workflowId}`;
    case "workflow_action":
      return `workflow-action:${selection.workflowId}:${selection.action}`;
    case "workflow_library":
      return `workflow-library:${selection.workflowId}:${selection.nodeType}`;
    case "workflow_node":
      return `workflow-node:${selection.workflowId}:${selection.nodeId}`;
    case "workflow_edge":
      return `workflow-edge:${selection.workflowId}:${selection.edgeId}`;
    case "run":
      return `run:${selection.runId}`;
    case "artifact":
      return `artifact:${selection.artifactId}`;
    default:
      return "unknown";
  }
}
