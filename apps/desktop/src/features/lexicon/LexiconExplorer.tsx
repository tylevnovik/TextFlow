import type { DictionaryKind, WorkspaceSnapshot } from "@textflow/shared-types";

export const lexiconKindLabels: Record<DictionaryKind, string> = {
  stopwords: "停用词",
  custom_lexicon: "自定义词典",
  phrase_lexicon: "短语词典",
  synonym_map: "同义词",
  near_synonym_map: "近义词",
  standard_terms: "标准词",
  exclusion_terms: "排除词",
  regex_rules: "正则规则"
};

export const lexiconKindOrder = Object.keys(lexiconKindLabels) as DictionaryKind[];

export type LexiconExplorerNodeKind = "kind" | "table";

export interface LexiconExplorerNode {
  id: string;
  kind: LexiconExplorerNodeKind;
  dictionaryKind: DictionaryKind;
  label: string;
  detail: string;
  badge?: string;
}

export function buildLexiconExplorerNodes(snapshot: WorkspaceSnapshot): LexiconExplorerNode[] {
  const collections = snapshot.current_project?.dictionary_set.collections;
  if (!collections) {
    return lexiconKindOrder.map((dictionaryKind) => ({
      id: dictionaryKind,
      kind: "kind",
      dictionaryKind,
      label: lexiconKindLabels[dictionaryKind],
      detail: "等待项目加载"
    }));
  }

  return lexiconKindOrder.flatMap((dictionaryKind) => {
    const collection = collections[dictionaryKind];
    const tables = collection?.tables ?? [];
    const enabledEntries = tables.reduce((sum, table) => {
      if (!table.enabled) {
        return sum;
      }
      return sum + table.entries.filter((entry) => entry.enabled).length;
    }, 0);

    return [
      {
        id: dictionaryKind,
        kind: "kind" as const,
        dictionaryKind,
        label: collection?.name ?? lexiconKindLabels[dictionaryKind],
        detail: `${tables.length} 张资源表`,
        badge: String(enabledEntries)
      },
      ...tables.map((table) => ({
        id: table.id,
        kind: "table" as const,
        dictionaryKind,
        label: table.name,
        detail: `${table.entries.length} 条 · ${table.built_in ? "内置" : "项目内"}`,
        badge: table.enabled ? "启用" : "停用"
      }))
    ];
  });
}

export function LexiconExplorer({
  nodes,
  selectedId,
  onSelectNode
}: {
  nodes: LexiconExplorerNode[];
  selectedId?: string;
  onSelectNode?: (node: LexiconExplorerNode) => void;
}) {
  return (
    <nav className="lexicon-explorer" aria-label="词库对象">
      {nodes.map((node) => (
        <button
          key={`${node.kind}-${node.dictionaryKind}-${node.id}`}
          type="button"
          className={`lexicon-explorer-node node-${node.kind} ${selectedId === node.id ? "is-active" : ""}`}
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
