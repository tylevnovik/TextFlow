import {
  createContext,
  startTransition,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  useState,
  type PropsWithChildren
} from "react";
import type {
  CorpusView,
  DictionaryTableResource,
  CorpusItem,
  DictionaryKind,
  ExportFormat,
  ExperimentSpec,
  IngestionSpec,
  PageId,
  ProjectManifest,
  ProjectSummary,
  RunRecord,
  WorkflowNodeRuntimeState,
  WorkspaceSnapshot
} from "@textflow/shared-types";
import type {
  ArtifactPreviewResponse,
  CorpusViewMutationResponse,
  DeleteCorpusDocumentResponse,
  DeleteCorpusViewResponse,
  DeleteProjectResponse,
  EngineProgressEvent,
  ExportProjectResponse,
  ExportProjectBackupResponse,
  ImportProjectFilesResponse,
  ListReviewTasksResponse,
  ResolveReviewTaskResponse,
  RunDiffSummary,
  RunExperimentMatrixResponse,
  SaveIngestionSpecResponse,
  SaveExperimentSpecResponse
} from "../bridge/desktopBridge";
import { desktopBridge } from "../bridge/desktopBridge";
import type { ReviewResolutionInput } from "../features/review/reviewTypes";
import { configureWorkflowNodeCatalog } from "../workflowNodeCatalog";

interface TaskProgressState {
  action: string;
  status: "idle" | "pending" | "running" | "completed" | "failed";
  value: number;
  message: string;
  detail?: EngineProgressEvent["detail"];
}

interface WorkspaceState {
  activePage: PageId;
  snapshot: WorkspaceSnapshot;
  loading: boolean;
  statusLine: string;
  lastExport: ExportProjectResponse | null;
  lastRunDiff: RunDiffSummary | null;
  uiScale: number;
}

type WorkspaceAction =
  | { type: "setPage"; page: PageId }
  | { type: "setLoading"; loading: boolean; statusLine?: string }
  | { type: "loadSnapshot"; snapshot: WorkspaceSnapshot; statusLine?: string }
  | { type: "setStatus"; statusLine: string }
  | { type: "prependProject"; project: ProjectSummary }
  | { type: "patchProject"; project: ProjectManifest; summary: ProjectSummary; statusLine?: string }
  | {
      type: "applyLocalPatch";
      project?: ProjectManifest;
      summary?: ProjectSummary;
      corpus?: CorpusItem[];
      appendCorpus?: CorpusItem[];
      patchDocument?: CorpusItem;
      removeDocId?: string;
      sourceFiles?: ProjectManifest["source_files"];
      dictionarySet?: ProjectManifest["dictionary_set"];
      projectUpdatedAt?: string;
      loading?: boolean;
      statusLine?: string;
    }
  | { type: "setLastExport"; lastExport: ExportProjectResponse | null }
  | { type: "setRunDiff"; lastRunDiff: RunDiffSummary | null }
  | { type: "setUiScale"; uiScale: number };

interface SaveProjectOptions {
  refresh?: boolean;
  actionLabel?: string;
}

interface WorkspaceContextValue {
  state: WorkspaceState;
  setActivePage: (page: PageId) => void;
  setUiScale: (uiScale: number) => void;
  refresh: (actionLabel?: string) => Promise<void>;
  createProject: (name: string, description: string) => Promise<void>;
  openProject: (projectId: string) => Promise<void>;
  duplicateProject: (projectId: string, name?: string) => Promise<void>;
  deleteProject: (projectId: string) => Promise<DeleteProjectResponse | null>;
  pickImportFiles: () => Promise<string[]>;
  importProjectFiles: (
    filePaths: string[],
    importTemplate?: ProjectManifest["import_template"]
  ) => Promise<ImportProjectFilesResponse | null>;
  importDictionaryTable: (kind: DictionaryKind, path: string) => Promise<DictionaryTableResource | null>;
  exportDictionaryTable: (kind: DictionaryKind, tableId: string, path: string) => Promise<{ kind: DictionaryKind; table_id: string; path: string } | null>;
  pickJsonFile: () => Promise<string | null>;
  saveJsonFilePath: (defaultFileName?: string) => Promise<string | null>;
  pickProjectPackageFile: () => Promise<string | null>;
  saveProjectPackagePath: (defaultFileName?: string) => Promise<string | null>;
  importProjectPackage: (path: string) => Promise<void>;
  saveProject: (project: ProjectManifest, options?: SaveProjectOptions) => Promise<boolean>;
  runWorkflow: () => Promise<RunRecord | null>;
  saveIngestionSpec: (spec: Partial<IngestionSpec>) => Promise<SaveIngestionSpecResponse | null>;
  createCorpusView: (view: Partial<CorpusView>) => Promise<CorpusViewMutationResponse | null>;
  updateCorpusView: (view: Partial<CorpusView> & { id: string }) => Promise<CorpusViewMutationResponse | null>;
  deleteCorpusView: (viewId: string) => Promise<DeleteCorpusViewResponse | null>;
  loadArtifactPreview: (artifactId: string, limit?: number) => Promise<ArtifactPreviewResponse | null>;
  listReviewTasks: (status?: string) => Promise<ListReviewTasksResponse | null>;
  saveExperimentSpec: (experiment: Partial<ExperimentSpec>) => Promise<SaveExperimentSpecResponse | null>;
  runExperimentMatrix: (experimentId: string) => Promise<RunExperimentMatrixResponse | null>;
  compareRuns: (leftRunId: string, rightRunId: string) => Promise<RunDiffSummary | null>;
  exportProject: (formats: ExportFormat[]) => Promise<ExportProjectResponse | null>;
  openPath: (path: string) => Promise<void>;
  revealPath: (path: string) => Promise<void>;
  exportProjectBackup: (path?: string) => Promise<ExportProjectBackupResponse | null>;
  updateCorpusDocument: (document: CorpusItem) => Promise<CorpusItem | null>;
  deleteCorpusDocument: (docId: string) => Promise<DeleteCorpusDocumentResponse | null>;
  resolveReviewTask: (reviewId: string, resolution: ReviewResolutionInput) => Promise<ResolveReviewTaskResponse | null>;
}

const emptySnapshot: WorkspaceSnapshot = {
  recent_projects: [],
  corpus: []
};

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);
const UI_SCALE_STORAGE_KEY = "textflow.uiScale";
const DEFAULT_UI_SCALE = 1;
const MIN_UI_SCALE = 0.8;
const MAX_UI_SCALE = 1.2;

const idleProgress: TaskProgressState = {
  action: "",
  status: "idle",
  value: 0,
  message: ""
};

const TaskProgressContext = createContext<TaskProgressState>(idleProgress);

function sameProgressState(left: TaskProgressState, right: TaskProgressState): boolean {
  return (
    left.action === right.action &&
    left.status === right.status &&
    left.message === right.message &&
    Math.abs(left.value - right.value) < 0.005 &&
    progressDetailSignature(left.detail) === progressDetailSignature(right.detail)
  );
}

function workflowNodeStateSignature(detail: Extract<NonNullable<TaskProgressState["detail"]>, { kind: "workflow_run" }>): string {
  const sourceStates = detail.full_node_state_sync
    ? detail.node_states ?? {}
    : {
        ...(detail.node_states ?? {}),
        ...(detail.node_state_delta ?? {})
      };
  return Object.entries(sourceStates)
    .sort(([leftNodeId], [rightNodeId]) => leftNodeId.localeCompare(rightNodeId))
    .map(([nodeId, nodeState]) => [
      nodeId,
      nodeState.status,
      Math.round((nodeState.progress ?? 0) * 1000),
      nodeState.detail ?? "",
      nodeState.output_summary ?? "",
      nodeState.duration_ms ?? "",
      nodeState.error ?? ""
    ].join("~"))
    .join(",");
}

function progressDetailSignature(detail: TaskProgressState["detail"]): string {
  if (!detail) {
    return "";
  }
  if (detail.kind === "workflow_run") {
    return [
      detail.kind,
      detail.stage,
      detail.current_node_id ?? "",
      detail.current_node_label ?? "",
      String(detail.completed_nodes),
      String(detail.total_nodes),
      detail.detail ?? "",
      detail.full_node_state_sync ? "1" : "0",
      workflowNodeStateSignature(detail)
    ].join("|");
  }
  if ("node_label" in detail) {
    return `${detail.kind ?? "node"}|${detail.node_label ?? ""}|${detail.detail ?? ""}`;
  }
  return `${detail.kind ?? ""}`;
}

function mergeWorkflowRunDetail(
  previous: TaskProgressState["detail"],
  incoming: NonNullable<TaskProgressState["detail"]>
): TaskProgressState["detail"] {
  if (incoming.kind !== "workflow_run") {
    return incoming;
  }
  const previousWorkflowDetail = previous?.kind === "workflow_run" ? previous : undefined;
  const nextNodeStates = incoming.full_node_state_sync
    ? { ...(incoming.node_states ?? {}), ...(incoming.node_state_delta ?? {}) }
    : {
        ...(previousWorkflowDetail?.node_states ?? {}),
        ...(incoming.node_states ?? {}),
        ...(incoming.node_state_delta ?? {})
      };
  return {
    ...(previousWorkflowDetail ?? {}),
    ...incoming,
    node_states: nextNodeStates,
    node_state_delta: incoming.node_state_delta ?? {},
    full_node_state_sync: Boolean(incoming.full_node_state_sync)
  };
}

function completedWorkflowNodeCount(nodeStates: Record<string, WorkflowNodeRuntimeState>): number {
  return Object.values(nodeStates).filter((nodeState) => nodeState.status !== "pending" && nodeState.status !== "running").length;
}

function workflowNodeStatesFromRun(run: RunRecord): Record<string, WorkflowNodeRuntimeState> {
  const nodeRuns = run.node_runs ?? [];
  const totalNodes = Math.max(nodeRuns.length, 1);
  return nodeRuns.reduce<Record<string, WorkflowNodeRuntimeState>>((accumulator, nodeRun, index) => {
    accumulator[nodeRun.node_id] = {
      node_id: nodeRun.node_id,
      node_type: nodeRun.node_type,
      label: nodeRun.label,
      status: nodeRun.status,
      node_index: index + 1,
      total_nodes: totalNodes,
      progress: 1,
      started_at: nodeRun.started_at,
      ended_at: nodeRun.ended_at,
      duration_ms: nodeRun.duration_ms,
      cache_hit: nodeRun.cache_hit,
      cache_key: nodeRun.cache_key,
      cache_path: nodeRun.cache_path,
      output_ports: nodeRun.output_ports,
      output_summary: nodeRun.output_summary,
      sample_outputs: nodeRun.sample_outputs,
      output_previews: nodeRun.output_previews,
      error: nodeRun.error
    };
    return accumulator;
  }, {});
}

function completeWorkflowRunDetail(
  previous: TaskProgressState["detail"],
  run?: RunRecord,
  message?: string
): TaskProgressState["detail"] {
  const previousWorkflowDetail = previous?.kind === "workflow_run" ? previous : undefined;
  const runNodeStates = run ? workflowNodeStatesFromRun(run) : {};
  let nodeStates = Object.keys(runNodeStates).length
    ? runNodeStates
    : { ...(previousWorkflowDetail?.node_states ?? {}) };

  const activeNodeId = previousWorkflowDetail?.current_node_id;
  if (!Object.keys(runNodeStates).length && activeNodeId && nodeStates[activeNodeId]?.status === "running") {
    nodeStates = {
      ...nodeStates,
      [activeNodeId]: {
        ...nodeStates[activeNodeId],
        status: "completed",
        progress: 1,
        detail: message || nodeStates[activeNodeId].detail
      }
    };
  }

  const totalNodes = Math.max(
    run?.node_runs?.length ?? previousWorkflowDetail?.total_nodes ?? Object.keys(nodeStates).length,
    0
  );
  const completedNodes = Object.keys(nodeStates).length
    ? completedWorkflowNodeCount(nodeStates)
    : Math.max(previousWorkflowDetail?.completed_nodes ?? 0, totalNodes);

  return {
    ...(previousWorkflowDetail ?? { kind: "workflow_run" as const }),
    run_id: run?.run_id ?? previousWorkflowDetail?.run_id,
    workflow_id: run?.workflow_id ?? previousWorkflowDetail?.workflow_id,
    workflow_name: run?.workflow_name ?? previousWorkflowDetail?.workflow_name,
    stage: "completed",
    total_nodes: totalNodes,
    completed_nodes: Math.max(completedNodes, previousWorkflowDetail?.completed_nodes ?? 0),
    current_node_id: undefined,
    current_node_label: undefined,
    current_node_index: undefined,
    last_completed_node_id: run?.node_runs?.at(-1)?.node_id ?? activeNodeId ?? previousWorkflowDetail?.last_completed_node_id,
    detail: message || previousWorkflowDetail?.detail || run?.output_summary || "流程已完成",
    node_states: nodeStates,
    node_state_delta: nodeStates,
    full_node_state_sync: true
  };
}

function normalizeProgressDetail(
  event: EngineProgressEvent,
  previous: TaskProgressState
): TaskProgressState["detail"] {
  if (event.detail) {
    return mergeWorkflowRunDetail(previous.detail, event.detail);
  }
  if (event.action === "run-workflow" && event.status === "completed" && previous.detail?.kind === "workflow_run") {
    return completeWorkflowRunDetail(previous.detail, undefined, event.message);
  }
  const nodeMatch = event.message.match(/^正在执行节点：(.+)$/);
  if (nodeMatch) {
    return {
      kind: "node",
      node_label: nodeMatch[1].trim()
    };
  }
  if (event.action === "run-workflow" && event.status === "running" && previous.detail?.kind === "node") {
    return previous.detail;
  }
  return undefined;
}

function clampUiScale(uiScale: number): number {
  if (!Number.isFinite(uiScale)) {
    return DEFAULT_UI_SCALE;
  }
  return Math.min(MAX_UI_SCALE, Math.max(MIN_UI_SCALE, Number(uiScale.toFixed(2))));
}

function readStoredUiScale(): number {
  if (typeof window === "undefined") {
    return DEFAULT_UI_SCALE;
  }
  const storedValue = window.localStorage.getItem(UI_SCALE_STORAGE_KEY);
  if (!storedValue) {
    return DEFAULT_UI_SCALE;
  }
  return clampUiScale(Number(storedValue));
}

function formatErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === "string") {
    return error;
  }
  try {
    return JSON.stringify(error);
  } catch {
    return "未知错误";
  }
}

function projectWithIngestionSpec(
  project: ProjectManifest,
  spec: IngestionSpec,
  updatedAt?: string
): ProjectManifest {
  const existingIndex = project.ingestion_specs.findIndex((item) => item.id === spec.id);
  const ingestionSpecs = existingIndex >= 0
    ? project.ingestion_specs.map((item, index) => index === existingIndex ? spec : item)
    : [...project.ingestion_specs, spec];
  return {
    ...project,
    updated_at: updatedAt ?? project.updated_at,
    ingestion_specs: ingestionSpecs
  };
}

function projectWithCorpusView(
  project: ProjectManifest,
  view: CorpusView,
  updatedAt?: string
): ProjectManifest {
  const existingIndex = project.corpus_views.findIndex((item) => item.id === view.id);
  const corpusViews = existingIndex >= 0
    ? project.corpus_views.map((item, index) => index === existingIndex ? view : item)
    : [...project.corpus_views, view];
  return {
    ...project,
    updated_at: updatedAt ?? project.updated_at,
    corpus_views: corpusViews
  };
}

function projectWithoutCorpusView(
  project: ProjectManifest,
  viewId: string,
  updatedAt?: string
): ProjectManifest {
  return {
    ...project,
    updated_at: updatedAt ?? project.updated_at,
    corpus_views: project.corpus_views.filter((view) => view.id !== viewId)
  };
}

function buildProjectSummary(
  project: ProjectManifest,
  corpus: CorpusItem[],
  recentProjects: ProjectSummary[],
  summary?: ProjectSummary
): ProjectSummary {
  if (summary) {
    return summary;
  }
  const existingSummary = recentProjects.find((item) => item.id === project.id);
  return {
    id: project.id,
    name: project.name,
    description: project.description,
    path: existingSummary?.path ?? project.paths.root,
    updated_at: project.updated_at,
    document_count: corpus.length,
    run_count: project.run_history.length
  };
}

function reducer(state: WorkspaceState, action: WorkspaceAction): WorkspaceState {
  switch (action.type) {
    case "setPage":
      return { ...state, activePage: action.page };
    case "setLoading":
      return {
        ...state,
        loading: action.loading,
        statusLine: action.statusLine ?? state.statusLine
      };
    case "loadSnapshot":
      return {
        ...state,
        loading: false,
        snapshot: action.snapshot,
        lastExport: state.lastExport?.project_id === action.snapshot.current_project?.id ? state.lastExport : null,
        lastRunDiff: action.snapshot.current_project
          ? state.lastRunDiff
          : null,
        statusLine: action.statusLine ?? state.statusLine
      };
    case "setStatus":
      return { ...state, statusLine: action.statusLine };
    case "prependProject":
      return {
        ...state,
        snapshot: {
          ...state.snapshot,
          recent_projects: [action.project, ...state.snapshot.recent_projects.filter((item) => item.id !== action.project.id)]
        }
      };
    case "patchProject":
      return {
        ...state,
        loading: false,
        snapshot: {
          ...state.snapshot,
          current_project: action.project,
          recent_projects: [
            action.summary,
            ...state.snapshot.recent_projects.filter((item) => item.id !== action.summary.id)
          ]
        },
        statusLine: action.statusLine ?? state.statusLine
      };
    case "applyLocalPatch": {
      const currentProject = action.project ?? state.snapshot.current_project;
      let nextProject = currentProject;
      if (nextProject && action.sourceFiles) {
        nextProject = {
          ...nextProject,
          source_files: action.sourceFiles
        };
      }
      if (nextProject && action.dictionarySet) {
        nextProject = {
          ...nextProject,
          dictionary_set: action.dictionarySet
        };
      }
      if (nextProject && action.projectUpdatedAt) {
        nextProject = {
          ...nextProject,
          updated_at: action.projectUpdatedAt
        };
      }

      let nextCorpus = action.corpus ?? state.snapshot.corpus;
      if (action.appendCorpus?.length) {
        const appendLookup = new Map(action.appendCorpus.map((item) => [item.doc_id, item]));
        nextCorpus = [
          ...nextCorpus.filter((item) => !appendLookup.has(item.doc_id)),
          ...action.appendCorpus
        ];
      }
      if (action.patchDocument) {
        const hasExisting = nextCorpus.some((item) => item.doc_id === action.patchDocument!.doc_id);
        nextCorpus = hasExisting
          ? nextCorpus.map((item) => (item.doc_id === action.patchDocument!.doc_id ? action.patchDocument! : item))
          : [...nextCorpus, action.patchDocument];
      }
      if (action.removeDocId) {
        nextCorpus = nextCorpus.filter((item) => item.doc_id !== action.removeDocId);
      }

      const nextSummary = nextProject
        ? buildProjectSummary(nextProject, nextCorpus, state.snapshot.recent_projects, action.summary)
        : undefined;

      return {
        ...state,
        loading: action.loading ?? false,
        snapshot: {
          ...state.snapshot,
          current_project: nextProject,
          corpus: nextCorpus,
          recent_projects: nextSummary
            ? [nextSummary, ...state.snapshot.recent_projects.filter((item) => item.id !== nextSummary.id)]
            : state.snapshot.recent_projects
        },
        statusLine: action.statusLine ?? state.statusLine
      };
    }
    case "setLastExport":
      return {
        ...state,
        lastExport: action.lastExport
      };
    case "setRunDiff":
      return {
        ...state,
        lastRunDiff: action.lastRunDiff
      };
    case "setUiScale":
      return {
        ...state,
        uiScale: clampUiScale(action.uiScale)
      };
    default:
      return state;
  }
}

const initialState: WorkspaceState = {
  activePage: "home",
  snapshot: emptySnapshot,
  loading: true,
  statusLine: "正在准备工作台...",
  lastExport: null,
  lastRunDiff: null,
  uiScale: DEFAULT_UI_SCALE
};

export function WorkspaceProvider({ children }: PropsWithChildren) {
  const [state, dispatch] = useReducer(reducer, initialState, (baseState) => ({
    ...baseState,
    uiScale: readStoredUiScale()
  }));
  const [progress, setProgress] = useState<TaskProgressState>(idleProgress);
  const [lastActionAt, setLastActionAt] = useState<string>("尚未执行");

  const updateProgress = (next: TaskProgressState | ((previous: TaskProgressState) => TaskProgressState)) => {
    startTransition(() => {
      setProgress((previous) => {
        const resolved = typeof next === "function" ? next(previous) : next;
        if (sameProgressState(previous, resolved)) {
          return previous;
        }
        return resolved;
      });
    });
  };

  const failAction = (actionLabel: string, error: unknown) => {
    const message = `${actionLabel}失败：${formatErrorMessage(error)}`;
    updateProgress({
      action: actionLabel,
      status: "failed",
      value: 1,
      message
    });
    dispatch({
      type: "setLoading",
      loading: false,
      statusLine: message
    });
  };

  const refresh = async (actionLabel?: string) => {
    dispatch({
      type: "setLoading",
      loading: true,
      statusLine: "正在加载项目和语料..."
    });
    updateProgress({
      action: "load-workspace",
      status: "running",
      value: 0.06,
      message: "正在加载项目和语料..."
    });
    try {
      const snapshot = await desktopBridge.loadWorkspace();
      configureWorkflowNodeCatalog(snapshot.node_definitions ?? [], snapshot.port_compatibility);
      const effectiveAction = actionLabel ?? lastActionAt;
      dispatch({
        type: "loadSnapshot",
        snapshot,
        statusLine: snapshot.current_project
          ? `当前项目：${snapshot.current_project.name}，最近一次动作：${effectiveAction}`
          : "还没有项目，先创建一个 .tfproj 工作空间。"
      });
      updateProgress({
        action: "load-workspace",
        status: "completed",
        value: 1,
        message: "工作区已更新"
      });
    } catch (error) {
      failAction("加载工作区", error);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  useEffect(() => {
    let unlisten: (() => void) | null = null;
    void desktopBridge.subscribeProgress((event: EngineProgressEvent) => {
      const nextStatus = event.status === "failed"
        ? "failed"
        : event.status === "completed"
          ? "completed"
          : "running";
      updateProgress((previous) => ({
        action: event.action,
        status: nextStatus,
        value: Math.max(0, Math.min(1, event.progress)),
        message: event.message,
        detail: normalizeProgressDetail(event, previous)
      }));
    }).then((dispose) => {
      unlisten = dispose;
    });

    return () => {
      if (unlisten) {
        unlisten();
      }
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    window.localStorage.setItem(UI_SCALE_STORAGE_KEY, String(state.uiScale));
  }, [state.uiScale]);

  const value = useMemo<WorkspaceContextValue>(() => ({
    state,
    setActivePage: (page) => {
      dispatch({ type: "setPage", page });
    },
    setUiScale: (uiScale) => {
      dispatch({ type: "setUiScale", uiScale });
    },
    refresh,
    createProject: async (name, description) => {
      dispatch({ type: "setLoading", loading: true, statusLine: "正在创建项目..." });
      updateProgress({
        action: "create-project",
        status: "running",
        value: 0.04,
        message: "正在创建项目..."
      });
      try {
        const project = await desktopBridge.createProject({ name, description });
        dispatch({ type: "prependProject", project });
        setLastActionAt("新建项目");
        await refresh("新建项目");
      } catch (error) {
        failAction("新建项目", error);
      }
    },
    openProject: async (projectId) => {
      dispatch({ type: "setLoading", loading: true, statusLine: "正在打开项目..." });
      updateProgress({
        action: "open-project",
        status: "running",
        value: 0.04,
        message: "正在打开项目..."
      });
      try {
        await desktopBridge.openProject(projectId);
        setLastActionAt("打开项目");
        await refresh("打开项目");
      } catch (error) {
        failAction("打开项目", error);
      }
    },
    duplicateProject: async (projectId, name) => {
      dispatch({ type: "setLoading", loading: true, statusLine: "正在复制项目..." });
      updateProgress({
        action: "duplicate-project",
        status: "running",
        value: 0.04,
        message: "正在复制项目..."
      });
      try {
        await desktopBridge.duplicateProject({ projectId, name });
        setLastActionAt("复制项目");
        await refresh("复制项目");
      } catch (error) {
        failAction("复制项目", error);
      }
    },
    deleteProject: async (projectId) => {
      dispatch({ type: "setLoading", loading: true, statusLine: "正在删除项目..." });
      updateProgress({
        action: "delete-project",
        status: "running",
        value: 0.04,
        message: "正在删除项目..."
      });
      try {
        const result = await desktopBridge.deleteProject(projectId);
        setLastActionAt("删除项目");
        await refresh("删除项目");
        return result;
      } catch (error) {
        failAction("删除项目", error);
        return null;
      }
    },
    pickImportFiles: async () => desktopBridge.pickImportFiles(),
    importProjectFiles: async (filePaths, importTemplate) => {
      const projectId = state.snapshot.current_project?.id;
      if (!projectId) {
        dispatch({ type: "setStatus", statusLine: "请先创建或打开项目，再导入语料。" });
        return null;
      }
      dispatch({ type: "setLoading", loading: true, statusLine: "正在导入文件并更新语料库..." });
      updateProgress({
        action: "import-project-files",
        status: "running",
        value: 0.04,
        message: "正在导入文件并更新语料库..."
      });
      try {
        const result = await desktopBridge.importProjectFiles(projectId, filePaths, importTemplate);
        const actionLabel = result.skipped_rows
          ? `导入 ${result.imported_documents} 篇文档，跳过 ${result.skipped_rows} 行`
          : `导入 ${result.imported_documents} 篇文档`;
        setLastActionAt(actionLabel);
        if (result.project || result.documents?.length) {
          dispatch({
            type: "applyLocalPatch",
            project: result.project,
            appendCorpus: result.documents,
            loading: false,
            statusLine: actionLabel
          });
          updateProgress({
            action: "import-project-files",
            status: "completed",
            value: 1,
            message: `${actionLabel}完成`
          });
        } else {
          await refresh(actionLabel);
        }
        return result;
      } catch (error) {
        failAction("导入文件", error);
        return null;
      }
    },
    importDictionaryTable: async (kind, path) => {
      const projectId = state.snapshot.current_project?.id;
      if (!projectId) {
        dispatch({ type: "setStatus", statusLine: "请先创建或打开项目，再导入词表。" });
        return null;
      }
      dispatch({ type: "setLoading", loading: true, statusLine: "正在导入词表..." });
      updateProgress({
        action: "import-dictionary-sheet",
        status: "running",
        value: 0.04,
        message: "正在导入词表..."
      });
      try {
        const imported = await desktopBridge.importDictionaryTable(projectId, kind, path);
        setLastActionAt(`导入词表 ${kind}`);
        if (imported.dictionary_set) {
          dispatch({
            type: "applyLocalPatch",
            dictionarySet: imported.dictionary_set,
            projectUpdatedAt: imported.project_updated_at,
            loading: false,
            statusLine: `导入词表 ${kind} 完成`
          });
          updateProgress({
            action: "import-dictionary-sheet",
            status: "completed",
            value: 1,
            message: `导入词表 ${kind} 完成`
          });
        } else {
          await refresh(`导入词表 ${kind}`);
        }
        return imported.table;
      } catch (error) {
        failAction(`导入词表 ${kind}`, error);
        return null;
      }
    },
    exportDictionaryTable: async (kind, tableId, path) => {
      const projectId = state.snapshot.current_project?.id;
      if (!projectId) {
        dispatch({ type: "setStatus", statusLine: "当前没有可导出的词表。" });
        return null;
      }
      dispatch({ type: "setLoading", loading: true, statusLine: "正在导出词表..." });
      updateProgress({
        action: "export-dictionary-sheet",
        status: "running",
        value: 0.04,
        message: "正在导出词表..."
      });
      try {
        const result = await desktopBridge.exportDictionaryTable(projectId, kind, tableId, path);
        dispatch({
          type: "setLoading",
          loading: false,
          statusLine: `词表已导出到 ${path}`
        });
        setLastActionAt(`导出词表 ${kind}`);
        return result;
      } catch (error) {
        failAction(`导出词表 ${kind}`, error);
        return null;
      }
    },
    pickJsonFile: async () => desktopBridge.pickJsonFile(),
    saveJsonFilePath: async (defaultFileName) => desktopBridge.saveJsonFilePath(defaultFileName),
    pickProjectPackageFile: async () => desktopBridge.pickProjectPackageFile(),
    saveProjectPackagePath: async (defaultFileName) => desktopBridge.saveProjectPackagePath(defaultFileName),
    importProjectPackage: async (path) => {
      dispatch({ type: "setLoading", loading: true, statusLine: "正在导入 .tfproj 项目包..." });
      updateProgress({
        action: "import-project-package",
        status: "running",
        value: 0.04,
        message: "正在导入 .tfproj 项目包..."
      });
      try {
        await desktopBridge.importProjectPackage(path);
        setLastActionAt("导入项目包");
        await refresh("导入项目包");
      } catch (error) {
        failAction("导入项目包", error);
      }
    },
    saveProject: async (project, options) => {
      const refreshAfterSave = options?.refresh ?? true;
      const actionLabel = options?.actionLabel ?? "保存项目配置";
      dispatch({ type: "setLoading", loading: true, statusLine: "正在保存项目配置..." });
      updateProgress({
        action: "save-project",
        status: "running",
        value: 0.04,
        message: "正在保存项目配置..."
      });
      try {
        const summary = await desktopBridge.saveProject(project);
        setLastActionAt(actionLabel);
        if (refreshAfterSave) {
          await refresh(actionLabel);
        } else {
          dispatch({
            type: "patchProject",
            project: {
              ...project,
              updated_at: summary.updated_at
            },
            summary,
            statusLine: `${actionLabel}已保存`
          });
          updateProgress({
            action: "save-project",
            status: "completed",
            value: 1,
            message: `${actionLabel}已保存`
          });
        }
        return true;
      } catch (error) {
        failAction(actionLabel, error);
        return false;
      }
    },
    runWorkflow: async () => {
      const projectId = state.snapshot.current_project?.id;
      if (!projectId) {
        dispatch({ type: "setStatus", statusLine: "请先创建或打开项目。" });
        return null;
      }
      dispatch({ type: "setLoading", loading: true, statusLine: "正在运行预处理与分析流程..." });
      updateProgress({
        action: "run-workflow",
        status: "running",
        value: 0.04,
        message: "正在运行预处理与分析流程..."
      });
      try {
        const response = await desktopBridge.runWorkflow(projectId);
        setLastActionAt("运行流程");
        dispatch({
          type: "applyLocalPatch",
          project: response.project,
          loading: false,
          statusLine: `当前项目：${response.project.name}，最近一次动作：运行流程`
        });
        updateProgress((previous) => {
          const message = previous.action === "run-workflow" && previous.status === "completed"
            ? previous.message
            : "运行流程完成";
          return {
            action: "run-workflow",
            status: "completed",
            value: 1,
            message,
            detail: completeWorkflowRunDetail(previous.detail, response.run, message)
          };
        });
        return response.run;
      } catch (error) {
        failAction("运行流程", error);
        return null;
      }
    },
    saveIngestionSpec: async (spec) => {
      const project = state.snapshot.current_project;
      if (!project) {
        dispatch({ type: "setStatus", statusLine: "请先创建或打开项目，再保存导入规格。" });
        return null;
      }
      dispatch({ type: "setLoading", loading: true, statusLine: "正在保存导入规格..." });
      updateProgress({
        action: "save-ingestion-spec",
        status: "running",
        value: 0.04,
        message: "正在保存导入规格..."
      });
      try {
        const result = await desktopBridge.saveIngestionSpec(project.id, spec);
        const nextProject = result.project ?? projectWithIngestionSpec(project, result.spec, result.project_updated_at);
        setLastActionAt("保存导入规格");
        dispatch({
          type: "applyLocalPatch",
          project: nextProject,
          projectUpdatedAt: result.project_updated_at,
          loading: false,
          statusLine: "导入规格已保存"
        });
        updateProgress({
          action: "save-ingestion-spec",
          status: "completed",
          value: 1,
          message: "导入规格已保存"
        });
        return result;
      } catch (error) {
        failAction("保存导入规格", error);
        return null;
      }
    },
    createCorpusView: async (view) => {
      const project = state.snapshot.current_project;
      if (!project) {
        dispatch({ type: "setStatus", statusLine: "请先创建或打开项目，再创建语料视图。" });
        return null;
      }
      dispatch({ type: "setLoading", loading: true, statusLine: "正在创建语料视图..." });
      updateProgress({
        action: "create-corpus-view",
        status: "running",
        value: 0.04,
        message: "正在创建语料视图..."
      });
      try {
        const result = await desktopBridge.createCorpusView(project.id, view);
        const nextProject = result.project ?? projectWithCorpusView(project, result.view, result.project_updated_at);
        setLastActionAt("创建语料视图");
        dispatch({
          type: "applyLocalPatch",
          project: nextProject,
          projectUpdatedAt: result.project_updated_at,
          loading: false,
          statusLine: "语料视图已创建"
        });
        updateProgress({
          action: "create-corpus-view",
          status: "completed",
          value: 1,
          message: "语料视图已创建"
        });
        return result;
      } catch (error) {
        failAction("创建语料视图", error);
        return null;
      }
    },
    updateCorpusView: async (view) => {
      const project = state.snapshot.current_project;
      if (!project) {
        dispatch({ type: "setStatus", statusLine: "请先创建或打开项目，再更新语料视图。" });
        return null;
      }
      dispatch({ type: "setLoading", loading: true, statusLine: "正在更新语料视图..." });
      updateProgress({
        action: "update-corpus-view",
        status: "running",
        value: 0.04,
        message: "正在更新语料视图..."
      });
      try {
        const result = await desktopBridge.updateCorpusView(project.id, view);
        const nextProject = result.project ?? projectWithCorpusView(project, result.view, result.project_updated_at);
        setLastActionAt("更新语料视图");
        dispatch({
          type: "applyLocalPatch",
          project: nextProject,
          projectUpdatedAt: result.project_updated_at,
          loading: false,
          statusLine: "语料视图已更新"
        });
        updateProgress({
          action: "update-corpus-view",
          status: "completed",
          value: 1,
          message: "语料视图已更新"
        });
        return result;
      } catch (error) {
        failAction("更新语料视图", error);
        return null;
      }
    },
    deleteCorpusView: async (viewId) => {
      const project = state.snapshot.current_project;
      if (!project) {
        dispatch({ type: "setStatus", statusLine: "请先创建或打开项目，再删除语料视图。" });
        return null;
      }
      dispatch({ type: "setLoading", loading: true, statusLine: "正在删除语料视图..." });
      updateProgress({
        action: "delete-corpus-view",
        status: "running",
        value: 0.04,
        message: "正在删除语料视图..."
      });
      try {
        const result = await desktopBridge.deleteCorpusView(project.id, viewId);
        const nextProject = result.project ?? projectWithoutCorpusView(project, viewId, result.project_updated_at);
        setLastActionAt("删除语料视图");
        dispatch({
          type: "applyLocalPatch",
          project: nextProject,
          projectUpdatedAt: result.project_updated_at,
          loading: false,
          statusLine: "语料视图已删除"
        });
        updateProgress({
          action: "delete-corpus-view",
          status: "completed",
          value: 1,
          message: "语料视图已删除"
        });
        return result;
      } catch (error) {
        failAction("删除语料视图", error);
        return null;
      }
    },
    loadArtifactPreview: async (artifactId, limit) => {
      const projectId = state.snapshot.current_project?.id;
      if (!projectId) {
        dispatch({ type: "setStatus", statusLine: "请先创建或打开项目，再读取产物预览。" });
        return null;
      }
      try {
        const preview = await desktopBridge.loadArtifactPreview(projectId, artifactId, limit);
        dispatch({ type: "setStatus", statusLine: `产物预览已加载：${artifactId}` });
        return preview;
      } catch (error) {
        failAction("读取产物预览", error);
        return null;
      }
    },
    listReviewTasks: async (status) => {
      const project = state.snapshot.current_project;
      if (!project) {
        dispatch({ type: "setStatus", statusLine: "请先创建或打开项目，再读取复核任务。" });
        return null;
      }
      try {
        const result = await desktopBridge.listReviewTasks(project.id, status);
        dispatch({
          type: "applyLocalPatch",
          project: {
            ...project,
            review_tasks: result.tasks as ProjectManifest["review_tasks"]
          },
          statusLine: "复核任务已加载"
        });
        return result;
      } catch (error) {
        failAction("读取复核任务", error);
        return null;
      }
    },
    saveExperimentSpec: async (experiment) => {
      const projectId = state.snapshot.current_project?.id;
      if (!projectId) {
        dispatch({ type: "setStatus", statusLine: "请先创建或打开项目，再保存实验规格。" });
        return null;
      }
      dispatch({ type: "setLoading", loading: true, statusLine: "正在保存实验规格..." });
      updateProgress({
        action: "save-experiment-spec",
        status: "running",
        value: 0.04,
        message: "正在保存实验规格..."
      });
      try {
        const result = await desktopBridge.saveExperimentSpec(projectId, experiment);
        setLastActionAt("保存实验规格");
        dispatch({
          type: "applyLocalPatch",
          project: result.project,
          projectUpdatedAt: result.project_updated_at,
          loading: false,
          statusLine: "实验规格已保存"
        });
        updateProgress({
          action: "save-experiment-spec",
          status: "completed",
          value: 1,
          message: "实验规格已保存"
        });
        return result;
      } catch (error) {
        failAction("保存实验规格", error);
        return null;
      }
    },
    runExperimentMatrix: async (experimentId) => {
      const projectId = state.snapshot.current_project?.id;
      if (!projectId) {
        dispatch({ type: "setStatus", statusLine: "请先创建或打开项目，再运行实验矩阵。" });
        return null;
      }
      dispatch({ type: "setLoading", loading: true, statusLine: "正在运行实验矩阵..." });
      updateProgress({
        action: "run-experiment-matrix",
        status: "running",
        value: 0.04,
        message: "正在运行实验矩阵..."
      });
      try {
        const result = await desktopBridge.runExperimentMatrix(projectId, experimentId);
        setLastActionAt("运行实验矩阵");
        dispatch({
          type: "applyLocalPatch",
          project: result.project,
          corpus: result.corpus,
          loading: false,
          statusLine: `实验矩阵已完成：${result.runs.length} 次运行`
        });
        updateProgress({
          action: "run-experiment-matrix",
          status: "completed",
          value: 1,
          message: `实验矩阵已完成：${result.runs.length} 次运行`
        });
        return result;
      } catch (error) {
        failAction("运行实验矩阵", error);
        return null;
      }
    },
    compareRuns: async (leftRunId, rightRunId) => {
      const projectId = state.snapshot.current_project?.id;
      if (!projectId) {
        dispatch({ type: "setStatus", statusLine: "请先创建或打开项目，再比较运行结果。" });
        return null;
      }
      dispatch({ type: "setLoading", loading: true, statusLine: "正在比较运行结果..." });
      updateProgress({
        action: "compare-runs",
        status: "running",
        value: 0.04,
        message: "正在比较运行结果..."
      });
      try {
        const diff = await desktopBridge.compareRuns(projectId, leftRunId, rightRunId);
        dispatch({ type: "setRunDiff", lastRunDiff: diff });
        dispatch({
          type: "setLoading",
          loading: false,
          statusLine: "运行结果对比已生成"
        });
        updateProgress({
          action: "compare-runs",
          status: "completed",
          value: 1,
          message: "运行结果对比已生成"
        });
        return diff;
      } catch (error) {
        failAction("比较运行结果", error);
        return null;
      }
    },
    exportProject: async (formats) => {
      const projectId = state.snapshot.current_project?.id;
      if (!projectId) {
        dispatch({ type: "setStatus", statusLine: "当前没有可导出的项目。" });
        return null;
      }
      dispatch({ type: "setLoading", loading: true, statusLine: "正在打包导出结果..." });
      updateProgress({
        action: "export-project",
        status: "running",
        value: 0.04,
        message: "正在打包导出结果..."
      });
      try {
        const exported = await desktopBridge.exportProject(projectId, formats);
        dispatch({ type: "setLastExport", lastExport: exported });
        try {
          await desktopBridge.openPath(exported.export_dir);
        } catch (openError) {
          dispatch({
            type: "setLoading",
            loading: false,
            statusLine: `导出完成：${exported.relative_export_dir}，但未能自动打开文件夹：${formatErrorMessage(openError)}`
          });
          setLastActionAt("导出结果");
          return exported;
        }
        dispatch({
          type: "setLoading",
          loading: false,
          statusLine: exported.files.length
            ? `导出完成，结果已放到 ${exported.relative_export_dir}，并已自动打开文件夹。`
            : "导出完成，但本次没有生成新文件。"
        });
        updateProgress({
          action: "export-project",
          status: "completed",
          value: 1,
          message: "导出结果完成"
        });
        setLastActionAt("导出结果");
        return exported;
      } catch (error) {
        failAction("导出结果", error);
        return null;
      }
    },
    openPath: async (path) => {
      await desktopBridge.openPath(path);
    },
    revealPath: async (path) => {
      await desktopBridge.revealPath(path);
    },
    exportProjectBackup: async (path) => {
      const projectId = state.snapshot.current_project?.id;
      if (!projectId) {
        dispatch({ type: "setStatus", statusLine: "当前没有可备份的项目。" });
        return null;
      }
      dispatch({ type: "setLoading", loading: true, statusLine: "正在打包完整项目备份..." });
      updateProgress({
        action: "export-project-backup",
        status: "running",
        value: 0.04,
        message: "正在打包完整项目备份..."
      });
      try {
        const backup = await desktopBridge.exportProjectBackup(projectId, path);
        dispatch({
          type: "setLoading",
          loading: false,
          statusLine: `项目包已生成：${backup.relative_path}`
        });
        setLastActionAt("导出项目包");
        return backup;
      } catch (error) {
        failAction("导出项目包", error);
        return null;
      }
    },
    updateCorpusDocument: async (document) => {
      const projectId = state.snapshot.current_project?.id;
      if (!projectId) {
        dispatch({ type: "setStatus", statusLine: "请先创建或打开项目。" });
        return null;
      }
      dispatch({ type: "setLoading", loading: true, statusLine: "正在保存语料文档..." });
      updateProgress({
        action: "update-corpus-document",
        status: "running",
        value: 0.04,
        message: "正在保存语料文档..."
      });
      try {
        const updated = await desktopBridge.updateCorpusDocument(projectId, document);
        setLastActionAt("保存语料文档");
        dispatch({
          type: "applyLocalPatch",
          patchDocument: updated.document,
          sourceFiles: updated.source_files,
          projectUpdatedAt: updated.project_updated_at,
          loading: false,
          statusLine: "保存语料文档完成"
        });
        updateProgress({
          action: "update-corpus-document",
          status: "completed",
          value: 1,
          message: "保存语料文档完成"
        });
        return updated.document;
      } catch (error) {
        failAction("保存语料文档", error);
        return null;
      }
    },
    deleteCorpusDocument: async (docId) => {
      const projectId = state.snapshot.current_project?.id;
      if (!projectId) {
        dispatch({ type: "setStatus", statusLine: "请先创建或打开项目。" });
        return null;
      }
      dispatch({ type: "setLoading", loading: true, statusLine: "正在删除语料文档..." });
      updateProgress({
        action: "delete-corpus-document",
        status: "running",
        value: 0.04,
        message: "正在删除语料文档..."
      });
      try {
        const result = await desktopBridge.deleteCorpusDocument(projectId, docId);
        setLastActionAt("删除语料文档");
        dispatch({
          type: "applyLocalPatch",
          removeDocId: result.doc_id,
          sourceFiles: result.source_files,
          projectUpdatedAt: result.project_updated_at,
          loading: false,
          statusLine: "删除语料文档完成"
        });
        updateProgress({
          action: "delete-corpus-document",
          status: "completed",
          value: 1,
          message: "删除语料文档完成"
        });
        return result;
      } catch (error) {
        failAction("删除语料文档", error);
        return null;
      }
    },
    resolveReviewTask: async (reviewId, resolution) => {
      const projectId = state.snapshot.current_project?.id;
      if (!projectId) {
        dispatch({ type: "setStatus", statusLine: "请先创建或打开项目。" });
        return null;
      }
      dispatch({ type: "setLoading", loading: true, statusLine: "正在写回复核结果..." });
      updateProgress({
        action: "resolve-review-task",
        status: "running",
        value: 0.04,
        message: "正在写回复核结果..."
      });
      try {
        const result = await desktopBridge.resolveReviewTask(projectId, reviewId, resolution);
        setLastActionAt(resolution.decision === "reject" ? "拒绝复核写回" : "写回复核结果");
        dispatch({
          type: "applyLocalPatch",
          project: result.project,
          corpus: result.corpus,
          sourceFiles: result.source_files,
          projectUpdatedAt: result.project_updated_at,
          loading: false,
          statusLine: resolution.decision === "reject" ? "复核任务已标记为拒绝" : "复核结果已写回项目"
        });
        updateProgress({
          action: "resolve-review-task",
          status: "completed",
          value: 1,
          message: resolution.decision === "reject" ? "复核任务已拒绝" : "复核结果已写回项目"
        });
        return result;
      } catch (error) {
        failAction(resolution.decision === "reject" ? "拒绝复核写回" : "写回复核结果", error);
        return null;
      }
    }
  }), [lastActionAt, state]);

  return (
    <TaskProgressContext.Provider value={progress}>
      <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>
    </TaskProgressContext.Provider>
  );
}

export function useWorkspace() {
  const value = useContext(WorkspaceContext);
  if (!value) {
    throw new Error("Workspace context is unavailable.");
  }
  return value;
}

export function useTaskProgress() {
  return useContext(TaskProgressContext);
}

export const workspaceStoreTestables = {
  sameProgressState,
  mergeWorkflowRunDetail,
  normalizeProgressDetail,
  workflowNodeStatesFromRun,
  completeWorkflowRunDetail
};
