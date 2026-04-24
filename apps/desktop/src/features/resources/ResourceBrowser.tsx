import type {
  CorpusItem,
  CorpusView,
  IngestionSpec,
  ProjectManifest
} from "@textflow/shared-types";
import { MiniMetric, Panel, Table } from "../../ui";

export interface ResourceBrowserProps {
  project: ProjectManifest;
  corpus: CorpusItem[];
  loading?: boolean;
  onOpenCorpusView?: (view: CorpusView) => void;
  onCreateCorpusView?: (view: Partial<CorpusView>) => Promise<void> | void;
  onSaveIngestionSpec?: (spec: Partial<IngestionSpec>) => Promise<void> | void;
}

function filterSummary(filterSpec: Record<string, unknown>): string {
  const entries = Object.entries(filterSpec);
  if (!entries.length) {
    return "全部文档";
  }
  return entries.map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(", ") : String(value)}`).join(" · ");
}

export function ResourceBrowser({
  project,
  corpus,
  loading = false,
  onOpenCorpusView,
  onCreateCorpusView,
  onSaveIngestionSpec
}: ResourceBrowserProps) {
  const resourceRows = project.corpus_resources.map((resource) => ({
    name: resource.name,
    source_files: resource.source_files.length,
    fingerprint: resource.fingerprint
  }));
  const specRows = project.ingestion_specs.map((spec) => ({
    name: spec.name,
    source_profile: spec.source_profile,
    fields: spec.field_mappings.length,
    dedupe: Object.keys(spec.dedupe_rules ?? {}).join(", ") || "未配置"
  }));

  const handleCreateCorpusView = () => {
    const resourceIds = project.corpus_resources.map((resource) => resource.id);
    void onCreateCorpusView?.({
      name: "当前语料视图",
      resource_ids: resourceIds,
      filter_spec: {},
      doc_ids: corpus.map((doc) => doc.doc_id)
    });
  };

  const handleSaveIngestionSpec = () => {
    void onSaveIngestionSpec?.({
      name: "当前导入规格",
      source_profile: project.import_template.source_profile,
      field_mappings: project.import_template.field_mappings,
      text_build: { ...project.import_template.text_build },
      dedupe_rules: { keys: ["title", "year"] }
    });
  };

  return (
    <Panel
      title="资源与语料视图"
      className="resource-browser-panel"
      actions={
        <div className="button-row">
          <button type="button" className="toolbar-button ghost" onClick={handleSaveIngestionSpec} disabled={loading || !onSaveIngestionSpec}>
            保存导入规格
          </button>
          <button type="button" className="toolbar-button" onClick={handleCreateCorpusView} disabled={loading || !onCreateCorpusView}>
            创建当前视图
          </button>
        </div>
      }
    >
      <div className="surface-metric-row">
        <MiniMetric label="资源" value={String(project.corpus_resources.length)} />
        <MiniMetric label="语料视图" value={String(project.corpus_views.length)} />
        <MiniMetric label="导入规格" value={String(project.ingestion_specs.length)} />
      </div>

      <div className="resource-browser-grid">
        <section className="surface-section">
          <div className="run-head">
            <h4>Corpus Views</h4>
            <span className="badge ready">{corpus.length} docs</span>
          </div>
          <div className="stack-list">
            {project.corpus_views.map((view) => (
              <article key={view.id} className="project-card resource-view-card">
                <div>
                  <h4>{view.name}</h4>
                  <p className="muted">{filterSummary(view.filter_spec)}</p>
                  <p className="muted">包含 {view.doc_ids?.length ?? corpus.length} 篇文档 · {view.resource_ids.length} 个资源</p>
                </div>
                <button type="button" className="toolbar-button compact" onClick={() => onOpenCorpusView?.(view)} disabled={loading}>
                  打开视图
                </button>
              </article>
            ))}
            {!project.corpus_views.length && (
              <div className="status-panel">
                <strong>还没有保存的语料视图</strong>
                <span className="muted">可先按资源、机构或年份生成一个可复用视图。</span>
              </div>
            )}
          </div>
        </section>

        <section className="surface-section">
          <h4>Ingestion Specs</h4>
          {specRows.length ? (
            <Table columns={["name", "source_profile", "fields", "dedupe"]} rows={specRows} rowKey="name" />
          ) : (
            <div className="status-panel">
              <strong>还没有导入规格</strong>
              <span className="muted">保存规格后，后续项目可以复用字段映射和正文构造规则。</span>
            </div>
          )}
        </section>
      </div>

      <section className="surface-section">
        <h4>Corpus Resources</h4>
        {resourceRows.length ? (
          <Table columns={["name", "source_files", "fingerprint"]} rows={resourceRows} rowKey="name" />
        ) : (
          <div className="status-panel">
            <strong>还没有资源索引</strong>
            <span className="muted">导入语料后会自动记录资源指纹，便于复现和审计。</span>
          </div>
        )}
      </section>
    </Panel>
  );
}
