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
  DictionaryTableResource,
  CorpusItem,
  DictionaryKind,
  ExportFormat,
  PageId,
  ProjectManifest,
  ProjectSummary,
  RunRecord,
  WorkspaceSnapshot
} from "@textflow/shared-types";
import type {
  DeleteCorpusDocumentResponse,
  DeleteProjectResponse,
  EngineProgressEvent,
  ExportProjectResponse,
  ExportProjectBackupResponse,
  ImportProjectFilesResponse
} from "../bridge/desktopBridge";
import { desktopBridge } from "../bridge/desktopBridge";

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
  uiScale: number;
}

type WorkspaceAction =
  | { type: "setPage"; page: PageId }
  | { type: "setLoading"; loading: boolean; statusLine?: string }
  | { type: "loadSnapshot"; snapshot: WorkspaceSnapshot; statusLine?: string }
  | { type: "setStatus"; statusLine: string }
  | { type: "prependProject"; project: ProjectSummary }
  | { type: "patchProject"; project: ProjectManifest; summary: ProjectSummary; statusLine?: string }
  | { type: "setLastExport"; lastExport: ExportProjectResponse | null }
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
  runPipeline: () => Promise<RunRecord | null>;
  exportProject: (formats: ExportFormat[]) => Promise<ExportProjectResponse | null>;
  openPath: (path: string) => Promise<void>;
  revealPath: (path: string) => Promise<void>;
  exportProjectBackup: (path?: string) => Promise<ExportProjectBackupResponse | null>;
  updateCorpusDocument: (document: CorpusItem) => Promise<CorpusItem | null>;
  deleteCorpusDocument: (docId: string) => Promise<DeleteCorpusDocumentResponse | null>;
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
    JSON.stringify(left.detail ?? null) === JSON.stringify(right.detail ?? null)
  );
}

function normalizeProgressDetail(
  event: EngineProgressEvent,
  previous: TaskProgressState
): TaskProgressState["detail"] {
  if (event.detail) {
    return event.detail;
  }
  const nodeMatch = event.message.match(/^正在执行节点：(.+)$/);
  if (nodeMatch) {
    return {
      kind: "node",
      node_label: nodeMatch[1].trim()
    };
  }
  if (event.action === "run-pipeline" && event.status === "running" && previous.detail?.kind === "node") {
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
    case "setLastExport":
      return {
        ...state,
        lastExport: action.lastExport
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
      startTransition(() => {
        dispatch({ type: "setPage", page });
      });
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
        await refresh(actionLabel);
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
        await refresh(`导入词表 ${kind}`);
        return imported;
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
    runPipeline: async () => {
      const projectId = state.snapshot.current_project?.id;
      if (!projectId) {
        dispatch({ type: "setStatus", statusLine: "请先创建或打开项目。" });
        return null;
      }
      dispatch({ type: "setLoading", loading: true, statusLine: "正在运行预处理与分析流程..." });
      updateProgress({
        action: "run-pipeline",
        status: "running",
        value: 0.04,
        message: "正在运行预处理与分析流程..."
      });
      try {
        const run = await desktopBridge.runPipeline(projectId);
        setLastActionAt("运行流程");
        await refresh("运行流程");
        return run;
      } catch (error) {
        failAction("运行流程", error);
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
        await refresh("保存语料文档");
        return updated;
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
        await refresh("删除语料文档");
        return result;
      } catch (error) {
        failAction("删除语料文档", error);
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
