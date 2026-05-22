import type { ReactNode } from "react";
import { Button, Divider } from "@fluentui/react-components";
import { DesktopFlowRegular } from "@fluentui/react-icons";
import { sourceProfiles, type CorpusItem, type ProjectManifest } from "@textflow/shared-types";
import type { WorkbenchSelection } from "../../app/workbenchSelection";

type CorpusInspectorSelection = Extract<
  WorkbenchSelection,
  { kind: "corpus_collection" | "corpus_document" | "ingestion_spec" }
>;

export function CorpusInspector({
  selection,
  project,
  corpus,
  onSendToWorkflow
}: {
  selection: CorpusInspectorSelection;
  project: ProjectManifest;
  corpus: CorpusItem[];
  onSendToWorkflow?: () => void;
}) {
  switch (selection.kind) {
    case "corpus_document":
      return (
        <CorpusDocumentInspector
          doc={corpus.find((item) => item.doc_id === selection.docId) ?? null}
          onSendToWorkflow={onSendToWorkflow}
        />
      );
    case "ingestion_spec":
      return (
        <InspectorCard
          eyebrow="导入规范"
          title={project.import_template.name}
          rows={[
            ["模板 ID", selection.specId],
            ["资料类型", sourceProfiles[project.import_template.source_profile]],
            ["字段映射", `${project.import_template.field_mappings.length} 条`],
            ["主文本字段", project.import_template.text_build.fields.join(" + ") || "未配置"],
            ["跳过空值", project.import_template.text_build.skip_empty ? "是" : "否"]
          ]}
        />
      );
    default:
      return (
        <InspectorCard
          eyebrow="语料集合"
          title={collectionTitle(selection.collectionId, project)}
          rows={collectionRows(selection.collectionId, project, corpus)}
          footer={(
            <Button
              appearance="primary"
              icon={<DesktopFlowRegular />}
              onClick={onSendToWorkflow}
              disabled={!corpus.length}
            >
              发送到节点图
            </Button>
          )}
        />
      );
  }
}

function CorpusDocumentInspector({
  doc,
  onSendToWorkflow
}: {
  doc: CorpusItem | null;
  onSendToWorkflow?: () => void;
}) {
  if (!doc) {
    return (
      <InspectorCard
        eyebrow="语料文档"
        title="文档未找到"
        rows={[["状态", "当前选择已不在语料库中"]]}
      />
    );
  }

  return (
    <div className="workbench-inspector-card corpus-inspector-card">
      <p className="workbench-kicker">语料文档</p>
      <h3>{doc.title || doc.doc_id}</h3>
      <Divider />
      <dl className="workbench-inspector-list">
        <InspectorRow label="文档 ID" value={doc.doc_id} />
        <InspectorRow label="资料类型" value={sourceProfiles[doc.source_profile]} />
        <InspectorRow label="状态" value={doc.status} />
        <InspectorRow label="年份" value={doc.year ? String(doc.year) : "未标年"} />
        <InspectorRow label="机构" value={doc.institution || "未填写"} />
        <InspectorRow label="来源" value={doc.source || "未填写"} />
      </dl>
      <div className="corpus-inspector-excerpt">
        <strong>正文</strong>
        <p>{clipText(doc.raw_text)}</p>
      </div>
      <div className="corpus-inspector-excerpt">
        <strong>清洗文本</strong>
        <p>{clipText(doc.clean_text || doc.normalized_text || "尚未生成清洗文本")}</p>
      </div>
      <div className="corpus-inspector-token-strip" aria-label="tokens">
        {(doc.filtered_tokens.length ? doc.filtered_tokens : doc.tokens).slice(0, 14).map((token) => (
          <span key={token}>{token}</span>
        ))}
      </div>
      <details className="corpus-inspector-metadata">
        <summary>元数据</summary>
        <pre>{JSON.stringify(doc.extra_metadata, null, 2)}</pre>
      </details>
      <Button
        appearance="primary"
        icon={<DesktopFlowRegular />}
        onClick={onSendToWorkflow}
      >
        发送到节点图
      </Button>
    </div>
  );
}

function InspectorCard({
  eyebrow,
  title,
  rows,
  footer
}: {
  eyebrow: string;
  title: string;
  rows: Array<[string, string]>;
  footer?: ReactNode;
}) {
  return (
    <div className="workbench-inspector-card">
      <p className="workbench-kicker">{eyebrow}</p>
      <h3>{title}</h3>
      <Divider />
      <dl className="workbench-inspector-list">
        {rows.map(([label, value]) => (
          <InspectorRow key={label} label={label} value={value} />
        ))}
      </dl>
      {footer}
    </div>
  );
}

function InspectorRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function collectionTitle(collectionId: string, project: ProjectManifest): string {
  if (collectionId === "all-corpus") {
    return "全部语料";
  }
  if (collectionId.startsWith("source:")) {
    return project.source_files.find((item) => item.id === collectionId.slice("source:".length))?.name ?? collectionId;
  }
  return project.corpus_views.find((view) => view.id === collectionId)?.name ?? collectionId;
}

function collectionRows(collectionId: string, project: ProjectManifest, corpus: CorpusItem[]): Array<[string, string]> {
  if (collectionId.startsWith("source:")) {
    const sourceFile = project.source_files.find((item) => item.id === collectionId.slice("source:".length));
    return [
      ["文档数", `${sourceFile?.row_count ?? 0}`],
      ["文件类型", sourceFile?.source_type ?? "未知"],
      ["导入时间", sourceFile?.imported_at ?? "未知"],
      ["Source profile", sourceFile?.source_profile ?? project.import_template.source_profile]
    ];
  }

  const view = project.corpus_views.find((item) => item.id === collectionId);
  return [
    ["文档数", `${view?.doc_ids?.length ?? corpus.length}`],
    ["导入批次", `${project.source_files.length}`],
    ["保存视图", `${project.corpus_views.length}`],
    ["Source profile", project.import_template.source_profile]
  ];
}

function clipText(value: string): string {
  return value.length > 180 ? `${value.slice(0, 180)}...` : value;
}
