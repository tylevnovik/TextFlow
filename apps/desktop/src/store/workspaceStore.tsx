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
}

interface WorkspaceState {
  activePage: PageId;
  snapshot: WorkspaceSnapshot;
  loading: boolean;
  statusLine: string;
  progress: TaskProgressState;
  lastExport: ExportProjectResponse | null;
}

type WorkspaceAction =
  | { type: "setPage"; page: PageId }
  | { type: "setLoading"; loading: boolean; statusLine?: string }
  | { type: "loadSnapshot"; snapshot: WorkspaceSnapshot; statusLine?: string }
  | { type: "setStatus"; statusLine: string }
  | { type: "prependProject"; project: ProjectSummary }
  | { type: "setProgress"; progress: TaskProgressState }
  | { type: "setLastExport"; lastExport: ExportProjectResponse | null };

interface WorkspaceContextValue {
  state: WorkspaceState;
  setActivePage: (page: PageId) => void;
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
  importDictionarySheet: (kind: DictionaryKind, path: string) => Promise<void>;
  exportDictionarySheet: (kind: DictionaryKind, path: string) => Promise<{ kind: DictionaryKind; path: string } | null>;
  pickJsonFile: () => Promise<string | null>;
  saveJsonFilePath: (defaultFileName?: string) => Promise<string | null>;
  pickProjectPackageFile: () => Promise<string | null>;
  saveProjectPackagePath: (defaultFileName?: string) => Promise<string | null>;
  importProjectPackage: (path: string) => Promise<void>;
  saveProject: (project: ProjectManifest) => Promise<boolean>;
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

const idleProgress: TaskProgressState = {
  action: "",
  status: "idle",
  value: 0,
  message: ""
};

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
    case "setProgress":
      return {
        ...state,
        loading: action.progress.status === "running" || action.progress.status === "pending",
        progress: action.progress,
        statusLine: action.progress.message || state.statusLine
      };
    case "setLastExport":
      return {
        ...state,
        lastExport: action.lastExport
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
  progress: idleProgress,
  lastExport: null
};

export function WorkspaceProvider({ children }: PropsWithChildren) {
  const [state, dispatch] = useReducer(reducer, initialState);
  const [lastActionAt, setLastActionAt] = useState<string>("尚未执行");

  const failAction = (actionLabel: string, error: unknown) => {
    const message = `${actionLabel}失败：${formatErrorMessage(error)}`;
    dispatch({
      type: "setProgress",
      progress: {
        action: actionLabel,
        status: "failed",
        value: 1,
        message
      }
    });
    dispatch({
      type: "setLoading",
      loading: false,
      statusLine: message
    });
  };

  const refresh = async (actionLabel?: string) => {
    dispatch({
      type: "setProgress",
      progress: {
        action: "load-workspace",
        status: "running",
        value: 0.06,
        message: "正在加载项目和语料..."
      }
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
      dispatch({
        type: "setProgress",
        progress: {
          action: "load-workspace",
          status: "completed",
          value: 1,
          message: "工作区已更新"
        }
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
      dispatch({
        type: "setProgress",
        progress: {
          action: event.action,
          status: nextStatus,
          value: Math.max(0, Math.min(1, event.progress)),
          message: event.message
        }
      });
    }).then((dispose) => {
      unlisten = dispose;
    });

    return () => {
      if (unlisten) {
        unlisten();
      }
    };
  }, []);

  const value = useMemo<WorkspaceContextValue>(() => ({
    state,
    setActivePage: (page) => {
      startTransition(() => {
        dispatch({ type: "setPage", page });
      });
    },
    refresh,
    createProject: async (name, description) => {
      dispatch({ type: "setLoading", loading: true, statusLine: "正在创建项目..." });
      dispatch({
        type: "setProgress",
        progress: {
          action: "create-project",
          status: "running",
          value: 0.04,
          message: "正在创建项目..."
        }
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
      dispatch({
        type: "setProgress",
        progress: {
          action: "open-project",
          status: "running",
          value: 0.04,
          message: "正在打开项目..."
        }
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
      dispatch({
        type: "setProgress",
        progress: {
          action: "duplicate-project",
          status: "running",
          value: 0.04,
          message: "正在复制项目..."
        }
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
      dispatch({
        type: "setProgress",
        progress: {
          action: "delete-project",
          status: "running",
          value: 0.04,
          message: "正在删除项目..."
        }
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
      dispatch({
        type: "setProgress",
        progress: {
          action: "import-project-files",
          status: "running",
          value: 0.04,
          message: "正在导入文件并更新语料库..."
        }
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
    importDictionarySheet: async (kind, path) => {
      const projectId = state.snapshot.current_project?.id;
      if (!projectId) {
        dispatch({ type: "setStatus", statusLine: "请先创建或打开项目，再导入词表。" });
        return;
      }
      dispatch({ type: "setLoading", loading: true, statusLine: "正在导入词表..." });
      dispatch({
        type: "setProgress",
        progress: {
          action: "import-dictionary-sheet",
          status: "running",
          value: 0.04,
          message: "正在导入词表..."
        }
      });
      try {
        await desktopBridge.importDictionarySheet(projectId, kind, path);
        setLastActionAt(`导入词表 ${kind}`);
        await refresh(`导入词表 ${kind}`);
      } catch (error) {
        failAction(`导入词表 ${kind}`, error);
      }
    },
    exportDictionarySheet: async (kind, path) => {
      const projectId = state.snapshot.current_project?.id;
      if (!projectId) {
        dispatch({ type: "setStatus", statusLine: "当前没有可导出的词表。" });
        return null;
      }
      dispatch({ type: "setLoading", loading: true, statusLine: "正在导出词表..." });
      dispatch({
        type: "setProgress",
        progress: {
          action: "export-dictionary-sheet",
          status: "running",
          value: 0.04,
          message: "正在导出词表..."
        }
      });
      try {
        const result = await desktopBridge.exportDictionarySheet(projectId, kind, path);
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
      dispatch({
        type: "setProgress",
        progress: {
          action: "import-project-package",
          status: "running",
          value: 0.04,
          message: "正在导入 .tfproj 项目包..."
        }
      });
      try {
        await desktopBridge.importProjectPackage(path);
        setLastActionAt("导入项目包");
        await refresh("导入项目包");
      } catch (error) {
        failAction("导入项目包", error);
      }
    },
    saveProject: async (project) => {
      dispatch({ type: "setLoading", loading: true, statusLine: "正在保存项目配置..." });
      dispatch({
        type: "setProgress",
        progress: {
          action: "save-project",
          status: "running",
          value: 0.04,
          message: "正在保存项目配置..."
        }
      });
      try {
        await desktopBridge.saveProject(project);
        setLastActionAt("保存项目配置");
        await refresh("保存项目配置");
        return true;
      } catch (error) {
        failAction("保存项目配置", error);
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
      dispatch({
        type: "setProgress",
        progress: {
          action: "run-pipeline",
          status: "running",
          value: 0.04,
          message: "正在运行预处理与分析流程..."
        }
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
      dispatch({
        type: "setProgress",
        progress: {
          action: "export-project",
          status: "running",
          value: 0.04,
          message: "正在打包导出结果..."
        }
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
      dispatch({
        type: "setProgress",
        progress: {
          action: "export-project-backup",
          status: "running",
          value: 0.04,
          message: "正在打包完整项目备份..."
        }
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
      dispatch({
        type: "setProgress",
        progress: {
          action: "update-corpus-document",
          status: "running",
          value: 0.04,
          message: "正在保存语料文档..."
        }
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
      dispatch({
        type: "setProgress",
        progress: {
          action: "delete-corpus-document",
          status: "running",
          value: 0.04,
          message: "正在删除语料文档..."
        }
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

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace() {
  const value = useContext(WorkspaceContext);
  if (!value) {
    throw new Error("Workspace context is unavailable.");
  }
  return value;
}
