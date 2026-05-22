import { Button, Toolbar, ToolbarButton, Tooltip } from "@fluentui/react-components";
import {
  ArrowDownloadRegular,
  DocumentTableRegular,
  FolderOpenRegular,
  OpenRegular
} from "@fluentui/react-icons";
import type { ArtifactRecord, ExportFormat, ProjectManifest } from "@textflow/shared-types";
import type { ArtifactPreview } from "../artifacts/ArtifactBrowser";
import { ArtifactBrowser } from "../artifacts/ArtifactBrowser";
import { buildRunCommands, type RunCommandId } from "./runCommands";

export interface ExportedWorkspaceFile {
  path: string;
  relative_path: string;
}

export interface ArtifactWorkspaceProps {
  project: ProjectManifest;
  artifacts: ArtifactRecord[];
  loading: boolean;
  selectedArtifactId?: string;
  generatedFiles?: ExportedWorkspaceFile[];
  onLoadPreview: (artifactId: string) => Promise<ArtifactPreview>;
  onOpenArtifact?: (artifact: ArtifactRecord) => void;
  onExportFormats?: (formats: ExportFormat[]) => void | Promise<void>;
  onOpenPath?: (path: string) => void | Promise<void>;
  onRevealPath?: (path: string) => void | Promise<void>;
}

export function ArtifactWorkspace({
  project,
  artifacts,
  loading,
  selectedArtifactId,
  generatedFiles = [],
  onLoadPreview,
  onOpenArtifact,
  onExportFormats,
  onOpenPath,
  onRevealPath
}: ArtifactWorkspaceProps) {
  const selectedArtifact = artifacts.find((artifact) => artifact.artifact_id === selectedArtifactId)
    ?? artifacts[0]
    ?? null;
  const commands = buildRunCommands({
    loading,
    artifact: selectedArtifact
  }).filter((command) => command.id !== "open_run" && command.id !== "compare_latest");

  const runCommand = (id: RunCommandId, formats?: ExportFormat[]) => {
    switch (id) {
      case "open_artifact":
        if (selectedArtifact) {
          onOpenArtifact?.(selectedArtifact);
        }
        return;
      case "export_csv":
      case "export_xlsx":
      case "export_html":
      case "export_png":
        if (formats?.length) {
          return onExportFormats?.(formats);
        }
        return;
      default:
        return;
    }
  };

  return (
    <div className="artifact-workspace">
      <section className="run-workspace-toolbar" aria-label="产物命令栏">
        <Toolbar>
          {commands.map((command) => (
            <Tooltip key={command.id} content={command.label} relationship="label">
              <ToolbarButton
                icon={commandIcon(command.id)}
                appearance={command.id === "open_artifact" ? "primary" : "subtle"}
                disabled={command.disabled}
                onClick={() => void runCommand(command.id, command.formats)}
              >
                {command.label}
              </ToolbarButton>
            </Tooltip>
          ))}
        </Toolbar>
      </section>

      <section className="run-workspace-summary" aria-label="产物摘要">
        <article>
          <span>节点产物</span>
          <strong>{artifacts.length}</strong>
        </article>
        <article>
          <span>来源运行</span>
          <strong>{selectedArtifact?.run_id ?? "暂无"}</strong>
        </article>
        <article>
          <span>来源节点</span>
          <strong>{selectedArtifact?.node_id ?? "暂无"}</strong>
        </article>
        <article>
          <span>已生成文件</span>
          <strong>{generatedFiles.length || project.results.report_files.length}</strong>
        </article>
      </section>

      <ArtifactBrowser
        title="运行产物预览"
        artifacts={artifacts}
        loading={loading}
        selectedArtifactId={selectedArtifactId}
        onLoadPreview={onLoadPreview}
        onOpenArtifact={onOpenArtifact}
      />

      <section className="panel generated-files-panel">
        <header className="panel-head">
          <div><h3>已生成文件</h3></div>
        </header>
        <div className="artifact-list">
          {generatedFiles.map((file) => (
            <article key={file.path} className="project-card artifact-row">
              <div>
                <h4>{fileNameFromPath(file.relative_path)}</h4>
                <p className="project-path">{file.relative_path}</p>
              </div>
              <div className="button-row">
                <Button onClick={() => void onOpenPath?.(file.path)} disabled={loading || !onOpenPath}>
                  打开
                </Button>
                <Button appearance="subtle" onClick={() => void onRevealPath?.(file.path)} disabled={loading || !onRevealPath}>
                  定位
                </Button>
              </div>
            </article>
          ))}
          {!generatedFiles.length && (
            <div className="status-panel">
              <strong>还没有可查看的导出文件</strong>
              <span className="muted">先从上方导出 CSV、XLSX、HTML 或 PNG，文件会记录在这里。</span>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

function commandIcon(id: RunCommandId) {
  switch (id) {
    case "open_artifact":
      return <OpenRegular />;
    case "export_csv":
    case "export_xlsx":
      return <DocumentTableRegular />;
    case "export_html":
    case "export_png":
      return <FolderOpenRegular />;
    default:
      return <ArrowDownloadRegular />;
  }
}

function fileNameFromPath(path: string): string {
  return path.split(/[\\/]/).filter(Boolean).at(-1) ?? path;
}
