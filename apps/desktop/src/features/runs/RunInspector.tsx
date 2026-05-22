import type { ReactNode } from "react";
import { Button, Divider } from "@fluentui/react-components";
import type { ArtifactRecord, ExportFormat, ProjectManifest, RunRecord } from "@textflow/shared-types";
import type { WorkbenchSelection } from "../../app/workbenchSelection";

type RunInspectorSelection = Extract<WorkbenchSelection, { kind: "run" | "artifact" }>;

export function RunInspector({
  selection,
  project,
  loading,
  onOpenRun,
  onOpenArtifact,
  onExportFormats
}: {
  selection: RunInspectorSelection;
  project: ProjectManifest;
  loading?: boolean;
  onOpenRun?: (run: RunRecord) => void;
  onOpenArtifact?: (artifact: ArtifactRecord) => void;
  onExportFormats?: (formats: ExportFormat[]) => void | Promise<void>;
}) {
  if (selection.kind === "artifact") {
    const artifact = project.artifact_records.find((item) => item.artifact_id === selection.artifactId)
      ?? project.artifact_records[0]
      ?? null;
    return (
      <ArtifactInspector
        artifact={artifact}
        run={artifact ? findRun(project, artifact.run_id) : null}
        loading={loading}
        onOpenArtifact={onOpenArtifact}
        onExportFormats={onExportFormats}
      />
    );
  }

  const run = project.run_history.find((item) => item.run_id === selection.runId)
    ?? project.run_history.at(-1)
    ?? project.run_history[0]
    ?? null;
  return (
    <RunDetailInspector
      run={run}
      artifacts={run ? project.artifact_records.filter((artifact) => artifact.run_id === run.run_id) : []}
      loading={loading}
      onOpenRun={onOpenRun}
      onOpenArtifact={onOpenArtifact}
      onExportFormats={onExportFormats}
    />
  );
}

function RunDetailInspector({
  run,
  artifacts,
  loading,
  onOpenRun,
  onOpenArtifact,
  onExportFormats
}: {
  run: RunRecord | null;
  artifacts: ArtifactRecord[];
  loading?: boolean;
  onOpenRun?: (run: RunRecord) => void;
  onOpenArtifact?: (artifact: ArtifactRecord) => void;
  onExportFormats?: (formats: ExportFormat[]) => void | Promise<void>;
}) {
  if (!run) {
    return (
      <InspectorCard
        eyebrow="运行"
        title="暂无运行"
        rows={[["状态", "运行节点图后会生成记录"]]}
      />
    );
  }

  return (
    <InspectorCard
      eyebrow="运行"
      title={run.run_id}
      rows={[
        ["状态", run.status],
        ["流程", run.workflow_name],
        ["开始", run.started_at],
        ["结束", run.ended_at ?? "处理中"],
        ["处理文档", `${run.processed_document_count}`],
        ["参数快照", run.params_snapshot_path],
        ["产物", `${artifacts.length} 个节点产物`]
      ]}
    >
      <div className="run-inspector-actions">
        <Button size="small" onClick={() => onOpenRun?.(run)} disabled={loading || !onOpenRun}>
          打开运行详情
        </Button>
        <Button size="small" appearance="subtle" onClick={() => void onExportFormats?.(["csv", "xlsx"])} disabled={loading || !onExportFormats}>
          导出表格
        </Button>
        <Button size="small" appearance="subtle" onClick={() => void onExportFormats?.(["html", "png"])} disabled={loading || !onExportFormats}>
          导出报告
        </Button>
      </div>
      <div className="workflow-inspector-excerpt">
        <strong>运行范围</strong>
        <p>{run.run_scope_summary || "处理对象：项目内全部资料"}</p>
      </div>
      <ArtifactList artifacts={artifacts} onOpenArtifact={onOpenArtifact} loading={loading} />
    </InspectorCard>
  );
}

function ArtifactInspector({
  artifact,
  run,
  loading,
  onOpenArtifact,
  onExportFormats
}: {
  artifact: ArtifactRecord | null;
  run: RunRecord | null;
  loading?: boolean;
  onOpenArtifact?: (artifact: ArtifactRecord) => void;
  onExportFormats?: (formats: ExportFormat[]) => void | Promise<void>;
}) {
  if (!artifact) {
    return (
      <InspectorCard
        eyebrow="产物"
        title="暂无产物"
        rows={[["状态", "输出节点运行后会生成产物"]]}
      />
    );
  }

  return (
    <InspectorCard
      eyebrow="产物"
      title={artifact.artifact_id}
      rows={[
        ["类型", artifact.kind],
        ["来源节点", artifact.node_id],
        ["运行", artifact.run_id],
        ["运行状态", run?.status ?? "未知"],
        ["行数", `${artifact.row_count ?? "未知"}`],
        ["预览", artifact.preview_path ?? "暂无预览文件"],
        ["路径", artifact.path || "存储在项目数据库"]
      ]}
    >
      <div className="run-inspector-actions">
        <Button size="small" onClick={() => onOpenArtifact?.(artifact)} disabled={loading || !onOpenArtifact}>
          打开产物
        </Button>
        <Button size="small" appearance="subtle" onClick={() => void onExportFormats?.(["csv"])} disabled={loading || !onExportFormats}>
          CSV
        </Button>
        <Button size="small" appearance="subtle" onClick={() => void onExportFormats?.(["xlsx"])} disabled={loading || !onExportFormats}>
          XLSX
        </Button>
        <Button size="small" appearance="subtle" onClick={() => void onExportFormats?.(["html", "png"])} disabled={loading || !onExportFormats}>
          HTML/PNG
        </Button>
      </div>
      <div className="workflow-inspector-excerpt">
        <strong>追溯</strong>
        <p>{run ? `${run.workflow_name} · ${run.params_snapshot_path}` : "当前产物暂未匹配到运行记录。"}</p>
      </div>
    </InspectorCard>
  );
}

function ArtifactList({
  artifacts,
  onOpenArtifact,
  loading
}: {
  artifacts: ArtifactRecord[];
  onOpenArtifact?: (artifact: ArtifactRecord) => void;
  loading?: boolean;
}) {
  if (!artifacts.length) {
    return null;
  }

  return (
    <div className="workflow-inspector-artifacts" aria-label="运行产物">
      {artifacts.slice(0, 6).map((artifact) => (
        <Button
          appearance="subtle"
          key={artifact.artifact_id}
          className="run-inspector-artifact"
          onClick={() => onOpenArtifact?.(artifact)}
          disabled={loading || !onOpenArtifact}
        >
          <strong>{artifact.kind}</strong>
          <span>{artifact.artifact_id}</span>
        </Button>
      ))}
    </div>
  );
}

function InspectorCard({
  eyebrow,
  title,
  rows,
  children
}: {
  eyebrow: string;
  title: string;
  rows: Array<[string, string]>;
  children?: ReactNode;
}) {
  return (
    <div className="workbench-inspector-card run-inspector-card">
      <p className="workbench-kicker">{eyebrow}</p>
      <h3>{title}</h3>
      <Divider />
      <dl className="workbench-inspector-list">
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      {children}
    </div>
  );
}

function findRun(project: ProjectManifest, runId: string): RunRecord | null {
  return project.run_history.find((run) => run.run_id === runId) ?? null;
}
