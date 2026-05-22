import type { ProjectManifest, WorkflowDefinition, WorkflowRuntimeProfile } from "@textflow/shared-types";
import { AuditTable, EmptyState, Panel } from "../../ui";
import { resolveWorkflowRuntimeProfile } from "../../workflow";
import { useWorkspace } from "../../store/workspaceStore";

export function ReportPreviewPage() {
  const {
    state: { snapshot }
  } = useWorkspace();
  const project = snapshot.current_project;

  if (!project) {
    return <EmptyState title="暂无报告" body="生成结果后即可预览 HTML 报告结构。" />;
  }

  const runtimeProfile = projectRuntimeProfile(project);

  return (
    <div className="report-layout">
      <Panel title="HTML 报告结构">
        <div className="report-block">
          <h4>1. 项目概览</h4>
          <p>{project.name}，共 {snapshot.corpus.length} 篇文档，最近更新时间 {project.updated_at}。</p>
        </div>
        <div className="report-block">
          <h4>2. 数据规模与流程参数</h4>
          <p>
            Source profile 为 <strong>{project.import_template.source_profile}</strong>，
            使用 {runtimeProfile.analysis.feature_term_count} 规模的特征词集进行后续分析。
          </p>
        </div>
        <div className="report-block">
          <h4>3. 关键词聚类摘要</h4>
          <ul className="feature-list">
            {project.results.keyword_cluster_result
              .filter((row) => row.is_label_term)
              .slice(0, 24)
              .map((row) => (
                <li key={`${row.cluster_id}-${row.term}`}>Cluster {row.cluster_id}: {row.topic_label}</li>
              ))}
          </ul>
        </div>
      </Panel>

      <Panel title="规则审计摘要">
        <AuditTable rows={project.results.audit_table} />
      </Panel>
    </div>
  );
}

function projectRuntimeProfile(
  project: ProjectManifest | null | undefined,
  workflow?: WorkflowDefinition | null
): WorkflowRuntimeProfile {
  return resolveWorkflowRuntimeProfile(project, workflow);
}
