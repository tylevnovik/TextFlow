import type {
  CorpusItem,
  DictionaryKind,
  DictionarySheet,
  ExportFormat,
  ProjectManifest,
  ProjectSummary,
  RunRecord,
  WorkspaceSnapshot
} from "@textflow/shared-types";
import { createSimulatedRun, demoProjectSummary, demoWorkspace } from "../data/demoProject";

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
}

export interface DeleteProjectResponse {
  project_id: string;
  deleted_path: string;
}

export interface EngineProgressEvent {
  action: string;
  status: string;
  progress: number;
  message: string;
}

interface DesktopBridge {
  loadWorkspace(): Promise<WorkspaceSnapshot>;
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
  runPipeline(projectId: string): Promise<RunRecord>;
  exportProject(projectId: string, formats: ExportFormat[]): Promise<ExportProjectResponse>;
  exportProjectBackup(projectId: string, path?: string): Promise<ExportProjectBackupResponse>;
  updateCorpusDocument(projectId: string, document: CorpusItem): Promise<CorpusItem>;
  deleteCorpusDocument(projectId: string, docId: string): Promise<DeleteCorpusDocumentResponse>;
  importDictionarySheet(projectId: string, kind: DictionaryKind, path: string): Promise<DictionarySheet>;
  exportDictionarySheet(projectId: string, kind: DictionaryKind, path: string): Promise<{ kind: DictionaryKind; path: string }>;
  saveProject(project: ProjectManifest): Promise<void>;
  openPath(path: string): Promise<void>;
  revealPath(path: string): Promise<void>;
  subscribeProgress(listener: (event: EngineProgressEvent) => void): Promise<() => void>;
}

declare global {
  interface Window {
    __TAURI_INTERNALS__?: unknown;
  }
}

const delay = (ms: number) => new Promise((resolve) => {
  window.setTimeout(resolve, ms);
});

async function tryInvoke<T>(command: string, payload?: Record<string, unknown>): Promise<T | null> {
  const { invoke, isTauri } = await import("@tauri-apps/api/core");
  if (!isTauri()) {
    return null;
  }
  return invoke<T>(command, payload);
}

export const desktopBridge: DesktopBridge = {
  async loadWorkspace() {
    const result = await tryInvoke<WorkspaceSnapshot>("load_workspace");
    if (result !== null) {
      return result;
    }
    await delay(180);
    return demoWorkspace;
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

  async runPipeline(projectId) {
    const result = await tryInvoke<RunRecord>("run_pipeline", { projectId });
    if (result !== null) {
      return result;
    }
    await delay(1_100);
    return createSimulatedRun();
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
    const result = await tryInvoke<CorpusItem>("update_corpus_document", { projectId, document });
    if (result !== null) {
      return result;
    }
    await delay(180);
    return document;
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

  async importDictionarySheet(projectId, kind, path) {
    const result = await tryInvoke<DictionarySheet>("import_dictionary_sheet", { projectId, kind, path });
    if (result !== null) {
      return result;
    }
    await delay(120);
    return demoWorkspace.current_project!.dictionary_set.sheets[kind];
  },

  async exportDictionarySheet(projectId, kind, path) {
    const result = await tryInvoke<{ kind: DictionaryKind; path: string }>("export_dictionary_sheet", {
      projectId,
      kind,
      path
    });
    if (result !== null) {
      return result;
    }
    await delay(90);
    return { kind, path };
  },

  async saveProject(project) {
    const result = await tryInvoke<ProjectSummary>("save_project", { project });
    if (result !== null) {
      return;
    }
    await delay(90);
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
      return () => {};
    }
    const { listen } = await import("@tauri-apps/api/event");
    return listen<EngineProgressEvent>("engine-progress", (event) => {
      listener(event.payload);
    });
  }
};
