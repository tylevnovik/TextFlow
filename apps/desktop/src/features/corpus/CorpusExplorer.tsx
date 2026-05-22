import type { ProjectManifest, WorkspaceSnapshot } from "@textflow/shared-types";

export type CorpusExplorerNodeKind = "all_corpus" | "source_file" | "corpus_view" | "ingestion_spec";

export interface CorpusExplorerNode {
  id: string;
  kind: CorpusExplorerNodeKind;
  label: string;
  detail: string;
  badge?: string;
}

export function buildCorpusExplorerNodes(snapshot: WorkspaceSnapshot): CorpusExplorerNode[] {
  const project = snapshot.current_project;

  return [
    {
      id: "all-corpus",
      kind: "all_corpus",
      label: "全部语料",
      detail: `${snapshot.corpus.length} 篇文档`,
      badge: String(snapshot.corpus.length)
    },
    ...sourceFileNodes(project),
    {
      id: project?.import_template.id ?? "active-template",
      kind: "ingestion_spec",
      label: "当前导入规范",
      detail: project?.import_template.name ?? "等待项目加载"
    },
    ...((project?.corpus_views ?? []).map((view) => ({
      id: view.id,
      kind: "corpus_view" as const,
      label: view.name,
      detail: view.doc_ids ? `${view.doc_ids.length} 篇文档` : `${view.resource_ids.length} 个语料资源`
    })))
  ];
}

export function CorpusExplorer({
  nodes,
  selectedId,
  onSelectNode
}: {
  nodes: CorpusExplorerNode[];
  selectedId?: string;
  onSelectNode?: (node: CorpusExplorerNode) => void;
}) {
  return (
    <nav className="corpus-explorer" aria-label="语料对象">
      {nodes.map((node) => (
        <button
          key={`${node.kind}-${node.id}`}
          type="button"
          className={`corpus-explorer-node ${selectedId === node.id ? "is-active" : ""}`}
          onClick={() => onSelectNode?.(node)}
        >
          <span>
            <strong>{node.label}</strong>
            <small>{node.detail}</small>
          </span>
          {node.badge && <em>{node.badge}</em>}
        </button>
      ))}
    </nav>
  );
}

function sourceFileNodes(project?: ProjectManifest): CorpusExplorerNode[] {
  return (project?.source_files ?? []).slice(0, 5).map((sourceFile) => ({
    id: sourceFile.id,
    kind: "source_file",
    label: sourceFile.name,
    detail: `${sourceFile.row_count} 行 · ${sourceFile.source_type}`,
    badge: sourceFile.source_type.toUpperCase()
  }));
}
