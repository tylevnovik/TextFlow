import type {
  ArtifactRecord,
  CorpusItem,
  CorpusView,
  DictionaryKind,
  DictionaryTableResource,
  ExperimentSpec,
  ExportFormat,
  IngestionSpec,
  NodeCatalogResponse,
  WorkflowNodeRuntimeState,
  WorkflowRunProgressDetail,
  ProjectManifest,
  ProjectSummary,
  RunRecord,
  WorkspaceSnapshot
} from "@textflow/shared-types";
import { createSimulatedRun, demoProjectSummary, demoWorkspace } from "../data/demoProject";
import type { ReviewResolutionInput, ReviewTaskRecord } from "../features/review/reviewTypes";
import { runArtifactRowCount } from "../runArtifacts";

export interface CreateProjectInput {
  name: string;
  description: string;
}

export interface DuplicateProjectInput {
  projectId: string;
  name?: string;
}

export interface ImportProjectFilesResponse {
  project_id: string;
  imported_documents: number;
  documents?: CorpusItem[];
  project?: ProjectManifest;
  source_files: Array<{ id: string; name: string; relative_path: string; row_count: number }>;
  document_count: number;
  skipped_rows: number;
  validation_issues: Array<{ file: string; row: number; missing_fields: string[]; reason: string }>;
}

export interface ExportProjectBackupResponse {
  path: string;
  relative_path: string;
}

export interface ExportedFileRecord {
  path: string;
  relative_path: string;
}

export interface ExportProjectResponse {
  project_id: string;
  export_dir: string;
  relative_export_dir: string;
  files: ExportedFileRecord[];
}

export interface DeleteCorpusDocumentResponse {
  doc_id: string;
  document_count: number;
  source_files?: ProjectManifest["source_files"];
  project_updated_at?: string;
}

export interface UpdateCorpusDocumentResponse {
  document: CorpusItem;
  document_count: number;
  source_files?: ProjectManifest["source_files"];
  project_updated_at?: string;
}

export interface SaveIngestionSpecResponse {
  spec: IngestionSpec;
  project?: ProjectManifest;
  project_updated_at?: string;
}

export interface ListIngestionSpecsResponse {
  project_id: string;
  specs: IngestionSpec[];
}

export interface CorpusViewMutationResponse {
  view: CorpusView;
  project?: ProjectManifest;
  project_updated_at?: string;
}

export interface DeleteCorpusViewResponse {
  view_id: string;
  removed?: CorpusView;
  project?: ProjectManifest;
  project_updated_at?: string;
}

export interface ArtifactPreviewResponse {
  artifact_id: string;
  columns?: string[];
  rows: Array<Record<string, unknown>>;
  row_count?: number;
  preview_rows?: number;
}

export interface ListRunArtifactsResponse {
  project_id: string;
  run_id?: string;
  artifacts: ArtifactRecord[];
}

export interface ImportDictionaryTableResponse {
  table: DictionaryTableResource;
  dictionary_set?: ProjectManifest["dictionary_set"];
  project_updated_at?: string;
}

export interface RunWorkflowResponse {
  run: RunRecord;
  project: ProjectManifest;
}

export interface CreateReviewTaskInput {
  review_type: string;
  target_ref: Record<string, string>;
  title?: string;
  description?: string;
  payload?: Record<string, unknown>;
}

export interface CreateReviewTaskResponse {
  task: ReviewTaskRecord;
  project: ProjectManifest;
  project_updated_at?: string;
}

export interface ListReviewTasksResponse {
  project_id: string;
  tasks: ReviewTaskRecord[];
}

export interface ResolveReviewTaskResponse {
  task: ReviewTaskRecord;
  project: ProjectManifest;
  corpus: CorpusItem[];
  source_files?: ProjectManifest["source_files"];
  project_updated_at?: string;
}

export interface SaveExperimentSpecResponse {
  experiment: ExperimentSpec;
  project: ProjectManifest;
  project_updated_at?: string;
}

export interface RunExperimentMatrixResponse {
  experiment: ExperimentSpec;
  runs: RunRecord[];
  project: ProjectManifest;
  corpus: CorpusItem[];
}

export interface RunDiffArtifactSummary {
  step: string;
  left_record_count: number;
  right_record_count: number;
  record_count_delta: number;
  added_files: string[];
  removed_files: string[];
}

export interface RunDiffSummary {
  left_run_id: string;
  right_run_id: string;
  summary: string;
  metrics?: Record<string, Record<string, number>>;
  artifact_diffs?: RunDiffArtifactSummary[];
}

export interface DeleteProjectResponse {
  project_id: string;
  deleted_path: string;
}

export interface LegacyEngineProgressDetail {
  kind?: "node" | "stage";
  node_id?: string;
  node_type?: string;
  node_label?: string;
  node_index?: number;
  total_nodes?: number;
  detail?: string;
}

export interface WorkflowRuntimeProgressDetail extends WorkflowRunProgressDetail {
  node_states: Record<string, WorkflowNodeRuntimeState>;
}

export type EngineProgressDetail = LegacyEngineProgressDetail | WorkflowRuntimeProgressDetail;

export interface EngineProgressEvent {
  action: string;
  status: string;
  progress: number;
  message: string;
  detail?: EngineProgressDetail;
}

interface DesktopBridge {
  loadWorkspace(): Promise<WorkspaceSnapshot>;
  getNodeCatalog(): Promise<NodeCatalogResponse>;
  createProject(input: CreateProjectInput): Promise<ProjectSummary>;
  openProject(projectId: string): Promise<ProjectSummary>;
  duplicateProject(input: DuplicateProjectInput): Promise<ProjectSummary>;
  deleteProject(projectId: string): Promise<DeleteProjectResponse>;
  pickImportFiles(): Promise<string[]>;
  pickJsonFile(): Promise<string | null>;
  saveJsonFilePath(defaultFileName?: string): Promise<string | null>;
  pickProjectPackageFile(): Promise<string | null>;
  saveProjectPackagePath(defaultFileName?: string): Promise<string | null>;
  importProjectPackage(path: string): Promise<ProjectSummary>;
  importProjectFiles(projectId: string, filePaths: string[], importTemplate?: ProjectManifest["import_template"]): Promise<ImportProjectFilesResponse>;
  runWorkflow(projectId: string): Promise<RunWorkflowResponse>;
  exportProject(projectId: string, formats: ExportFormat[]): Promise<ExportProjectResponse>;
  exportProjectBackup(projectId: string, path?: string): Promise<ExportProjectBackupResponse>;
  updateCorpusDocument(projectId: string, document: CorpusItem): Promise<UpdateCorpusDocumentResponse>;
  deleteCorpusDocument(projectId: string, docId: string): Promise<DeleteCorpusDocumentResponse>;
  saveIngestionSpec(projectId: string, spec: Partial<IngestionSpec>): Promise<SaveIngestionSpecResponse>;
  listIngestionSpecs(projectId: string): Promise<ListIngestionSpecsResponse>;
  createCorpusView(projectId: string, view: Partial<CorpusView>): Promise<CorpusViewMutationResponse>;
  updateCorpusView(projectId: string, view: Partial<CorpusView> & { id: string }): Promise<CorpusViewMutationResponse>;
  deleteCorpusView(projectId: string, viewId: string): Promise<DeleteCorpusViewResponse>;
  loadArtifactPreview(projectId: string, artifactId: string, limit?: number): Promise<ArtifactPreviewResponse>;
  listRunArtifacts(projectId: string, runId?: string): Promise<ListRunArtifactsResponse>;
  importDictionaryTable(projectId: string, kind: DictionaryKind, path: string): Promise<ImportDictionaryTableResponse>;
  exportDictionaryTable(projectId: string, kind: DictionaryKind, tableId: string, path: string): Promise<{ kind: DictionaryKind; table_id: string; path: string }>;
  createReviewTask(projectId: string, input: CreateReviewTaskInput): Promise<CreateReviewTaskResponse>;
  listReviewTasks(projectId: string, status?: string): Promise<ListReviewTasksResponse>;
  resolveReviewTask(projectId: string, reviewId: string, resolution: ReviewResolutionInput): Promise<ResolveReviewTaskResponse>;
  saveExperimentSpec(projectId: string, experiment: Partial<ExperimentSpec>): Promise<SaveExperimentSpecResponse>;
  runExperimentMatrix(projectId: string, experimentId: string): Promise<RunExperimentMatrixResponse>;
  compareRuns(projectId: string, leftRunId: string, rightRunId: string): Promise<RunDiffSummary>;
  saveProject(project: ProjectManifest): Promise<ProjectSummary>;
  openPath(path: string): Promise<void>;
  revealPath(path: string): Promise<void>;
  subscribeProgress(listener: (event: EngineProgressEvent) => void): Promise<() => void>;
}

declare global {
  interface Window {
    __TAURI_INTERNALS__?: unknown;
  }
}

interface EngineTaskSnapshot {
  action: string;
  status: string;
  progress: number;
  message: string;
  detail?: EngineProgressDetail;
  result?: unknown;
  error?: string;
}

interface EngineTaskTicket {
  task_id: string;
}

type DevEnginePayloadMapper = (payload?: Record<string, unknown>) => Record<string, unknown>;

const delay = (ms: number) => new Promise((resolve) => {
  window.setTimeout(resolve, ms);
});

const devEngineProgressListeners = new Set<(event: EngineProgressEvent) => void>();

function devEngineBaseUrl(): string | null {
  const configured = import.meta.env.VITE_TEXTFLOW_ENGINE_URL;
  if (!configured || typeof configured !== "string") {
    return null;
  }
  return configured.replace(/\/+$/, "");
}

function emitDevEngineProgress(snapshot: EngineTaskSnapshot) {
  const event: EngineProgressEvent = {
    action: snapshot.action,
    status: snapshot.status,
    progress: snapshot.progress,
    message: snapshot.message,
    detail: snapshot.detail
  };
  devEngineProgressListeners.forEach((listener) => listener(event));
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    throw new Error(`Engine request failed (${response.status}): ${await response.text()}`);
  }
  return response.json() as Promise<T>;
}

async function runDevEngineTask<T>(action: string, payload: Record<string, unknown>): Promise<T> {
  const baseUrl = devEngineBaseUrl();
  if (!baseUrl) {
    throw new Error("VITE_TEXTFLOW_ENGINE_URL is not configured.");
  }
  const ticket = await fetchJson<EngineTaskTicket>(`${baseUrl}/tasks/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, payload })
  });

  for (;;) {
    const snapshot = await fetchJson<EngineTaskSnapshot>(`${baseUrl}/tasks/${encodeURIComponent(ticket.task_id)}`);
    emitDevEngineProgress(snapshot);
    if (snapshot.status === "completed") {
      return snapshot.result as T;
    }
    if (snapshot.status === "failed") {
      throw new Error(snapshot.error || snapshot.message || `${action} failed`);
    }
    await delay(250);
  }
}

const devEngineCommandMap: Record<string, { action: string; mapPayload: DevEnginePayloadMapper }> = {
  load_workspace: { action: "load-workspace", mapPayload: () => ({}) },
  get_node_catalog: { action: "get-node-catalog", mapPayload: () => ({}) },
  create_project: {
    action: "create-project",
    mapPayload: (payload) => {
      const input = payload?.input as CreateProjectInput | undefined;
      return {
        name: input?.name,
        description: input?.description ?? ""
      };
    }
  },
  open_project: {
    action: "open-project",
    mapPayload: (payload) => ({ project_id: payload?.projectId })
  },
  duplicate_project: {
    action: "duplicate-project",
    mapPayload: (payload) => {
      const input = payload?.input as DuplicateProjectInput | undefined;
      return {
        project_id: input?.projectId,
        name: input?.name
      };
    }
  },
  delete_project: {
    action: "delete-project",
    mapPayload: (payload) => ({ project_id: payload?.projectId })
  },
  import_project_files: {
    action: "import-project-files",
    mapPayload: (payload) => ({
      project_id: payload?.projectId,
      file_paths: payload?.filePaths,
      import_template: payload?.importTemplate
    })
  },
  import_project_package: {
    action: "import-project-package",
    mapPayload: (payload) => ({ path: payload?.path })
  },
  run_workflow: {
    action: "run-workflow",
    mapPayload: (payload) => ({ project_id: payload?.projectId })
  },
  export_project: {
    action: "export-project",
    mapPayload: (payload) => ({
      project_id: payload?.projectId,
      formats: payload?.formats
    })
  },
  export_project_backup: {
    action: "export-project-backup",
    mapPayload: (payload) => ({
      project_id: payload?.projectId,
      path: payload?.path
    })
  },
  update_corpus_document: {
    action: "update-corpus-document",
    mapPayload: (payload) => ({
      project_id: payload?.projectId,
      document: payload?.document
    })
  },
  delete_corpus_document: {
    action: "delete-corpus-document",
    mapPayload: (payload) => ({
      project_id: payload?.projectId,
      doc_id: payload?.docId
    })
  },
  save_ingestion_spec: {
    action: "save-ingestion-spec",
    mapPayload: (payload) => ({
      project_id: payload?.projectId,
      spec: payload?.spec
    })
  },
  list_ingestion_specs: {
    action: "list-ingestion-specs",
    mapPayload: (payload) => ({ project_id: payload?.projectId })
  },
  create_corpus_view: {
    action: "create-corpus-view",
    mapPayload: (payload) => ({
      project_id: payload?.projectId,
      view: payload?.view
    })
  },
  update_corpus_view: {
    action: "update-corpus-view",
    mapPayload: (payload) => ({
      project_id: payload?.projectId,
      view: payload?.view
    })
  },
  delete_corpus_view: {
    action: "delete-corpus-view",
    mapPayload: (payload) => ({
      project_id: payload?.projectId,
      view_id: payload?.viewId
    })
  },
  load_artifact_preview: {
    action: "load-artifact-preview",
    mapPayload: (payload) => ({
      project_id: payload?.projectId,
      artifact_id: payload?.artifactId,
      limit: payload?.limit
    })
  },
  list_run_artifacts: {
    action: "list-run-artifacts",
    mapPayload: (payload) => ({
      project_id: payload?.projectId,
      run_id: payload?.runId
    })
  },
  import_dictionary_sheet: {
    action: "import-dictionary-sheet",
    mapPayload: (payload) => ({
      project_id: payload?.projectId,
      kind: payload?.kind,
      path: payload?.path
    })
  },
  export_dictionary_sheet: {
    action: "export-dictionary-sheet",
    mapPayload: (payload) => ({
      project_id: payload?.projectId,
      kind: payload?.kind,
      table_id: payload?.tableId,
      path: payload?.path
    })
  },
  create_review_task: {
    action: "create-review-task",
    mapPayload: (payload) => ({
      project_id: payload?.projectId,
      task: payload?.task
    })
  },
  list_review_tasks: {
    action: "list-review-tasks",
    mapPayload: (payload) => ({
      project_id: payload?.projectId,
      status: payload?.status
    })
  },
  resolve_review_task: {
    action: "resolve-review-task",
    mapPayload: (payload) => ({
      project_id: payload?.projectId,
      review_id: payload?.reviewId,
      resolution: payload?.resolution
    })
  },
  save_experiment_spec: {
    action: "save-experiment-spec",
    mapPayload: (payload) => ({
      project_id: payload?.projectId,
      experiment: payload?.experiment
    })
  },
  run_experiment_matrix: {
    action: "run-experiment-matrix",
    mapPayload: (payload) => ({
      project_id: payload?.projectId,
      experiment_id: payload?.experimentId
    })
  },
  compare_runs: {
    action: "compare-runs",
    mapPayload: (payload) => ({
      project_id: payload?.projectId,
      left_run_id: payload?.leftRunId,
      right_run_id: payload?.rightRunId
    })
  },
  save_project: {
    action: "save-project",
    mapPayload: (payload) => (payload?.project as Record<string, unknown> | undefined) ?? {}
  }
};

function simulatedReviewTasks(project: ProjectManifest): ReviewTaskRecord[] {
  return project.review_tasks as unknown as ReviewTaskRecord[];
}

function simulatedExperimentSpecs(project: ProjectManifest): ExperimentSpec[] {
  return project.experiment_specs as ExperimentSpec[];
}

async function tryInvoke<T>(command: string, payload?: Record<string, unknown>): Promise<T | null> {
  const { invoke, isTauri } = await import("@tauri-apps/api/core");
  if (isTauri()) {
    return invoke<T>(command, payload);
  }

  const devEngineCommand = devEngineCommandMap[command];
  if (devEngineCommand && devEngineBaseUrl()) {
    return runDevEngineTask<T>(devEngineCommand.action, devEngineCommand.mapPayload(payload));
  }
  return null;
}

export const desktopBridge: DesktopBridge = {
  async loadWorkspace() {
    const result = await tryInvoke<WorkspaceSnapshot>("load_workspace");
    if (result !== null) {
      return result;
    }
    await delay(180);
    // Browser-only fallback: normal desktop builds use the Tauri/Python sidecar.
    return demoWorkspace;
  },

  async getNodeCatalog() {
    const result = await tryInvoke<NodeCatalogResponse>("get_node_catalog");
    if (result !== null) {
      return result;
    }
    await delay(120);
    return {
      schema_version: "1.0",
      node_definitions: demoWorkspace.node_definitions ?? [],
      plugin_errors: []
    };
  },

  async createProject(input) {
    const result = await tryInvoke<ProjectSummary>("create_project", { input });
    if (result !== null) {
      return result;
    }
    await delay(120);
    return {
      ...demoProjectSummary,
      id: `project-${Date.now()}`,
      name: input.name,
      description: input.description,
      updated_at: new Date().toISOString()
    };
  },

  async openProject(projectId) {
    const result = await tryInvoke<ProjectSummary>("open_project", { projectId });
    if (result !== null) {
      return result;
    }
    await delay(120);
    return {
      ...demoProjectSummary,
      id: projectId,
      updated_at: new Date().toISOString()
    };
  },

  async duplicateProject(input) {
    const result = await tryInvoke<ProjectSummary>("duplicate_project", {
      input: {
        projectId: input.projectId,
        name: input.name
      }
    });
    if (result !== null) {
      return result;
    }
    await delay(220);
    return {
      ...demoProjectSummary,
      id: `project-${Date.now()}`,
      name: input.name ?? `${demoProjectSummary.name} 副本`,
      updated_at: new Date().toISOString()
    };
  },

  async deleteProject(projectId) {
    const result = await tryInvoke<DeleteProjectResponse>("delete_project", { projectId });
    if (result !== null) {
      return result;
    }
    await delay(180);
    return {
      project_id: projectId,
      deleted_path: `projects/${projectId}.tfproj`
    };
  },

  async importProjectFiles(projectId, filePaths, importTemplate) {
    const result = await tryInvoke<ImportProjectFilesResponse>("import_project_files", {
      projectId,
      filePaths,
      importTemplate
    });
    if (result !== null) {
      return result;
    }
    await delay(300);
    return {
      project_id: projectId,
      imported_documents: filePaths.length,
      source_files: filePaths.map((path, index) => ({
        id: `${index}-${path}`,
        name: path.split(/[\\/]/).at(-1) ?? path,
        relative_path: `corpus/imported/${path.split(/[\\/]/).at(-1) ?? `file-${index}.txt`}`,
        row_count: 1
      })),
      document_count: demoWorkspace.corpus.length + filePaths.length,
      skipped_rows: 0,
      validation_issues: []
    };
  },

  async pickImportFiles() {
    const result = await tryInvoke<string[]>("pick_files");
    if (result !== null) {
      return result;
    }
    await delay(50);
    return [];
  },

  async pickJsonFile() {
    const result = await tryInvoke<string | null>("pick_json_file");
    if (result !== null) {
      return result;
    }
    await delay(50);
    return null;
  },

  async saveJsonFilePath(defaultFileName) {
    const result = await tryInvoke<string | null>("save_json_file_path", { defaultFileName });
    if (result !== null) {
      return result;
    }
    await delay(50);
    return null;
  },

  async pickProjectPackageFile() {
    const result = await tryInvoke<string | null>("pick_project_package_file");
    if (result !== null) {
      return result;
    }
    await delay(50);
    return null;
  },

  async saveProjectPackagePath(defaultFileName) {
    const result = await tryInvoke<string | null>("save_project_package_path", { defaultFileName });
    if (result !== null) {
      return result;
    }
    await delay(50);
    return null;
  },

  async importProjectPackage(path) {
    const result = await tryInvoke<ProjectSummary>("import_project_package", { path });
    if (result !== null) {
      return result;
    }
    await delay(180);
    return {
      ...demoProjectSummary,
      id: `project-imported-${Date.now()}`,
      path,
      updated_at: new Date().toISOString()
    };
  },

  async runWorkflow(projectId) {
    const result = await tryInvoke<RunWorkflowResponse>("run_workflow", { projectId });
    if (result !== null) {
      return result;
    }
    await delay(1_100);
    return {
      run: createSimulatedRun(),
      project: demoWorkspace.current_project!
    };
  },

  async exportProject(projectId, formats) {
    const result = await tryInvoke<ExportProjectResponse>("export_project", { projectId, formats });
    if (result !== null) {
      return result;
    }
    await delay(300);
    const files = formats.map((format) => ({
      path: `C:/Users/demo/Documents/TextFlow/demo.tfproj/exports/demo-export.${format}`,
      relative_path: `exports/demo-export.${format}`
    }));
    return {
      project_id: projectId,
      export_dir: "C:/Users/demo/Documents/TextFlow/demo.tfproj/exports",
      relative_export_dir: "exports",
      files
    };
  },

  async exportProjectBackup(projectId, path) {
    const result = await tryInvoke<ExportProjectBackupResponse>("export_project_backup", { projectId, path });
    if (result !== null) {
      return result;
    }
    await delay(200);
    return {
      path: path ?? `exports/backups/${projectId}.tfproj`,
      relative_path: path ?? `exports/backups/${projectId}.tfproj`
    };
  },

  async updateCorpusDocument(projectId, document) {
    const result = await tryInvoke<UpdateCorpusDocumentResponse>("update_corpus_document", { projectId, document });
    if (result !== null) {
      return result;
    }
    await delay(180);
    return {
      document,
      document_count: demoWorkspace.corpus.length
    };
  },

  async deleteCorpusDocument(projectId, docId) {
    const result = await tryInvoke<DeleteCorpusDocumentResponse>("delete_corpus_document", { projectId, docId });
    if (result !== null) {
      return result;
    }
    await delay(120);
    return {
      doc_id: docId,
      document_count: Math.max(0, demoWorkspace.corpus.length - 1)
    };
  },

  async saveIngestionSpec(projectId, spec) {
    const result = await tryInvoke<SaveIngestionSpecResponse | IngestionSpec>("save_ingestion_spec", { projectId, spec });
    if (result !== null) {
      return "spec" in result ? result : { spec: result };
    }
    await delay(120);
    const project = demoWorkspace.current_project!;
    const specId = spec.id ?? `ingest-${Date.now()}`;
    const saved: IngestionSpec = {
      id: specId,
      name: spec.name ?? "当前导入规格",
      source_profile: spec.source_profile ?? project.import_template.source_profile,
      field_mappings: spec.field_mappings ?? [],
      text_build: spec.text_build ?? {},
      dedupe_rules: spec.dedupe_rules ?? {}
    };
    const existingIndex = project.ingestion_specs.findIndex((item) => item.id === specId);
    if (existingIndex >= 0) {
      project.ingestion_specs[existingIndex] = saved;
    } else {
      project.ingestion_specs.push(saved);
    }
    project.updated_at = new Date().toISOString();
    return {
      spec: saved,
      project,
      project_updated_at: project.updated_at
    };
  },

  async listIngestionSpecs(projectId) {
    const result = await tryInvoke<ListIngestionSpecsResponse | IngestionSpec[]>("list_ingestion_specs", { projectId });
    if (result !== null) {
      return Array.isArray(result) ? { project_id: projectId, specs: result } : result;
    }
    await delay(80);
    return {
      project_id: projectId,
      specs: demoWorkspace.current_project!.ingestion_specs
    };
  },

  async createCorpusView(projectId, view) {
    const result = await tryInvoke<CorpusViewMutationResponse | CorpusView>("create_corpus_view", { projectId, view });
    if (result !== null) {
      return "view" in result ? result : { view: result };
    }
    await delay(120);
    const project = demoWorkspace.current_project!;
    const created: CorpusView = {
      id: view.id ?? `view-${Date.now()}`,
      name: view.name ?? "当前语料视图",
      resource_ids: view.resource_ids ?? project.corpus_resources.map((resource) => resource.id),
      filter_spec: view.filter_spec ?? {},
      doc_ids: view.doc_ids ?? demoWorkspace.corpus.map((doc) => doc.doc_id)
    };
    project.corpus_views.push(created);
    project.updated_at = new Date().toISOString();
    return {
      view: created,
      project,
      project_updated_at: project.updated_at
    };
  },

  async updateCorpusView(projectId, view) {
    const result = await tryInvoke<CorpusViewMutationResponse | CorpusView>("update_corpus_view", { projectId, view });
    if (result !== null) {
      return "view" in result ? result : { view: result };
    }
    await delay(120);
    const project = demoWorkspace.current_project!;
    const existing = project.corpus_views.find((item) => item.id === view.id);
    if (!existing) {
      throw new Error(`Corpus view ${view.id} not found`);
    }
    const updated: CorpusView = { ...existing, ...view };
    project.corpus_views = project.corpus_views.map((item) => item.id === view.id ? updated : item);
    project.updated_at = new Date().toISOString();
    return {
      view: updated,
      project,
      project_updated_at: project.updated_at
    };
  },

  async deleteCorpusView(projectId, viewId) {
    const result = await tryInvoke<DeleteCorpusViewResponse | CorpusView>("delete_corpus_view", { projectId, viewId });
    if (result !== null) {
      return "view_id" in result ? result : { view_id: viewId, removed: result };
    }
    await delay(100);
    const project = demoWorkspace.current_project!;
    const removed = project.corpus_views.find((view) => view.id === viewId);
    project.corpus_views = project.corpus_views.filter((view) => view.id !== viewId);
    project.updated_at = new Date().toISOString();
    return {
      view_id: viewId,
      removed,
      project,
      project_updated_at: project.updated_at
    };
  },

  async loadArtifactPreview(projectId, artifactId, limit = 50) {
    const result = await tryInvoke<ArtifactPreviewResponse>("load_artifact_preview", { projectId, artifactId, limit });
    if (result !== null) {
      return result;
    }
    await delay(130);
    const artifact = demoWorkspace.current_project!.artifact_records.find((item) => item.artifact_id === artifactId);
    return {
      artifact_id: artifactId,
      columns: ["artifact_id", "kind", "path", "row_count"],
      rows: artifact ? [{
        artifact_id: artifact.artifact_id,
        kind: artifact.kind,
        path: artifact.path,
        row_count: artifact.row_count ?? 0
      }] : [],
      row_count: artifact?.row_count ?? 0
    };
  },

  async listRunArtifacts(projectId, runId) {
    const result = await tryInvoke<ListRunArtifactsResponse | ArtifactRecord[]>("list_run_artifacts", { projectId, runId });
    if (result !== null) {
      return Array.isArray(result) ? { project_id: projectId, run_id: runId, artifacts: result } : result;
    }
    await delay(90);
    const artifacts = demoWorkspace.current_project!.artifact_records
      .filter((artifact) => !runId || artifact.run_id === runId);
    return {
      project_id: projectId,
      run_id: runId,
      artifacts
    };
  },

  async importDictionaryTable(projectId, kind, path) {
    const result = await tryInvoke<ImportDictionaryTableResponse>("import_dictionary_sheet", { projectId, kind, path });
    if (result !== null) {
      return result;
    }
    await delay(120);
    return {
      table: demoWorkspace.current_project!.dictionary_set.collections[kind].tables[0],
      dictionary_set: demoWorkspace.current_project!.dictionary_set
    };
  },

  async exportDictionaryTable(projectId, kind, tableId, path) {
    const result = await tryInvoke<{ kind: DictionaryKind; table_id: string; path: string }>("export_dictionary_sheet", {
      projectId,
      kind,
      tableId,
      path
    });
    if (result !== null) {
      return result;
    }
    await delay(90);
    return { kind, table_id: tableId, path };
  },

  async createReviewTask(projectId, input) {
    const result = await tryInvoke<CreateReviewTaskResponse>("create_review_task", {
      projectId,
      task: input
    });
    if (result !== null) {
      return result;
    }
    await delay(120);
    const project = demoWorkspace.current_project!;
    const tasks = simulatedReviewTasks(project);
    const task: ReviewTaskRecord = {
      review_id: `review-${Date.now()}`,
      project_id: projectId,
      review_type: input.review_type,
      status: "open",
      target_ref: input.target_ref,
      title: input.title ?? "新建复核任务",
      description: input.description,
      payload: input.payload,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    };
    tasks.unshift(task);
    return {
      task,
      project,
      project_updated_at: new Date().toISOString()
    };
  },

  async listReviewTasks(projectId, status) {
    const result = await tryInvoke<ListReviewTasksResponse>("list_review_tasks", {
      projectId,
      status
    });
    if (result !== null) {
      return result;
    }
    await delay(90);
    const project = demoWorkspace.current_project!;
    const tasks = simulatedReviewTasks(project).filter((task) => !status || task.status === status);
    return {
      project_id: projectId,
      tasks
    };
  },

  async resolveReviewTask(projectId, reviewId, resolution) {
    const result = await tryInvoke<ResolveReviewTaskResponse>("resolve_review_task", {
      projectId,
      reviewId,
      resolution
    });
    if (result !== null) {
      return result;
    }
    await delay(120);
    const project = demoWorkspace.current_project!;
    const tasks = simulatedReviewTasks(project);
    const task = tasks.find((item) => item.review_id === reviewId);
    if (!task) {
      throw new Error(`Review task ${reviewId} not found`);
    }
    task.status = "resolved";
    task.updated_at = new Date().toISOString();
    task.resolution = {
      ...resolution,
      applied_changes: resolution.decision === "reject" ? [] : ["demo-writeback"],
      resolved_at: new Date().toISOString()
    };
    return {
      task,
      project,
      corpus: demoWorkspace.corpus,
      source_files: project.source_files,
      project_updated_at: new Date().toISOString()
    };
  },

  async saveExperimentSpec(projectId, experiment) {
    const result = await tryInvoke<SaveExperimentSpecResponse>("save_experiment_spec", {
      projectId,
      experiment
    });
    if (result !== null) {
      return result;
    }
    await delay(120);
    const project = demoWorkspace.current_project!;
    const experiments = simulatedExperimentSpecs(project);
    const experimentId = experiment.experiment_id ?? `exp-${Date.now()}`;
    const saved: ExperimentSpec = {
      experiment_id: experimentId,
      name: experiment.name ?? "参数矩阵实验",
      workflow_id: experiment.workflow_id ?? project.active_workflow_id,
      variant_matrix: experiment.variant_matrix ?? [
        { label: "baseline", node_overrides: {} },
        { label: "high-keywords", node_overrides: { "node-keyword-extraction": { top_k_project: 24 } } }
      ]
    };
    const existingIndex = experiments.findIndex((item) => item.experiment_id === experimentId);
    if (existingIndex >= 0) {
      experiments[existingIndex] = saved;
    } else {
      experiments.push(saved);
    }
    project.updated_at = new Date().toISOString();
    return {
      experiment: saved,
      project,
      project_updated_at: project.updated_at
    };
  },

  async runExperimentMatrix(projectId, experimentId) {
    const result = await tryInvoke<RunExperimentMatrixResponse>("run_experiment_matrix", {
      projectId,
      experimentId
    });
    if (result !== null) {
      return result;
    }
    await delay(900);
    const project = demoWorkspace.current_project!;
    const experiment = simulatedExperimentSpecs(project).find((item) => item.experiment_id === experimentId)
      ?? {
        experiment_id: experimentId,
        name: "参数矩阵实验",
        workflow_id: project.active_workflow_id,
        variant_matrix: [
          { label: "baseline", node_overrides: {} },
          { label: "high-keywords", node_overrides: { "node-keyword-extraction": { top_k_project: 24 } } }
        ]
      };
    const runs = experiment.variant_matrix.map((variant, index) => ({
      ...createSimulatedRun(),
      run_id: `run-${Date.now()}-${index + 1}`,
      experiment_id: experiment.experiment_id,
      experiment_name: experiment.name,
      variant_label: String((variant as Record<string, unknown>).label ?? `variant-${index + 1}`),
      variant_index: index,
      variant_overrides: variant
    })) as RunRecord[];
    project.run_history = [...project.run_history, ...runs];
    project.updated_at = new Date().toISOString();
    return {
      experiment,
      runs,
      project,
      corpus: demoWorkspace.corpus
    };
  },

  async compareRuns(projectId, leftRunId, rightRunId) {
    const result = await tryInvoke<RunDiffSummary>("compare_runs", {
      projectId,
      leftRunId,
      rightRunId
    });
    if (result !== null) {
      return result;
    }
    await delay(160);
    const project = demoWorkspace.current_project!;
    const left = project.run_history.find((run) => run.run_id === leftRunId);
    const right = project.run_history.find((run) => run.run_id === rightRunId);
    const leftRows = left?.artifacts.reduce((total, artifact) => total + runArtifactRowCount(artifact), 0) ?? 0;
    const rightRows = right?.artifacts.reduce((total, artifact) => total + runArtifactRowCount(artifact), 0) ?? 0;
    return {
      left_run_id: leftRunId,
      right_run_id: rightRunId,
      summary: `Compared ${leftRunId} vs ${rightRunId}: artifact row delta ${rightRows - leftRows}.`,
      metrics: {
        processed_document_count: {
          left: left?.processed_document_count ?? 0,
          right: right?.processed_document_count ?? 0,
          delta: (right?.processed_document_count ?? 0) - (left?.processed_document_count ?? 0)
        }
      },
      artifact_diffs: [
        {
          step: "analysis",
          left_record_count: leftRows,
          right_record_count: rightRows,
          record_count_delta: rightRows - leftRows,
          added_files: [],
          removed_files: []
        }
      ]
    };
  },

  async saveProject(project) {
    const result = await tryInvoke<ProjectSummary>("save_project", { project });
    if (result !== null) {
      return result;
    }
    await delay(90);
    return {
      id: project.id,
      name: project.name,
      description: project.description,
      path: demoProjectSummary.path,
      updated_at: new Date().toISOString(),
      document_count: demoWorkspace.corpus.length,
      run_count: project.run_history.length
    };
  },

  async openPath(path) {
    const result = await tryInvoke<null>("open_path", { path });
    if (result !== null) {
      return;
    }
    await delay(30);
  },

  async revealPath(path) {
    const result = await tryInvoke<null>("reveal_path", { path });
    if (result !== null) {
      return;
    }
    await delay(30);
  },

  async subscribeProgress(listener) {
    const { isTauri } = await import("@tauri-apps/api/core");
    if (!isTauri()) {
      if (!devEngineBaseUrl()) {
        return () => {};
      }
      devEngineProgressListeners.add(listener);
      return () => {
        devEngineProgressListeners.delete(listener);
      };
    }
    const { listen } = await import("@tauri-apps/api/event");
    return listen<EngineProgressEvent>("engine-progress", (event) => {
      listener(event.payload);
    });
  }
};
