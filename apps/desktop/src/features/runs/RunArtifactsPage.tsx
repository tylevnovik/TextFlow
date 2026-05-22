import { Button } from "@fluentui/react-components";
import type { ExportFormat, ProjectManifest } from "@textflow/shared-types";
import type { WorkbenchSelection } from "../../app/workbenchSelection";
import { useWorkspace } from "../../store/workspaceStore";
import { EmptyState, Panel } from "../../ui";
import { ArtifactWorkspace } from "./ArtifactWorkspace";
import { RunHistoryWorkspace } from "./RunHistoryWorkspace";

export function RunArtifactsPage({
  workbenchSelection,
  onWorkbenchSelect
}: {
  workbenchSelection?: WorkbenchSelection;
  onWorkbenchSelect?: (selection: WorkbenchSelection) => void;
}) {
  const {
    state: { snapshot, loading, lastExport },
    compareRuns,
    exportProject,
    exportProjectBackup,
    loadArtifactPreview,
    openPath,
    revealPath,
    saveProjectPackagePath
  } = useWorkspace();
  const project = snapshot.current_project;

  if (!project) {
    return <EmptyState title="还没有结果" body="先完成一次处理，这里就会出现表格、图表和报告。" />;
  }

  const currentProjectSummary = snapshot.recent_projects.find((item) => item.id === project.id);
  const projectRootPath = currentProjectSummary?.path;
  const fallbackExportDir = projectRootPath ? joinFsPath(projectRootPath, project.paths.exports_dir) : null;
  const visibleExport = lastExport?.project_id === project.id ? lastExport : null;
  const exportDirPath = visibleExport?.export_dir ?? fallbackExportDir;
  const exportDirLabel = visibleExport?.relative_export_dir ?? project.paths.exports_dir;
  const generatedFiles = projectRootPath
    ? project.results.report_files.map((relativePath) => ({
        path: joinFsPath(projectRootPath, relativePath),
        relative_path: relativePath
      }))
    : [];

  const handleExportProjectPackage = async () => {
    const path = await saveProjectPackagePath(`${project.name}.tfproj`);
    if (!path) {
      return;
    }
    await exportProjectBackup(path);
  };

  const handleLoadArtifactPreview = async (artifactId: string) => {
    const preview = await loadArtifactPreview(artifactId);
    return preview ?? {
      artifact_id: artifactId,
      rows: [],
      row_count: 0
    };
  };

  const handleExportResults = async (formats: ExportFormat[]) => {
    await exportProject(formats);
  };

  const selectRun = (run: ProjectManifest["run_history"][number]) => {
    onWorkbenchSelect?.({
      kind: "run",
      projectId: project.id,
      runId: run.run_id
    });
  };

  const selectArtifact = (artifact: ProjectManifest["artifact_records"][number]) => {
    onWorkbenchSelect?.({
      kind: "artifact",
      projectId: project.id,
      artifactId: artifact.artifact_id
    });
  };

  const showArtifactWorkspace = workbenchSelection?.kind === "artifact";
  const selectedArtifactId = workbenchSelection?.kind === "artifact" ? workbenchSelection.artifactId : undefined;

  return (
    <>
      <Panel
        title="运行产物与导出"
        actions={
          <div className="button-row">
            <Button appearance="primary" onClick={() => void handleExportResults(["csv", "xlsx"])} disabled={loading}>
              导出表格
            </Button>
            <Button onClick={() => void handleExportResults(["html", "png"])} disabled={loading}>
              导出报告与图表
            </Button>
            <Button appearance="subtle" onClick={() => void handleExportProjectPackage()} disabled={loading}>
              导出 .tfproj 项目包
            </Button>
          </div>
        }
      >
        <ul className="feature-list">
          <li>表格导出适合继续在 Excel 里筛选和汇总。</li>
          <li>报告与图表导出会包含高频词图、项目关键词图、关键词词云、机构主题热力图和文档聚类图。</li>
          <li>`.tfproj` 项目包会把项目、语料、词库、运行记录和导出文件一起打成一个单文件。</li>
        </ul>
        <div className="status-panel export-location-panel">
          <strong>导出位置</strong>
          <p className="project-path">{exportDirPath ?? "还没有导出过结果。导出后会自动打开导出文件夹。"}</p>
          <div className="button-row">
            <Button
              onClick={() => exportDirPath ? void openPath(exportDirPath) : undefined}
              disabled={loading || !exportDirPath}
            >
              打开导出文件夹
            </Button>
            <Button
              appearance="subtle"
              onClick={() => visibleExport?.files[0] ? void revealPath(visibleExport.files[0].path) : undefined}
              disabled={loading || !visibleExport?.files.length}
            >
              定位最近导出的文件
            </Button>
          </div>
          <span className="muted">
            {visibleExport
              ? `最近一次导出保存在 ${visibleExport.relative_export_dir}，导出完成后会自动打开该文件夹。`
              : `当前项目的导出目录固定在 ${exportDirLabel}。`}
          </span>
        </div>
      </Panel>

      {showArtifactWorkspace ? (
        <ArtifactWorkspace
          project={project}
          artifacts={project.artifact_records}
          loading={loading}
          selectedArtifactId={selectedArtifactId}
          generatedFiles={visibleExport?.files.length ? visibleExport.files : generatedFiles}
          onLoadPreview={handleLoadArtifactPreview}
          onOpenArtifact={selectArtifact}
          onExportFormats={handleExportResults}
          onOpenPath={openPath}
          onRevealPath={revealPath}
        />
      ) : (
        <RunHistoryWorkspace
          project={project}
          loading={loading}
          onSelectRun={selectRun}
          onCompareRuns={async (leftRunId, rightRunId) => {
            await compareRuns(leftRunId, rightRunId);
          }}
          onExportFormats={handleExportResults}
        />
      )}
    </>
  );
}

function joinFsPath(basePath: string, relativePath: string): string {
  const normalizedBase = basePath.replace(/[\\/]+$/, "");
  const normalizedRelative = relativePath.replace(/^[\\/]+/, "").replace(/\//g, "\\");
  return `${normalizedBase}\\${normalizedRelative}`;
}
